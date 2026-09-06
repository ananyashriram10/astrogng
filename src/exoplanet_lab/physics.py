"""Derived physical properties for a transit candidate.

These turn the raw measurables (depth, period) into quantities a person can
reason about — planet size, orbital distance, rough temperature — using the
standard relations. Every function returns ``None`` when the stellar inputs it
needs are unknown, because a wrong number here is worse than no number.
"""

from __future__ import annotations

import math


EARTH_RADII_PER_SOLAR_RADIUS = 109.076
AU_PER_SOLAR_RADIUS = 0.00465047
DEFAULT_BOND_ALBEDO = 0.3


def planet_radius_earth(
    depth_ppm: float, stellar_radius_solar: float | None
) -> float | None:
    """Rp = R* * sqrt(depth). Transit depth is the ratio of the two disc areas."""
    if not stellar_radius_solar or stellar_radius_solar <= 0 or depth_ppm <= 0:
        return None
    depth = depth_ppm / 1_000_000
    radius_solar = stellar_radius_solar * math.sqrt(depth)
    return radius_solar * EARTH_RADII_PER_SOLAR_RADIUS


def semi_major_axis_au(
    period_days: float, stellar_mass_solar: float | None
) -> float | None:
    """Kepler's third law in solar units: a^3 = M * P^2, with a in AU and P in years."""
    if not stellar_mass_solar or stellar_mass_solar <= 0 or period_days <= 0:
        return None
    period_years = period_days / 365.25
    return (stellar_mass_solar * period_years**2) ** (1 / 3)


def equilibrium_temperature_k(
    stellar_teff_k: float | None,
    stellar_radius_solar: float | None,
    axis_au: float | None,
    albedo: float = DEFAULT_BOND_ALBEDO,
) -> float | None:
    """T_eq = T* * sqrt(R* / 2a) * (1 - A)^(1/4).

    Assumes even heat redistribution and a Bond albedo; this is a ballpark
    figure for context, not a claim about an actual surface temperature.
    """
    if (
        not stellar_teff_k
        or not stellar_radius_solar
        or not axis_au
        or stellar_teff_k <= 0
        or stellar_radius_solar <= 0
        or axis_au <= 0
    ):
        return None
    radius_au = stellar_radius_solar * AU_PER_SOLAR_RADIUS
    return stellar_teff_k * math.sqrt(radius_au / (2 * axis_au)) * (1 - albedo) ** 0.25


def size_class(radius_earth: float | None) -> str | None:
    """Rough bucket used for a human-readable label."""
    if radius_earth is None or radius_earth <= 0:
        return None
    if radius_earth < 1.25:
        return "Earth-size"
    if radius_earth < 2.0:
        return "super-Earth"
    if radius_earth < 6.0:
        return "Neptune-size"
    if radius_earth < 15.0:
        return "Jupiter-size"
    return "larger than Jupiter"
