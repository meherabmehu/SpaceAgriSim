"""
Reference evapotranspiration: FAO-56 Penman-Monteith, Hargreaves-Samani, and DLI.

This is product code, not a research script. It lives here because `app.et0` and the
simulator's water path both depend on it, and a research folder is not on the import path of
a deployed service.

Why this module is the most trustworthy thing in the codebase
-------------------------------------------------------------
Every other model here fits parameters to data. This one fits nothing: FAO-56 (Allen et al.
1998, Irrigation and Drainage Paper 56) is a closed-form energy balance plus an aerodynamic
term with no free coefficients. That is exactly why it can be checked against published
numbers, and why the checks below run on every call to `run_published_examples()`.

    ET0 = (0.408 * D * (Rn - G) + g * (900/(T+273)) * u2 * (es - ea))
          / (D + g * (1 + 0.34 * u2))

with D the slope of the saturation vapour-pressure curve, g the psychrometric constant, Rn
net radiation in MJ m^-2 d^-1, G soil heat flux (0 for a daily step), u2 wind at 2 m, and es
and ea saturation and actual vapour pressure in kPa.

The 0.408 converts MJ m^-2 d^-1 to mm d^-1 (latent heat of vaporisation 2.45 MJ/kg). Omitting
it - which this project did in its first draft of Hargreaves - inflates every ET0 value by
2.45x. Example 20 below is the check that caught it.

Units: temperatures degC, radiation MJ m^-2 d^-1, pressure kPa, wind m s^-1, ET0 mm d^-1.
"""
from __future__ import annotations

import math

# Solar constant (FAO-56 eq. 21), MJ m^-2 min^-1.
SOLAR_CONSTANT = 0.0820
STEFAN_BOLTZMANN = 4.903e-9  # MJ K^-4 m^-2 d^-1
ALBEDO_REFERENCE_GRASS = 0.23

# MJ m^-2 d^-1 -> mm d^-1 (latent heat of vaporisation, 2.45 MJ kg^-1).
MJ_TO_MM = 0.408

# PAR fraction of global shortwave radiation (standard convention for sunlight) and the
# photon conversion for PAR at its mean photon energy.
PAR_FRACTION_OF_GLOBAL = 0.45
MOL_PAR_PER_MJ = 4.57


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


# ---------------------------------------------------------------------------------------
# Astronomy
# ---------------------------------------------------------------------------------------
def extraterrestrial_radiation(latitude_deg: float, day_of_year: int) -> tuple[float, float]:
    """Daily extraterrestrial radiation Ra (MJ m^-2 d^-1) and daylight hours (eq. 21, 34).

    The arccos argument is clamped to [-1, 1]: at high latitudes during polar day or polar
    night it leaves the domain, and an unclamped arccos raises instead of returning the
    physically correct 24 h or 0 h of daylight.
    """
    phi = math.radians(latitude_deg)
    # Inverse relative Earth-Sun distance (eq. 23) and solar declination (eq. 24).
    dr = 1.0 + 0.033 * math.cos(2.0 * math.pi * day_of_year / 365.0)
    delta = 0.409 * math.sin(2.0 * math.pi * day_of_year / 365.0 - 1.39)

    cos_omega = _clamp(-math.tan(phi) * math.tan(delta), -1.0, 1.0)
    omega_s = math.acos(cos_omega)

    ra = ((24.0 * 60.0 / math.pi) * SOLAR_CONSTANT * dr
          * (omega_s * math.sin(phi) * math.sin(delta)
             + math.cos(phi) * math.cos(delta) * math.sin(omega_s)))
    daylight_hours = 24.0 / math.pi * omega_s
    return max(ra, 0.0), daylight_hours


def clear_sky_radiation(ra_mj: float, elevation_m: float) -> float:
    """Rso, the clear-sky solar radiation (FAO-56 eq. 37)."""
    return (0.75 + 2e-5 * max(elevation_m, 0.0)) * ra_mj


# ---------------------------------------------------------------------------------------
# Vapour pressure and the psychrometric quantities
# ---------------------------------------------------------------------------------------
def saturation_vapour_pressure(t_celsius: float) -> float:
    """es(T) in kPa (FAO-56 eq. 11)."""
    return 0.6108 * math.exp(17.27 * t_celsius / (t_celsius + 237.3))


def mean_saturation_vapour_pressure(tmax: float, tmin: float) -> float:
    """es in kPa from the daily extremes (FAO-56 eq. 12).

    Averaging the two saturation values, not saturating the average temperature: the curve is
    convex, so the two answers differ, and the standard specifies this one.
    """
    return (saturation_vapour_pressure(tmax) + saturation_vapour_pressure(tmin)) / 2.0


def actual_vapour_pressure_from_dewpoint(tdew_celsius: float) -> float:
    """ea in kPa from dew point (FAO-56 eq. 14). The preferred route: dew point is a
    temperature, so it is conserved through the day."""
    return saturation_vapour_pressure(tdew_celsius)


def actual_vapour_pressure_from_mean_rh(tmean: float, rh_mean: float) -> float:
    """ea in kPa from mean RH (FAO-56 eq. 19 fallback). Used only when dew point is absent."""
    return _clamp(rh_mean, 0.0, 100.0) / 100.0 * saturation_vapour_pressure(tmean)


def actual_vapour_pressure_from_rh_extremes(tmax: float, tmin: float,
                                            rh_max: float, rh_min: float) -> float:
    """ea in kPa from RH extremes (FAO-56 eq. 17). The other documented fallback."""
    return ((saturation_vapour_pressure(tmin) * _clamp(rh_max, 0.0, 100.0) / 100.0
             + saturation_vapour_pressure(tmax) * _clamp(rh_min, 0.0, 100.0) / 100.0) / 2.0)


def slope_saturation_curve(tmean: float) -> float:
    """Delta, kPa per degC (FAO-56 eq. 13)."""
    es = saturation_vapour_pressure(tmean)
    return 4098.0 * es / (tmean + 237.3) ** 2


def psychrometric_constant(pressure_kpa: float) -> float:
    """gamma, kPa per degC (FAO-56 eq. 7-8)."""
    return 0.000665 * pressure_kpa


def atmospheric_pressure(elevation_m: float) -> float:
    """Standard-atmosphere pressure, kPa (FAO-56 eq. 7). Used only when PS is unavailable."""
    return 101.3 * ((293.0 - 0.0065 * elevation_m) / 293.0) ** 5.26


def wind_at_2m(wind_ms: float, measurement_height_m: float = 2.0) -> float:
    """Convert wind measured at another height to 2 m (FAO-56 eq. 47). No-op at 2 m."""
    if measurement_height_m == 2.0:
        return wind_ms
    return wind_ms * 4.87 / math.log(67.8 * measurement_height_m - 5.42)


# ---------------------------------------------------------------------------------------
# Radiation balance
# ---------------------------------------------------------------------------------------
def net_longwave(rs: float, rso: float, tmax: float, tmin: float, ea: float) -> float:
    """Net outgoing longwave, MJ m^-2 d^-1 (FAO-56 eq. 39).

    The cloudiness factor Rs/Rso is clamped to [0, 1]. A measured Rs above the clear-sky value
    is possible (a distant cloud edge, a sensor offset) and would otherwise make Rnl negative,
    i.e. a longwave *gain* at the surface, which is unphysical for a daily step.
    """
    cloudiness = _clamp(rs / rso, 0.0, 1.0) if rso > 0 else 1.0
    sigma_t = ((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2.0
    return STEFAN_BOLTZMANN * sigma_t * (0.34 - 0.14 * math.sqrt(max(ea, 0.0))) * (
        1.35 * cloudiness - 0.35)


def net_radiation(rs: float, rso: float, tmax: float, tmin: float, ea: float) -> float:
    """Rn = Rns - Rnl in MJ m^-2 d^-1 (FAO-56 eq. 40)."""
    rns = (1.0 - ALBEDO_REFERENCE_GRASS) * rs
    return max(rns - net_longwave(rs, rso, tmax, tmin, ea), -50.0)


# ---------------------------------------------------------------------------------------
# The calculation
# ---------------------------------------------------------------------------------------
def reference_et0(
    *,
    tmax: float,
    tmin: float,
    ea: float,
    rs: float,
    wind_2m: float,
    pressure_kpa: float,
    day_of_year: int,
    latitude_deg: float,
    elevation_m: float,
) -> dict:
    """FAO-56 daily reference ET0 with its two terms kept separate.

    Returns ET0 in mm/day plus the radiation and aerodynamic contributions, net radiation and
    VPD, so a caller can see *why* a day is evaporative rather than only how much.
    """
    ra_mj, daylight_hours = extraterrestrial_radiation(latitude_deg, day_of_year)
    rso = clear_sky_radiation(ra_mj, elevation_m)
    tmean = (tmax + tmin) / 2.0

    es = mean_saturation_vapour_pressure(tmax, tmin)
    # ea can never exceed es at the daily mean: a dew point above the mean temperature would
    # give a negative VPD and an inverted aerodynamic term.
    ea_used = min(max(ea, 0.0), saturation_vapour_pressure(tmean))
    vpd = max(es - ea_used, 0.0)

    delta = slope_saturation_curve(tmean)
    gamma = psychrometric_constant(pressure_kpa)
    rn = net_radiation(rs, rso, tmax, tmin, ea_used)

    # Daily step, so soil heat flux G = 0 (FAO-56 eq. 42).
    denominator = delta + gamma * (1.0 + 0.34 * wind_2m)
    radiation_term = (MJ_TO_MM * delta * rn) / denominator
    aero_term = gamma * (900.0 / (tmean + 273.0)) * wind_2m * vpd / denominator

    return {
        "et0MmPerDay": radiation_term + aero_term,
        "radiationTermMm": radiation_term,
        "aeroTermMm": aero_term,
        "vpdKpa": vpd,
        "netRadiationMJm2": rn,
        "esKpa": es,
        "eaKpa": ea_used,
        "deltaKpaPerC": delta,
        "gammaKpaPerC": gamma,
        "raMJm2": ra_mj,
        "rsoMJm2": rso,
        "daylightHours": daylight_hours,
        "method": "FAO-56 Penman-Monteith daily (eq. 6), G = 0",
    }


def hargreaves_et0(tmax: float, tmin: float, ra_mj: float) -> dict:
    """Hargreaves-Samani ET0 (FAO-56 eq. 52) - temperature and latitude only.

    The 0.408 factor is mandatory: Ra arrives in MJ m^-2 d^-1 and the equation's output is a
    water depth. Without it the result is 2.45x too large, which is precisely the bug Example
    20 caught.
    """
    spread = max(tmax - tmin, 0.0)
    tmean = (tmax + tmin) / 2.0
    et0 = 0.0023 * MJ_TO_MM * ra_mj * (tmean + 17.8) * math.sqrt(spread)
    return {
        "et0MmPerDay": max(et0, 0.0),
        "method": "Hargreaves-Samani (FAO-56 eq. 52), temperature + latitude only",
    }


def daily_light_integral(rs_mj: float) -> dict:
    """DLI in mol m^-2 d^-1 from global shortwave radiation.

    An ESTIMATE for sunlight: the PAR fraction and the photon conversion are conventions for
    the solar spectrum, and neither applies to an LED fixture with a different spectrum.
    Labelled as an estimate wherever it is returned.
    """
    dli = max(rs_mj, 0.0) * PAR_FRACTION_OF_GLOBAL * MOL_PAR_PER_MJ
    return {
        "dliMolPerM2PerDay": dli,
        "method": "Rs [MJ m^-2 d^-1] x 0.45 (PAR fraction) x 4.57 (mol MJ^-1)",
        "estimate": True,
        "note": ("Sunlight conversion. An LED spectrum has a different PAR fraction and photon "
                 "energy, so this is not a fixture measurement."),
    }


# ---------------------------------------------------------------------------------------
# Self-checks against the published worked examples
# ---------------------------------------------------------------------------------------
# How far a recomputation may sit from the published worked example and still count as a match.
# 1.5 % absorbs the examples' own rounding (input values are printed to 1-2 decimals) while still
# failing on a dropped constant: the missing 0.408 in Hargreaves was a 145 % error.
PUBLISHED_EXAMPLE_TOLERANCE_PERCENT = 1.5


def run_published_examples() -> list[dict]:
    """Reproduce the worked examples printed in FAO-56 chapter 4.

    These are the only external authority available for this module, and the test suite asserts
    all three. A refactor that breaks one of them should break the build.
    """
    results: list[dict] = []

    # Example 17 - Bangkok, April. Rs (22.65) and RHmean (66 %) are the values the example
    # itself uses; deriving Rs from sunshine hours here would test the Angstrom formula as well
    # as the ET0 equation, and this check is about ET0.
    ra, _ = extraterrestrial_radiation(13.73, 105)
    example17 = reference_et0(
        tmax=34.8, tmin=25.6,
        ea=actual_vapour_pressure_from_mean_rh((34.8 + 25.6) / 2.0, 66.0),
        rs=22.65, wind_2m=2.0, pressure_kpa=101.3, day_of_year=105,
        latitude_deg=13.73, elevation_m=2.0)
    results.append({"example": "FAO-56 Example 17 (Bangkok, monthly)",
                    "publishedMmPerDay": 5.72, "computedMmPerDay": example17["et0MmPerDay"],
                    "ra": ra, "rs": 22.65})

    # Example 18 - Uccle, 6 July: the daily case this module is actually used for.
    ra18, _ = extraterrestrial_radiation(50.8, 187)
    example18 = reference_et0(
        tmax=21.5, tmin=12.3,
        ea=actual_vapour_pressure_from_rh_extremes(21.5, 12.3, 84.0, 63.0),
        rs=22.07, wind_2m=wind_at_2m(2.078, 2.0), pressure_kpa=100.1, day_of_year=187,
        latitude_deg=50.8, elevation_m=100.0)
    results.append({"example": "FAO-56 Example 18 (Uccle, daily)",
                    "publishedMmPerDay": 3.88, "computedMmPerDay": example18["et0MmPerDay"],
                    "ra": ra18, "rs": 22.07, "ea": example18["eaKpa"],
                    "u2": wind_at_2m(2.078, 2.0)})

    # Example 20 - Lyon, July: Hargreaves must land on 5.0 mm/day. This is the check that caught
    # the missing 0.408.
    ra20, _ = extraterrestrial_radiation(45.72, 196)
    example20 = hargreaves_et0(26.6, 14.8, ra20)
    results.append({"example": "FAO-56 Example 20, Hargreaves-Samani (Lyon, July)",
                    "publishedMmPerDay": 5.0, "computedMmPerDay": example20["et0MmPerDay"],
                    "ra": ra20, "rs": None})

    for row in results:
        difference = row["computedMmPerDay"] - row["publishedMmPerDay"]
        percent = 100.0 * difference / row["publishedMmPerDay"]
        row["differenceMmPerDay"] = round(difference, 4)
        row["percentDifference"] = round(percent, 3)
        row["withinTolerance"] = abs(percent) <= PUBLISHED_EXAMPLE_TOLERANCE_PERCENT
    return results


if __name__ == "__main__":
    for row in run_published_examples():
        extra = ", ".join(f"{k} {v:.2f}" for k, v in row.items()
                          if k in ("ra", "rs") and v is not None)
        print(f"{row['example']}: published {row['publishedMmPerDay']} mm/day, "
              f"computed {row['computedMmPerDay']:.2f} mm/day  ({extra})")
