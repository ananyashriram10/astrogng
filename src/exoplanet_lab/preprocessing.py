from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


def _rolling_median(values: NDArray[np.float64], window: int) -> NDArray[np.float64]:
    """Memory-conscious rolling median with reflected edges."""
    if window <= 1 or values.size < 3:
        return np.full_like(values, np.nanmedian(values))
    window = min(window, values.size if values.size % 2 else values.size - 1)
    window = max(3, window | 1)
    pad = window // 2
    padded = np.pad(values, pad, mode="reflect")
    result = np.empty_like(values)
    # Chunking prevents a long Kepler series from materializing a huge window matrix.
    chunk_size = max(256, 2_000_000 // window)
    for start in range(0, values.size, chunk_size):
        stop = min(values.size, start + chunk_size)
        view = np.lib.stride_tricks.sliding_window_view(
            padded[start : stop + window - 1], window
        )
        result[start:stop] = np.nanmedian(view, axis=1)
    return result


def robust_sigma(values: NDArray[np.float64]) -> float:
    median = float(np.nanmedian(values))
    mad = float(np.nanmedian(np.abs(values - median)))
    return 1.4826 * mad if mad > 0 else float(np.nanstd(values))


def preprocess_light_curve(
    time: ArrayLike,
    flux: ArrayLike,
    *,
    quality: ArrayLike | None = None,
    window_length: int = 401,
    sigma_clip: float = 6.0,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Clean, detrend, clip, and median-normalize a light curve.

    The output remains suitable for transit search: clipping is intentionally
    conservative so genuine downward excursions are retained.
    """
    times = np.asarray(time, dtype=float).reshape(-1)
    values = np.asarray(flux, dtype=float).reshape(-1)
    if times.size != values.size:
        raise ValueError("time and flux must contain the same number of points")
    if times.size < 20:
        raise ValueError("at least 20 light-curve points are required")

    valid = np.isfinite(times) & np.isfinite(values)
    if quality is not None:
        flags = np.asarray(quality).reshape(-1)
        if flags.size != times.size:
            raise ValueError("quality must match the time and flux lengths")
        valid &= flags == 0
    times, values = times[valid], values[valid]
    order = np.argsort(times)
    times, values = times[order], values[order]
    if times.size < 20:
        raise ValueError("too few valid points remain after quality filtering")

    scale = float(np.nanmedian(values))
    if not np.isfinite(scale) or scale == 0:
        raise ValueError("flux median must be finite and non-zero")
    normalized = values / scale
    trend = _rolling_median(normalized, window_length)
    trend[~np.isfinite(trend) | (trend == 0)] = 1.0
    flattened = normalized / trend

    scatter = robust_sigma(flattened)
    center = float(np.nanmedian(flattened))
    if scatter > 0:
        # Upward cosmic-ray events are clipped more aggressively than dips.
        upper_bad = flattened >= center + sigma_clip * scatter
        lower_bad = flattened <= center - (sigma_clip * 1.75) * scatter
        # A single isolated low cadence is far more likely to be a glitch than
        # astrophysics; a real transit or eclipse -- however deep -- persists
        # across multiple consecutive cadences. Only drop a low outlier if it
        # has no low neighbor on either side, so a very deep eclipsing-binary
        # dip (tens of percent) survives to be measured and correctly flagged
        # as a false positive, instead of being clipped down to just its
        # shallow ingress/egress shoulders and misread as a modest, plausible
        # transit.
        has_low_neighbor = np.zeros_like(lower_bad)
        has_low_neighbor[1:] |= lower_bad[:-1]
        has_low_neighbor[:-1] |= lower_bad[1:]
        isolated_low = lower_bad & ~has_low_neighbor
        keep = ~(upper_bad | isolated_low)
        times, flattened = times[keep], flattened[keep]

    flattened /= float(np.nanmedian(flattened))
    return times, flattened

