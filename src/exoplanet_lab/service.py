from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .archive import fetch_light_curve
from .catalog import ResolvedTarget, resolve_target_identifier
from .models import AnalysisResult, StellarProfile
from .pipeline import PipelineConfig, ProgressHook, TransitPipeline
from .scoring import load_candidate_scorer


@dataclass(slots=True)
class ArchiveAnalysisOptions:
    mission: str = "Kepler"
    cadence: str = "long"
    max_files: int | None = 4
    max_candidates: int = 3
    min_period: float = 0.5
    max_period: float = 30.0
    require_trained_model: bool = True
    use_catalog_period_hint: bool = True


def analyze_archive_target(
    target: str,
    options: ArchiveAnalysisOptions | None = None,
    progress: ProgressHook | None = None,
) -> AnalysisResult:
    """Resolve a target, download its MAST light curve, and score BLS candidates."""
    options = options or ArchiveAnalysisOptions()

    def report(stage: str, detail: str = "") -> None:
        if progress is not None:
            progress(stage, detail)

    report("resolve", f"Looking up {target} in the NASA KOI catalog")
    resolved: ResolvedTarget = resolve_target_identifier(target)
    report(
        "download",
        f"Fetching up to {options.max_files} light-curve product(s) for "
        f"{resolved.mast_target} from MAST",
    )
    light_curve = fetch_light_curve(
        resolved.mast_target,
        options.mission,
        cadence=options.cadence,
        max_files=options.max_files,
    )
    scorer = load_candidate_scorer(require_trained=options.require_trained_model)
    search_min_period = options.min_period
    search_max_period = options.max_period
    if options.use_catalog_period_hint and resolved.catalog_period_days:
        # A KOI identifies a known signal, so use its catalog period only to
        # make the confirmation path responsive. KIC/object-name discovery
        # still searches the full configured range.
        period_hint = resolved.catalog_period_days
        search_min_period = max(search_min_period, period_hint * 0.9)
        search_max_period = min(search_max_period, period_hint * 1.1)
        if search_max_period <= search_min_period:
            search_min_period = period_hint * 0.5
            search_max_period = period_hint * 1.5
    pipeline = TransitPipeline(
        PipelineConfig(
            max_candidates=options.max_candidates,
            min_period=search_min_period,
            max_period=search_max_period,
            minimum_snr=5.0,
            period_hint=(
                resolved.catalog_period_days
                if options.use_catalog_period_hint
                else None
            ),
        ),
        scorer=scorer,
    )
    result = pipeline.analyze(
        resolved.kepoi_name or target,
        light_curve.time,
        light_curve.flux,
        mission=light_curve.mission,
        source=(
            f"{light_curve.product_count} official PDCSAP light-curve product(s) "
            f"from MAST via Lightkurve; host query {resolved.mast_target}"
        ),
        star=StellarProfile(
            radius_solar=resolved.stellar_radius_solar,
            mass_solar=resolved.stellar_mass_solar,
            teff_k=resolved.stellar_teff_k,
        ),
        target_metadata=resolved.to_dict(),
        progress=progress,
    )
    result.notes.append(
        "KOI names identify signals; NASA kepid/KIC identifies the host star used for the MAST query."
    )
    if options.use_catalog_period_hint and resolved.catalog_period_days:
        result.notes.append(
            f"The KOI catalog period ({resolved.catalog_period_days:.6f} days) narrowed the confirmation search window; omit the hint for blind discovery."
        )
    return result
