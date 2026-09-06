from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike

from . import physics
from .features import extract_candidate_features
from .models import AnalysisResult, Candidate, LightCurveSeries, StellarProfile
from .preprocessing import preprocess_light_curve
from .scoring import CandidateScorer, HeuristicCandidateScorer
from .search import iterative_box_search


ProgressHook = Callable[[str, str], None]

# Harmonic ratios that mean "this is the same signal, counted wrong".
_ALIAS_HARMONICS: tuple[tuple[float, str], ...] = (
    (2.0, "twice the period"),
    (3.0, "three times the period"),
    (0.5, "half the period"),
    (1 / 3, "a third of the period"),
)
# A straight re-detection is the dominant failure mode and its period can drift
# a fair way on weak, few-transit signals, so it gets a looser window than the
# harmonics — where a near-miss is more likely to be a genuine resonant pair.
_REPEAT_TOLERANCE = 0.08
_HARMONIC_TOLERANCE = 0.02
_DEPTH_AGREEMENT = 2.0
# A period match this tight (four-plus significant figures) is on its own
# already overwhelming evidence of a re-detection: distinct real planets do
# not share an orbital period to this precision by chance. Depth is not
# required to agree here — a corrupted residual mask from the first
# iteration routinely throws off the second pass's depth fit even though
# it has locked onto the exact same transit.
_EXACT_PERIOD_TOLERANCE = 0.01


def _depths_agree(a: float, b: float) -> bool:
    if a <= 0 or b <= 0:
        return False
    ratio = a / b if a >= b else b / a
    return ratio <= _DEPTH_AGREEMENT


def flag_alias_candidates(candidates: list[Candidate]) -> None:
    """Mark candidates that repeat an earlier signal's period or a harmonic of it.

    The iterative search masks each detection before searching again, but on
    long-period targets with few transits the mask rarely removes the signal
    cleanly, so the same planet gets 'found' several times at slightly
    different periods. Labelling that is far more honest than presenting them
    as separate worlds.
    """
    for index, candidate in enumerate(candidates):
        for earlier in candidates[:index]:
            if earlier.alias_of is not None or earlier.period_days <= 0:
                continue
            ratio = candidate.period_days / earlier.period_days
            depths_agree = _depths_agree(candidate.depth_ppm, earlier.depth_ppm)

            if abs(ratio - 1.0) <= _EXACT_PERIOD_TOLERANCE:
                candidate.alias_of = earlier.candidate_id
                candidate.alias_reason = (
                    f"Same period ({candidate.period_days:.4f} d) as {earlier.candidate_id} — "
                    "almost certainly a re-detection of one signal, not a second planet"
                    + ("" if depths_agree else " (the depth fit differs, likely a residual-masking artifact)")
                )
                break

            if abs(ratio - 1.0) <= _REPEAT_TOLERANCE and depths_agree:
                candidate.alias_of = earlier.candidate_id
                candidate.alias_reason = (
                    f"Same period and depth as {earlier.candidate_id} — "
                    "almost certainly a re-detection of one signal, not a second planet"
                )
                break

            for factor, label in _ALIAS_HARMONICS:
                if abs(ratio - factor) / factor <= _HARMONIC_TOLERANCE:
                    candidate.alias_of = earlier.candidate_id
                    candidate.alias_reason = (
                        f"{label.capitalize()} of {earlier.candidate_id} — "
                        "likely a harmonic of the same signal"
                    )
                    break
            if candidate.alias_of is not None:
                break


@dataclass(slots=True)
class PipelineConfig:
    window_length: int = 401
    sigma_clip: float = 6.0
    min_period: float = 0.5
    max_period: float | None = 30.0
    period_steps: int = 700
    max_candidates: int = 3
    minimum_snr: float = 5.0
    period_hint: float | None = None


class TransitPipeline:
    def __init__(
        self,
        config: PipelineConfig | None = None,
        scorer: CandidateScorer | None = None,
    ) -> None:
        self.config = config or PipelineConfig()
        self.scorer = scorer or HeuristicCandidateScorer()

    def analyze(
        self,
        target: str,
        time: ArrayLike,
        flux: ArrayLike,
        *,
        mission: str = "Unknown",
        source: str = "user-provided light curve",
        quality: ArrayLike | None = None,
        stellar_radius_solar: float | None = None,
        star: StellarProfile | None = None,
        target_metadata: dict[str, str | int | float | None] | None = None,
        progress: ProgressHook | None = None,
    ) -> AnalysisResult:
        def report(stage: str, detail: str = "") -> None:
            if progress is not None:
                progress(stage, detail)

        if star is None and stellar_radius_solar is not None:
            star = StellarProfile(radius_solar=stellar_radius_solar)

        report("preprocess", "Cleaning and detrending the light curve")
        raw_time = np.asarray(time, dtype=float).reshape(-1)
        raw_flux = np.asarray(flux, dtype=float).reshape(-1)
        clean_time, clean_flux = preprocess_light_curve(
            raw_time,
            raw_flux,
            quality=quality,
            window_length=self.config.window_length,
            sigma_clip=self.config.sigma_clip,
        )
        report(
            "search",
            f"Box Least Squares sweep over {self.config.min_period:.2f}–"
            f"{self.config.max_period or 0:.2f} day periods",
        )
        peaks, periodogram = iterative_box_search(
            clean_time,
            clean_flux,
            n_candidates=self.config.max_candidates,
            min_period=self.config.min_period,
            max_period=self.config.max_period,
            period_steps=self.config.period_steps,
            period_hint=self.config.period_hint,
        )

        radius_solar = star.radius_solar if star else None
        candidates: list[Candidate] = []
        for index, peak in enumerate(peaks, start=1):
            report("score", f"Scoring candidate {index} of {len(peaks)}")
            features = extract_candidate_features(clean_time, clean_flux, peak)
            features["period_days"] = peak.period
            features["duration_hours"] = peak.duration * 24
            features["stellar_radius_solar"] = (
                radius_solar if radius_solar is not None else float("nan")
            )
            if float(features["snr"]) < self.config.minimum_snr:
                continue
            confidence = self.scorer.predict(features)
            depth_ppm = round(float(features["depth_ppm"]), 2)
            radius_earth = physics.planet_radius_earth(depth_ppm, radius_solar)
            axis_au = physics.semi_major_axis_au(
                peak.period, star.mass_solar if star else None
            )
            temp_k = physics.equilibrium_temperature_k(
                star.teff_k if star else None, radius_solar, axis_au
            )
            gbt_proba = getattr(self.scorer, "last_gbt_proba", None)
            cnn_proba = getattr(self.scorer, "last_cnn_proba", None)
            candidates.append(
                Candidate(
                    candidate_id=f"{target.replace(' ', '-')}-{index}",
                    period_days=round(peak.period, 6),
                    epoch_days=round(peak.epoch, 6),
                    duration_hours=round(peak.duration * 24, 4),
                    depth_ppm=depth_ppm,
                    snr=round(float(features["snr"]), 2),
                    bls_power=round(peak.power, 4),
                    confidence=round(confidence, 4),
                    disposition=(
                        "planet-like"
                        if confidence >= self.scorer.threshold
                        else "likely false positive"
                    ),
                    num_transits_observed=int(features["num_transits_observed"]),
                    odd_even_depth_diff_ppm=round(
                        float(features["odd_even_depth_diff_ppm"]), 2
                    ),
                    secondary_eclipse_depth_ppm=round(
                        float(features["secondary_eclipse_depth_ppm"]), 2
                    ),
                    transit_shape_symmetry=round(
                        float(features["transit_shape_symmetry"]), 4
                    ),
                    phase=list(features["phase"]),
                    folded_flux=list(features["folded_flux"]),
                    gbt_proba=gbt_proba,
                    cnn_proba=cnn_proba,
                    global_view=list(features["global_view"]),
                    local_view=list(features["local_view"]),
                    planet_radius_earth=(
                        round(radius_earth, 3) if radius_earth is not None else None
                    ),
                    semi_major_axis_au=(
                        round(axis_au, 4) if axis_au is not None else None
                    ),
                    equilibrium_temp_k=(round(temp_k, 1) if temp_k is not None else None),
                    size_class=physics.size_class(radius_earth),
                )
            )

        flag_alias_candidates(candidates)

        finite_raw = np.isfinite(raw_time) & np.isfinite(raw_flux)
        return AnalysisResult(
            target=target,
            mission=mission,
            source=source,
            status="complete",
            is_multi_planet=len(candidates) > 1,
            candidates=candidates,
            raw_light_curve=LightCurveSeries(
                time=raw_time[finite_raw].round(7).tolist(),
                flux=raw_flux[finite_raw].round(8).tolist(),
            ),
            detrended_light_curve=LightCurveSeries(
                time=clean_time.round(7).tolist(), flux=clean_flux.round(8).tolist()
            ),
            notes=[
                f"Score produced by {self.scorer.model_name}; it ranks planet-like signals but does not confirm planets.",
                "Catalog and locally extracted features share units, but their measurement pipelines are not identical; validate before scientific use.",
            ],
            classifier=self.scorer.model_name,
            target_metadata=target_metadata or {},
            periodogram=periodogram,
            star=star,
        )
