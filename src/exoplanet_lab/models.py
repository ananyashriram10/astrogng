from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class LightCurveSeries:
    time: list[float]
    flux: list[float]


@dataclass(slots=True)
class Periodogram:
    period: list[float]
    power: list[float]


@dataclass(slots=True)
class StellarProfile:
    """What we know about the host star, which sets the scale for everything else."""

    radius_solar: float | None = None
    mass_solar: float | None = None
    teff_k: float | None = None


@dataclass(slots=True)
class Candidate:
    candidate_id: str
    period_days: float
    epoch_days: float
    duration_hours: float
    depth_ppm: float
    snr: float
    bls_power: float
    confidence: float
    disposition: str
    num_transits_observed: int
    odd_even_depth_diff_ppm: float
    secondary_eclipse_depth_ppm: float
    transit_shape_symmetry: float
    phase: list[float] = field(default_factory=list)
    folded_flux: list[float] = field(default_factory=list)
    gbt_proba: float | None = None
    cnn_proba: float | None = None
    # The exact arrays handed to the CNN: a full-orbit view and a zoom on the dip.
    global_view: list[float] = field(default_factory=list)
    local_view: list[float] = field(default_factory=list)
    # Derived physical properties; None whenever the stellar inputs are unknown.
    planet_radius_earth: float | None = None
    semi_major_axis_au: float | None = None
    equilibrium_temp_k: float | None = None
    size_class: str | None = None
    # Set when this signal looks like a repeat or harmonic of an earlier one.
    alias_of: str | None = None
    alias_reason: str | None = None


@dataclass(slots=True)
class AnalysisResult:
    target: str
    mission: str
    source: str
    status: str
    is_multi_planet: bool
    candidates: list[Candidate]
    raw_light_curve: LightCurveSeries
    detrended_light_curve: LightCurveSeries
    notes: list[str] = field(default_factory=list)
    classifier: str = ""
    target_metadata: dict[str, Any] = field(default_factory=dict)
    periodogram: Periodogram | None = None
    star: StellarProfile | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AnalysisResult":
        periodogram = payload.get("periodogram")
        star = payload.get("star")
        return cls(
            target=payload["target"],
            mission=payload["mission"],
            source=payload["source"],
            status=payload["status"],
            is_multi_planet=payload["is_multi_planet"],
            candidates=[Candidate(**candidate) for candidate in payload["candidates"]],
            raw_light_curve=LightCurveSeries(**payload["raw_light_curve"]),
            detrended_light_curve=LightCurveSeries(**payload["detrended_light_curve"]),
            notes=payload.get("notes", []),
            classifier=payload.get("classifier", ""),
            target_metadata=payload.get("target_metadata", {}),
            periodogram=Periodogram(**periodogram) if periodogram else None,
            star=StellarProfile(**star) if star else None,
        )
