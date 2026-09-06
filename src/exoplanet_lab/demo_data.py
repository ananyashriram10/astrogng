from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import physics
from .features import fold_and_bin, make_global_local_views
from .models import AnalysisResult, Candidate, LightCurveSeries, StellarProfile
from .pipeline import flag_alias_candidates
from .search import bls_periodogram


@dataclass(frozen=True, slots=True)
class DemoPlanet:
    label: str
    period: float
    duration_hours: float
    depth_ppm: float
    confidence: float


@dataclass(frozen=True, slots=True)
class DemoTarget:
    name: str
    mission: str
    seed: int
    planets: tuple[DemoPlanet, ...]
    false_positive: bool = False
    # Published stellar parameters for the real system each demo is shaped after,
    # so derived sizes and distances are physically sensible even offline.
    radius_solar: float = 1.0
    mass_solar: float = 1.0
    teff_k: float = 5800.0


DEMO_TARGETS: tuple[DemoTarget, ...] = (
    DemoTarget(
        name="Kepler-90",
        mission="Kepler",
        seed=90,
        planets=(
            DemoPlanet("Kepler-90 b", 7.008, 3.1, 420.0, 0.96),
            DemoPlanet("Kepler-90 c", 8.719, 3.7, 610.0, 0.94),
            DemoPlanet("Kepler-90 i", 14.449, 2.8, 310.0, 0.91),
        ),
        radius_solar=1.2,
        mass_solar=1.2,
        teff_k=6080.0,
    ),
    DemoTarget(
        name="TRAPPIST-1",
        mission="K2 / Spitzer-inspired demo",
        seed=1,
        planets=(
            DemoPlanet("TRAPPIST-1 b", 1.511, 0.61, 7_200.0, 0.98),
            DemoPlanet("TRAPPIST-1 c", 2.422, 0.69, 6_800.0, 0.97),
            DemoPlanet("TRAPPIST-1 d", 4.050, 0.82, 3_700.0, 0.93),
        ),
        radius_solar=0.1192,
        mass_solar=0.0898,
        teff_k=2566.0,
    ),
    DemoTarget(
        name="Kepler-10",
        mission="Kepler",
        seed=10,
        planets=(DemoPlanet("Kepler-10 b", 0.8375, 1.8, 152.0, 0.95),),
        radius_solar=1.065,
        mass_solar=0.91,
        teff_k=5627.0,
    ),
    DemoTarget(
        name="False-positive example",
        mission="Kepler-style synthetic control",
        seed=404,
        planets=(DemoPlanet("Eclipsing binary signal", 3.214, 5.8, 42_000.0, 0.08),),
        false_positive=True,
    ),
)


def _inject_trapezoid(
    time: np.ndarray,
    flux: np.ndarray,
    *,
    period: float,
    duration_days: float,
    depth: float,
    epoch: float,
    secondary_ratio: float = 0.0,
) -> None:
    phase_days = ((time - epoch + period / 2) % period) - period / 2
    distance = np.abs(phase_days)
    half = duration_days / 2
    flat_half = half * 0.58
    shape = np.clip((half - distance) / max(half - flat_half, 1e-6), 0.0, 1.0)
    flux -= depth * shape
    if secondary_ratio:
        secondary_phase = ((time - epoch - period / 2 + period / 2) % period) - period / 2
        secondary_shape = np.clip(
            (half - np.abs(secondary_phase)) / max(half - flat_half, 1e-6), 0.0, 1.0
        )
        flux -= depth * secondary_ratio * secondary_shape


def build_demo_result(target: DemoTarget) -> AnalysisResult:
    rng = np.random.default_rng(target.seed)
    cadence = 0.04 if target.name != "Kepler-10" else 0.025
    time = np.arange(0.0, 80.0, cadence)
    # Add realistic gaps without making the example nondeterministic.
    keep = ~(((time > 22.0) & (time < 23.4)) | ((time > 57.2) & (time < 58.0)))
    time = time[keep]
    trend = 1.0 + 0.0016 * np.sin(2 * np.pi * time / 17.0) + 0.0006 * np.sin(
        2 * np.pi * time / 4.7
    )
    noise_ppm = 65 if target.name == "Kepler-10" else 115
    detrended = np.ones_like(time) + rng.normal(0.0, noise_ppm / 1_000_000, time.size)

    epochs: list[float] = []
    for index, planet in enumerate(target.planets):
        epoch = 0.31 + index * 0.19
        epochs.append(epoch)
        _inject_trapezoid(
            time,
            detrended,
            period=planet.period,
            duration_days=planet.duration_hours / 24,
            depth=planet.depth_ppm / 1_000_000,
            epoch=epoch,
            secondary_ratio=0.42 if target.false_positive else 0.0,
        )
    raw_flux = detrended * trend

    periodogram = bls_periodogram(time, detrended, min_period=0.3, max_period=20.0)

    candidates: list[Candidate] = []
    for index, (planet, epoch) in enumerate(zip(target.planets, epochs, strict=True), start=1):
        phase, folded = fold_and_bin(time, detrended, planet.period, epoch)
        global_view, local_view = make_global_local_views(
            time, detrended, planet.period, epoch, planet.duration_hours / 24
        )
        event_count = int(np.floor((time[-1] - time[0]) / planet.period)) + 1
        depth_ratio = 0.16 if target.false_positive else 0.035
        radius_earth = physics.planet_radius_earth(planet.depth_ppm, target.radius_solar)
        axis_au = physics.semi_major_axis_au(planet.period, target.mass_solar)
        temp_k = physics.equilibrium_temperature_k(
            target.teff_k, target.radius_solar, axis_au
        )
        candidates.append(
            Candidate(
                candidate_id=planet.label,
                period_days=planet.period,
                epoch_days=epoch,
                duration_hours=planet.duration_hours,
                depth_ppm=planet.depth_ppm,
                snr=round(planet.depth_ppm / noise_ppm * np.sqrt(max(event_count, 1)), 2),
                bls_power=round(12.0 + planet.confidence * 19.0, 3),
                confidence=planet.confidence,
                disposition=("likely false positive" if target.false_positive else "planet-like"),
                num_transits_observed=event_count,
                odd_even_depth_diff_ppm=round(planet.depth_ppm * depth_ratio, 2),
                secondary_eclipse_depth_ppm=(
                    round(planet.depth_ppm * 0.42, 2) if target.false_positive else 0.0
                ),
                transit_shape_symmetry=0.88 if target.false_positive else 0.97,
                phase=phase,
                folded_flux=folded,
                global_view=global_view,
                local_view=local_view,
                planet_radius_earth=(
                    round(radius_earth, 3) if radius_earth is not None else None
                ),
                semi_major_axis_au=round(axis_au, 4) if axis_au is not None else None,
                equilibrium_temp_k=round(temp_k, 1) if temp_k is not None else None,
                size_class=physics.size_class(radius_earth),
            )
        )

    flag_alias_candidates(candidates)

    return AnalysisResult(
        target=target.name,
        mission=target.mission,
        source="deterministic synthetic demo; periods inspired by published systems",
        status="cached demo",
        is_multi_planet=len(candidates) > 1,
        candidates=candidates,
        raw_light_curve=LightCurveSeries(
            time=time.round(5).tolist(), flux=raw_flux.round(8).tolist()
        ),
        detrended_light_curve=LightCurveSeries(
            time=time.round(5).tolist(), flux=detrended.round(8).tolist()
        ),
        notes=[
            "The plotted points are synthetic and deterministic; they are not downloaded archive photometry.",
            "Only three signals are shown in multi-planet demos to keep the interface readable.",
            "Confidence values demonstrate the planned UI and must not be interpreted as validated scientific probabilities.",
        ],
        classifier="demo-fixture",
        periodogram=periodogram,
        star=StellarProfile(
            radius_solar=target.radius_solar,
            mass_solar=target.mass_solar,
            teff_k=target.teff_k,
        ),
    )


def find_demo_target(name: str) -> DemoTarget | None:
    wanted = name.strip().casefold().replace("b", "") if name.strip().casefold() == "kepler-10b" else name.strip().casefold()
    for target in DEMO_TARGETS:
        if target.name.casefold() == wanted:
            return target
    return None
