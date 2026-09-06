from __future__ import annotations

import json
import os
import queue
import threading
from collections.abc import Iterator
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .cache import ResultCache
from .catalog import resolve_target_identifier
from .pipeline import PipelineConfig, TransitPipeline
from .scoring import load_candidate_scorer
from .service import ArchiveAnalysisOptions, analyze_archive_target


app = FastAPI(
    title="Exoplanet Transit Lab API",
    version="0.1.0",
    description="Detect and rank repeating transit-like signals in stellar light curves.",
)
app.add_middleware(
    CORSMiddleware,
    # The Vite dev server's port is assigned dynamically, so allow any
    # localhost/127.0.0.1 origin rather than pinning specific ports.
    allow_origin_regex=(
        r"https://[a-z0-9-]+\.vercel\.app"
        r"|http://(localhost|127\.0\.0\.1)(:\d+)?"
    ),
    allow_origins=[
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "").split(",")
        if origin.strip()
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
cache = ResultCache()


class AnalyzeRequest(BaseModel):
    target: str = Field(min_length=1, examples=["Kepler-90"])
    mission: str | None = Field(default=None, examples=["Kepler"])
    time: list[float] | None = None
    flux: list[float] | None = None
    use_archive: bool = Field(
        default=False,
        description="Fetch the target's real Kepler/TESS light curve through MAST via Lightkurve.",
    )
    cadence: str = Field(default="long", pattern="^(long|short|fast)$")
    max_files: int | None = Field(default=4, ge=1, le=100)
    max_candidates: int = Field(default=3, ge=1, le=5)
    min_period: float = Field(default=0.5, gt=0)
    max_period: float = Field(default=30.0, gt=0)
    use_catalog_period_hint: bool = Field(
        default=True,
        description="For KOI inputs, narrow the confirmation search around the NASA catalog period.",
    )


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "Exoplanet Transit Lab API", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/targets")
def targets() -> list[dict[str, str | int | bool]]:
    return cache.list_targets()


@app.get("/resolve/{target}")
def resolve(target: str) -> dict[str, str | int | float | None]:
    try:
        return resolve_target_identifier(target).to_dict()
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/candidates/{target}")
def candidates(target: str) -> dict[str, Any]:
    result = cache.load(target)
    if result is None:
        raise HTTPException(status_code=404, detail="Target is not present in the demo cache")
    return result.to_dict()


@app.get("/lightcurve/{target}")
def light_curve(target: str) -> dict[str, Any]:
    result = cache.load(target)
    if result is None:
        raise HTTPException(status_code=404, detail="Target is not present in the demo cache")
    return {
        "target": result.target,
        "source": result.source,
        "raw": result.raw_light_curve,
        "detrended": result.detrended_light_curve,
    }


@app.post("/analyze")
def analyze(request: AnalyzeRequest) -> dict[str, Any]:
    if (request.time is None) != (request.flux is None):
        raise HTTPException(status_code=422, detail="time and flux must be supplied together")
    if request.max_period <= request.min_period:
        raise HTTPException(status_code=422, detail="max_period must be greater than min_period")

    if request.use_archive and request.time is not None:
        raise HTTPException(
            status_code=422,
            detail="use_archive cannot be combined with time/flux request arrays",
        )

    if request.use_archive:
        try:
            result = analyze_archive_target(
                request.target,
                ArchiveAnalysisOptions(
                    mission=request.mission or "Kepler",
                    cadence=request.cadence,
                    max_files=request.max_files,
                    max_candidates=request.max_candidates,
                    min_period=request.min_period,
                    max_period=request.max_period,
                    use_catalog_period_hint=request.use_catalog_period_hint,
                    require_trained_model=True,
                ),
            )
        except (RuntimeError, LookupError, ValueError, OSError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        cache.save(result)
        return result.to_dict()

    if request.time is None:
        demo = cache.load(request.target)
        if demo is not None:
            return demo.to_dict()
        raise HTTPException(
            status_code=404,
            detail="Unknown demo target. Set use_archive=true to fetch a real MAST target.",
        )
    else:
        time, flux = request.time, request.flux
        source = "request payload"

    pipeline = TransitPipeline(
        PipelineConfig(
            max_candidates=request.max_candidates,
            min_period=request.min_period,
            max_period=request.max_period,
        ),
        scorer=load_candidate_scorer(),
    )
    try:
        result = pipeline.analyze(
            request.target,
            time,
            flux,
            mission=request.mission or "Unknown",
            source=source,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    cache.save(result)
    return result.to_dict()


@app.get("/analyze/stream")
def analyze_stream(
    target: str,
    mission: str = "Kepler",
    max_files: int = 4,
    max_candidates: int = 3,
    min_period: float = 0.5,
    max_period: float = 30.0,
    use_catalog_period_hint: bool = True,
) -> StreamingResponse:
    """Same archive analysis as POST /analyze, streamed as Server-Sent Events.

    The work is blocking and can take a minute, so it runs on a worker thread
    while stage updates are pushed to the client as they actually happen.
    """
    events: queue.Queue[dict[str, Any] | None] = queue.Queue()

    def report(stage: str, detail: str = "") -> None:
        events.put({"type": "progress", "stage": stage, "detail": detail})

    def run() -> None:
        try:
            result = analyze_archive_target(
                target,
                ArchiveAnalysisOptions(
                    mission=mission,
                    max_files=max_files,
                    max_candidates=max_candidates,
                    min_period=min_period,
                    max_period=max_period,
                    use_catalog_period_hint=use_catalog_period_hint,
                    require_trained_model=True,
                ),
                progress=report,
            )
            cache.save(result)
            events.put({"type": "result", "result": result.to_dict()})
        except Exception as exc:  # surfaced to the client as an error event
            events.put({"type": "error", "message": str(exc)})
        finally:
            events.put(None)

    threading.Thread(target=run, daemon=True).start()

    def stream() -> Iterator[str]:
        while True:
            event = events.get()
            if event is None:
                break
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
