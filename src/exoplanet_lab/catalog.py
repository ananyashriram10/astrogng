from __future__ import annotations

import csv
import io
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KOI_CACHE = PROJECT_ROOT / "data" / "koi_cumulative_training.csv"
TAP_ENDPOINT = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"


@dataclass(slots=True)
class ResolvedTarget:
    requested_name: str
    mast_target: str
    identifier_type: str
    kepid: int | None = None
    kepoi_name: str | None = None
    kepler_name: str | None = None
    stellar_radius_solar: float | None = None
    stellar_mass_solar: float | None = None
    stellar_teff_k: float | None = None
    catalog_disposition: str | None = None
    catalog_period_days: float | None = None
    catalog_duration_hours: float | None = None
    catalog_depth_ppm: float | None = None

    def to_dict(self) -> dict[str, str | int | float | None]:
        return asdict(self)


def normalize_koi_name(value: str) -> str | None:
    compact = re.sub(r"[\s_-]+", "", value.strip().upper())
    match = re.fullmatch(r"(?:KOI|K)?(\d{1,5})\.(\d{2})", compact)
    if not match:
        return None
    return f"K{int(match.group(1)):05d}.{match.group(2)}"


def parse_kic_id(value: str) -> int | None:
    compact = re.sub(r"[\s_-]+", "", value.strip().upper())
    match = re.fullmatch(r"(?:KIC)?(\d{6,9})", compact)
    return int(match.group(1)) if match else None


def _optional_float(value: str | None) -> float | None:
    try:
        parsed = float(value or "")
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _record_to_target(requested: str, record: dict[str, str]) -> ResolvedTarget:
    kepid = int(float(record["kepid"]))
    return ResolvedTarget(
        requested_name=requested,
        mast_target=f"KIC {kepid}",
        identifier_type="KOI" if normalize_koi_name(requested) else "KIC",
        kepid=kepid,
        kepoi_name=record.get("kepoi_name") or None,
        kepler_name=record.get("kepler_name") or None,
        stellar_radius_solar=_optional_float(record.get("koi_srad")),
        stellar_mass_solar=_optional_float(record.get("koi_smass")),
        stellar_teff_k=_optional_float(record.get("koi_steff")),
        catalog_disposition=record.get("koi_disposition") or None,
        catalog_period_days=_optional_float(record.get("koi_period")),
        catalog_duration_hours=_optional_float(record.get("koi_duration")),
        catalog_depth_ppm=_optional_float(record.get("koi_depth")),
    )


def _find_cached_record(
    requested: str, koi_name: str | None, kic_id: int | None, cache_path: Path
) -> dict[str, str] | None:
    if not cache_path.exists():
        return None
    with cache_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if koi_name and row.get("kepoi_name", "").upper() == koi_name:
                return row
            if kic_id and row.get("kepid") and int(float(row["kepid"])) == kic_id:
                return row
    return None


def _fetch_catalog_record(koi_name: str | None, kic_id: int | None) -> dict[str, str] | None:
    columns = (
        "kepid,kepoi_name,kepler_name,koi_disposition,koi_period,koi_duration,"
        "koi_depth,koi_srad,koi_smass,koi_steff"
    )
    if koi_name:
        where = f"kepoi_name='{koi_name}'"
    elif kic_id:
        where = f"kepid={kic_id}"
    else:
        return None
    query = f"select top 1 {columns} from cumulative where {where}"
    url = f"{TAP_ENDPOINT}?{urlencode({'query': query, 'format': 'csv'})}"
    with urlopen(url, timeout=45) as response:  # noqa: S310 - fixed NASA HTTPS endpoint
        text = response.read().decode("utf-8-sig")
    return next(csv.DictReader(io.StringIO(text)), None)


def resolve_target_identifier(
    requested: str,
    *,
    cache_path: Path = DEFAULT_KOI_CACHE,
    allow_network: bool = True,
) -> ResolvedTarget:
    """Resolve a KOI or KIC identifier to the host identifier accepted by MAST.

    A KOI names a signal. ``kepid`` identifies its host star and is the bridge
    to Lightkurve's KIC lookup. Ordinary object names are passed through for
    Lightkurve/Simbad resolution and do not receive KOI metadata.
    """
    requested = requested.strip()
    if not requested:
        raise ValueError("target name cannot be empty")
    koi_name = normalize_koi_name(requested)
    kic_id = None if koi_name else parse_kic_id(requested)
    if not koi_name and not kic_id:
        return ResolvedTarget(
            requested_name=requested,
            mast_target=requested,
            identifier_type="object name",
        )

    record = _find_cached_record(requested, koi_name, kic_id, cache_path)
    if record is None and allow_network:
        record = _fetch_catalog_record(koi_name, kic_id)
    if record is None:
        kind = "KOI" if koi_name else "KIC"
        raise LookupError(f"{kind} identifier {requested!r} was not found in the NASA KOI table")
    return _record_to_target(requested, record)

