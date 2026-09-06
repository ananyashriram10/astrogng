from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DOWNLOAD_DIR = PROJECT_ROOT / "data" / "lightkurve"


@dataclass(slots=True)
class ArchiveLightCurve:
    time: np.ndarray
    flux: np.ndarray
    target: str
    mission: str
    product_count: int
    cadence: str


def fetch_light_curve(
    target: str,
    mission: str | None = "Kepler",
    *,
    author: str | None = None,
    cadence: str = "long",
    max_files: int | None = 4,
    download_dir: Path | str = DEFAULT_DOWNLOAD_DIR,
) -> ArchiveLightCurve:
    """Fetch, normalize, and stitch PDCSAP light curves from MAST via Lightkurve."""
    try:
        import lightkurve as lk
    except ImportError as exc:
        raise RuntimeError(
            "Live archive access requires the science extras: pip install -e .[science]"
        ) from exc

    resolved_author = author
    if resolved_author is None and mission:
        resolved_author = "SPOC" if mission.upper() == "TESS" else mission
    kwargs: dict[str, Any] = {"exptime": cadence}
    if mission:
        kwargs["mission"] = mission
    if resolved_author:
        kwargs["author"] = resolved_author

    search = lk.search_lightcurve(target, **kwargs)
    if len(search) == 0:
        raise LookupError(
            f"No {mission or 'Kepler/TESS'} {cadence}-cadence light curves were found for {target!r}"
        )
    selected = search[:max_files] if max_files is not None else search
    directory = Path(download_dir)
    directory.mkdir(parents=True, exist_ok=True)
    try:
        collection = selected.download_all(
            quality_bitmask="default",
            download_dir=str(directory),
        )
    except Exception as exc:
        # Lightkurve's download_all has no partial-failure tolerance: if any
        # one product fails (network blip, incomplete transfer, corrupt
        # FITS), it raises immediately and discards whatever already
        # succeeded. Surface that as a clear, retryable error rather than a
        # raw traceback.
        raise RuntimeError(
            f"Downloading light-curve data for {target!r} failed partway through "
            f"({exc}). This is usually a transient MAST/network issue — try again, "
            "or lower the number of products to stitch."
        ) from exc
    if collection is None or len(collection) == 0:
        raise LookupError(f"MAST returned no downloadable light-curve files for {target!r}")

    # Lightkurve reads official Kepler/TESS products using PDCSAP_FLUX by default.
    stitched = collection.stitch(corrector_func=lambda curve: curve.normalize()).remove_nans()
    return ArchiveLightCurve(
        time=np.asarray(stitched.time.value, dtype=float),
        flux=np.asarray(stitched.flux.value, dtype=float),
        target=target,
        mission=mission or "Kepler/TESS",
        product_count=len(collection),
        cadence=cadence,
    )

