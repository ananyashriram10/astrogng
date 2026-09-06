from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .models import Periodogram
from .preprocessing import robust_sigma


@dataclass(slots=True)
class TransitPeak:
    period: float
    epoch: float
    duration: float
    power: float


def bls_periodogram(
    time: NDArray[np.float64],
    flux: NDArray[np.float64],
    *,
    min_period: float = 0.5,
    max_period: float | None = None,
    period_steps: int = 1200,
    max_points: int = 600,
) -> Periodogram | None:
    """Full BLS period-vs-power grid, for visualizing the search rather than just its winner.

    Independent of box_least_squares_search's own peak-finding (which may use
    autopower or a period-hint-narrowed grid); this always sweeps the plain,
    uniform range so the periodogram shown to a user reflects the whole space
    that was searched.
    """
    baseline = float(time[-1] - time[0])
    upper = min(max_period or baseline / 2, baseline / 2)
    if upper <= min_period:
        return None

    try:
        from astropy.timeseries import BoxLeastSquares
    except ImportError:
        return None

    minimum_duration = min(0.04, min_period * 0.2)
    maximum_duration = min(0.5, upper * 0.08, min_period * 0.8)
    maximum_duration = max(maximum_duration, minimum_duration * 1.25)
    durations = np.geomspace(minimum_duration, maximum_duration, 8)
    periods = np.linspace(min_period, upper, period_steps)
    model = BoxLeastSquares(time, flux)
    result = model.power(periods, durations)
    power = np.asarray(result.power, dtype=float)

    if power.size > max_points:
        # Downsample by taking the max power within each bucket so the peak
        # survives thinning instead of being averaged away.
        edges = np.linspace(0, power.size, max_points + 1).astype(int)
        thinned_period = np.empty(max_points)
        thinned_power = np.empty(max_points)
        for i in range(max_points):
            start, stop = edges[i], max(edges[i + 1], edges[i] + 1)
            segment = power[start:stop]
            best = int(np.argmax(segment))
            thinned_power[i] = segment[best]
            thinned_period[i] = periods[start:stop][best]
        periods_out, power_out = thinned_period, thinned_power
    else:
        periods_out, power_out = periods, power

    return Periodogram(
        period=periods_out.round(5).tolist(), power=power_out.round(6).tolist()
    )


def transit_mask(
    time: NDArray[np.float64], period: float, duration: float, epoch: float
) -> NDArray[np.bool_]:
    offset = ((time - epoch + 0.5 * period) % period) - 0.5 * period
    return np.abs(offset) <= duration / 2


def _numpy_box_search(
    time: NDArray[np.float64],
    flux: NDArray[np.float64],
    *,
    min_period: float,
    max_period: float,
    period_steps: int,
    duration_fractions: tuple[float, ...],
) -> TransitPeak:
    """Small dependency-free BLS approximation used when Astropy is absent."""
    periods = np.linspace(min_period, max_period, period_steps)
    bin_count = 160
    global_scatter = max(robust_sigma(flux), 1e-9)
    best = TransitPeak(period=min_period, epoch=float(time[0]), duration=0.1, power=-np.inf)

    for period in periods:
        phase = ((time - time[0]) % period) / period
        bins = np.minimum((phase * bin_count).astype(int), bin_count - 1)
        sums = np.bincount(bins, weights=flux, minlength=bin_count)
        counts = np.bincount(bins, minlength=bin_count).astype(float)
        doubled_sums = np.concatenate((sums, sums))
        doubled_counts = np.concatenate((counts, counts))
        cumulative_sum = np.concatenate(([0.0], np.cumsum(doubled_sums)))
        cumulative_count = np.concatenate(([0.0], np.cumsum(doubled_counts)))

        for fraction in duration_fractions:
            width = int(np.clip(round(fraction * bin_count), 1, bin_count // 4))
            window_sum = cumulative_sum[width : width + bin_count] - cumulative_sum[:bin_count]
            window_count = (
                cumulative_count[width : width + bin_count] - cumulative_count[:bin_count]
            )
            means = np.divide(
                window_sum,
                window_count,
                out=np.full(bin_count, np.inf),
                where=window_count > 0,
            )
            start_bin = int(np.argmin(means))
            depth = max(0.0, 1.0 - float(means[start_bin]))
            power = depth * np.sqrt(max(window_count[start_bin], 1.0)) / global_scatter
            if power > best.power:
                center_phase = ((start_bin + width / 2) % bin_count) / bin_count
                best = TransitPeak(
                    period=float(period),
                    epoch=float(time[0] + center_phase * period),
                    duration=float(max(period * fraction, np.median(np.diff(time)) * 2)),
                    power=float(power),
                )
    return best


def box_least_squares_search(
    time: NDArray[np.float64],
    flux: NDArray[np.float64],
    *,
    min_period: float = 0.5,
    max_period: float | None = None,
    period_steps: int = 700,
    period_hint: float | None = None,
) -> TransitPeak:
    baseline = float(time[-1] - time[0])
    upper = min(max_period or baseline / 2, baseline / 2)
    if upper <= min_period:
        raise ValueError("light-curve baseline is too short for the requested period range")

    try:
        from astropy.timeseries import BoxLeastSquares
    except ImportError:
        return _numpy_box_search(
            time,
            flux,
            min_period=min_period,
            max_period=upper,
            period_steps=period_steps,
            duration_fractions=(0.015, 0.025, 0.04, 0.065),
        )

    minimum_duration = min(0.04, min_period * 0.2)
    maximum_duration = min(0.5, upper * 0.08, min_period * 0.8)
    maximum_duration = max(maximum_duration, minimum_duration * 1.25)
    durations = np.geomspace(minimum_duration, maximum_duration, 8)
    model = BoxLeastSquares(time, flux)
    # Keep archive analysis responsive while still sampling enough frequencies
    # to resolve repeated events across a multi-quarter baseline.
    if period_hint is not None and min_period <= period_hint <= upper:
        # Include the catalog ephemeris exactly in the confirmation search.
        # The surrounding grid still permits a small measurement offset.
        local_min = max(min_period, period_hint * 0.98)
        local_max = min(upper, period_hint * 1.02)
        periods = np.unique(
            np.concatenate(
                [
                    np.linspace(min_period, upper, max(100, period_steps // 4)),
                    np.linspace(local_min, local_max, 401),
                    np.asarray([period_hint]),
                ]
            )
        )
        result = model.power(periods, durations)
    else:
        result = model.autopower(
            durations,
            minimum_period=min_period,
            maximum_period=upper,
            minimum_n_transit=2,
            frequency_factor=3.0,
        )
    index = int(np.nanargmax(result.power))
    return TransitPeak(
        period=float(result.period[index]),
        epoch=float(result.transit_time[index]),
        duration=float(result.duration[index]),
        power=float(result.power[index]),
    )


def iterative_box_search(
    time: NDArray[np.float64],
    flux: NDArray[np.float64],
    *,
    n_candidates: int = 3,
    min_period: float = 0.5,
    max_period: float | None = None,
    period_steps: int = 700,
    period_hint: float | None = None,
) -> tuple[list[TransitPeak], Periodogram | None]:
    residual = np.asarray(flux, dtype=float).copy()
    periodogram = bls_periodogram(
        time,
        residual,
        min_period=min_period,
        max_period=max_period,
        period_steps=max(period_steps, 300),
    )
    peaks: list[TransitPeak] = []
    for _ in range(n_candidates):
        peak = box_least_squares_search(
            time,
            residual,
            min_period=min_period,
            max_period=max_period,
            period_steps=period_steps,
            period_hint=period_hint if not peaks else None,
        )
        peaks.append(peak)
        mask = transit_mask(time, peak.period, peak.duration, peak.epoch)
        residual[mask] = float(np.nanmedian(residual[~mask])) if np.any(~mask) else 1.0
    return peaks, periodogram
