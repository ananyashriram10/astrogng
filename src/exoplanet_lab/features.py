from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from .preprocessing import robust_sigma
from .search import TransitPeak, transit_mask


def fold_and_bin(
    time: NDArray[np.float64],
    flux: NDArray[np.float64],
    period: float,
    epoch: float,
    *,
    bins: int = 160,
) -> tuple[list[float], list[float]]:
    phase = ((time - epoch + 0.5 * period) % period) / period - 0.5
    edges = np.linspace(-0.5, 0.5, bins + 1)
    indices = np.digitize(phase, edges) - 1
    centers = (edges[:-1] + edges[1:]) / 2
    binned = np.full(bins, np.nan)
    for index in range(bins):
        values = flux[indices == index]
        if values.size:
            binned[index] = np.nanmedian(values)
    valid = np.isfinite(binned)
    return centers[valid].round(7).tolist(), binned[valid].round(8).tolist()


def make_global_local_views(
    time: NDArray[np.float64],
    flux: NDArray[np.float64],
    period: float,
    epoch: float,
    duration: float,
    *,
    global_bins: int = 201,
    local_bins: int = 61,
) -> tuple[list[float], list[float]]:
    """Bins a phase-folded light curve into fixed-length global/local views for the CNN.

    Mirrors the AstroNet-style representation the astrogng CNN was trained on:
    a global view of the full phase range, and a local view zoomed to +/- 2x
    the transit duration. Empty bins are filled by linear interpolation so the
    output is always exactly (global_bins,) and (local_bins,) long.
    """
    phase = ((time - epoch + 0.5 * period) % period) / period - 0.5
    order = np.argsort(phase)
    phase_sorted = phase[order]
    flux_sorted = flux[order]

    def _bin(edges: NDArray[np.float64], bins: int) -> NDArray[np.float64]:
        view = np.full(bins, np.nan)
        for i in range(bins):
            mask = (phase_sorted >= edges[i]) & (phase_sorted < edges[i + 1])
            if mask.any():
                view[i] = np.nanmedian(flux_sorted[mask])
        nan_mask = np.isnan(view)
        if nan_mask.any() and not nan_mask.all():
            view[nan_mask] = np.interp(
                np.flatnonzero(nan_mask), np.flatnonzero(~nan_mask), view[~nan_mask]
            )
        elif nan_mask.all():
            view[:] = 1.0
        return view

    global_edges = np.linspace(-0.5, 0.5, global_bins + 1)
    global_view = _bin(global_edges, global_bins)

    local_half_width = max(2 * (duration / period), 1e-4)
    local_edges = np.linspace(-local_half_width, local_half_width, local_bins + 1)
    local_view = _bin(local_edges, local_bins)

    return global_view.round(8).tolist(), local_view.round(8).tolist()


def extract_candidate_features(
    time: NDArray[np.float64], flux: NDArray[np.float64], peak: TransitPeak
) -> dict[str, float | int | list[float]]:
    primary = transit_mask(time, peak.period, peak.duration, peak.epoch)
    outside = ~transit_mask(time, peak.period, peak.duration * 2.5, peak.epoch)
    baseline = float(np.nanmedian(flux[outside])) if np.any(outside) else 1.0
    primary_depth = max(0.0, baseline - float(np.nanmedian(flux[primary]))) if np.any(primary) else 0.0
    scatter = max(robust_sigma(flux[outside]), 1e-9) if np.any(outside) else 1e-9
    snr = primary_depth / scatter * np.sqrt(max(int(primary.sum()), 1))

    transit_number = np.rint((time - peak.epoch) / peak.period).astype(int)
    odd = primary & (np.abs(transit_number) % 2 == 1)
    even = primary & (np.abs(transit_number) % 2 == 0)
    odd_depth = baseline - float(np.nanmedian(flux[odd])) if np.any(odd) else primary_depth
    even_depth = baseline - float(np.nanmedian(flux[even])) if np.any(even) else primary_depth

    secondary_epoch = peak.epoch + peak.period / 2
    secondary = transit_mask(time, peak.period, peak.duration, secondary_epoch)
    secondary_depth = max(
        0.0, baseline - float(np.nanmedian(flux[secondary])) if np.any(secondary) else 0.0
    )

    offset = ((time - peak.epoch + 0.5 * peak.period) % peak.period) - 0.5 * peak.period
    left = primary & (offset < 0)
    right = primary & (offset >= 0)
    left_depth = baseline - float(np.nanmedian(flux[left])) if np.any(left) else primary_depth
    right_depth = baseline - float(np.nanmedian(flux[right])) if np.any(right) else primary_depth
    symmetry = 1.0 - min(abs(left_depth - right_depth) / max(primary_depth, 1e-9), 1.0)
    observed = max(1, int(np.unique(transit_number[primary]).size))
    phase, folded_flux = fold_and_bin(time, flux, peak.period, peak.epoch)
    global_view, local_view = make_global_local_views(
        time, flux, peak.period, peak.epoch, peak.duration
    )
    return {
        "depth_ppm": primary_depth * 1_000_000,
        "snr": float(snr),
        "num_transits_observed": observed,
        "odd_even_depth_diff_ppm": abs(odd_depth - even_depth) * 1_000_000,
        "secondary_eclipse_depth_ppm": secondary_depth * 1_000_000,
        "transit_shape_symmetry": float(symmetry),
        "phase": phase,
        "folded_flux": folded_flux,
        "global_view": global_view,
        "local_view": local_view,
    }
