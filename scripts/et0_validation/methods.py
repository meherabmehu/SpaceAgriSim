"""FAO-56 computations used by the validation.

Two forms of the same equation are implemented because the difference between them is one of
the things being measured:

* :func:`hourly_et0` - eq. 53 applied per hour, summed over 24 h. G is 0.1 Rn in daylight and
  0.5 Rn at night (eq. 45-46), Ra is integrated over the hour (eq. 28).
* :func:`daily_et0` - eq. 6 applied to daily aggregates with G = 0 (eq. 42), delegated to the
  product's audited implementation so the validation cannot silently drift from production.

Neither returns a value it can avoid: a day with insufficient inputs is ``None``, never zero.
"""
from __future__ import annotations

import datetime as _dt
import math
import sys
from pathlib import Path
from typing import Any, Sequence

_BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND) not in sys.path:  # pragma: no cover - import plumbing
    sys.path.insert(0, str(_BACKEND))

from app.simulation.et0_fao56 import (  # noqa: E402
    ALBEDO_REFERENCE_GRASS,
    MJ_TO_MM,
    STEFAN_BOLTZMANN,
    clear_sky_radiation,
    extraterrestrial_radiation,
    hargreaves_et0,
    psychrometric_constant,
    reference_et0,
    saturation_vapour_pressure,
    slope_saturation_curve,
    wind_at_2m,
)

# Stefan-Boltzmann for an HOURLY step. The daily constant is per day, so it must be divided
# by 24 - multiplying instead produced ET0 of -75 000 mm/day in an early version, and the
# regression test asserts this relationship rather than the literal value.
STEFAN_BOLTZMANN_HOURLY = STEFAN_BOLTZMANN / 24.0
SOLAR_CONSTANT = 0.0820  # MJ m^-2 min^-1
J_PER_MJ = 1_000_000.0
SECONDS_PER_HOUR = 3600.0

MIN_ISD_HOURS_PER_DAY = 18


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def hourly_extraterrestrial_radiation(
    latitude_deg: float, day_of_year: int, solar_hour_midpoint: float
) -> float:
    """Ra for one hour, MJ m^-2 h^-1 (FAO-56 eq. 28).

    ``solar_hour_midpoint`` is local solar time in hours (0-24). The bracket is built from the
    hour's angular bounds directly; reusing the daily eq. 21 bracket here double-counts
    sin(phi)sin(delta) and drives Ra negative in the afternoon.
    """
    phi = math.radians(latitude_deg)
    dr = 1.0 + 0.033 * math.cos(2.0 * math.pi * day_of_year / 365.0)
    delta = 0.409 * math.sin(2.0 * math.pi * day_of_year / 365.0 - 1.39)

    omega = math.radians((solar_hour_midpoint - 12.0) * 15.0)
    omega1 = omega - math.pi / 24.0
    omega2 = omega + math.pi / 24.0

    return max(
        (12.0 * 60.0 / math.pi) * SOLAR_CONSTANT * dr
        * ((omega2 - omega1) * math.sin(phi) * math.sin(delta)
           + math.cos(phi) * math.cos(delta) * (math.sin(omega2) - math.sin(omega1))),
        0.0,
    )


def solar_hour_midpoint(hour_utc: int, longitude_deg: float) -> float:
    """Local solar time at the middle of a UTC hourly interval.

    The longitude/15 deg shift is what makes a station at 110 W use the correct Ra: without
    it, morning and evening hours exchange radiation, which biases the daylight-flagged
    radiation term.
    """
    return (hour_utc + 0.5 + longitude_deg / 15.0) % 24.0


def hourly_et0(
    *,
    temperature_c: float,
    dewpoint_c: float,
    rs_w_m2: float,
    wind_10m_ms: float,
    pressure_kpa: float,
    latitude_deg: float,
    longitude_deg: float,
    day_of_year: int,
    hour_utc: int,
    elevation_m: float,
    u2_override: float | None = None,
) -> dict[str, float]:
    """FAO-56 eq. 53 for one hour; the caller sums 24 of these.

    All inputs are in the units named. ``rs_w_m2`` is an hourly mean flux, so it is converted
    to MJ m^-2 h^-1 here - a W m^-2 value used directly would be 3.6e6 too large.
    """
    rs = rs_w_m2 * SECONDS_PER_HOUR / J_PER_MJ
    ra = hourly_extraterrestrial_radiation(
        latitude_deg, day_of_year, solar_hour_midpoint(hour_utc, longitude_deg)
    )
    rso = clear_sky_radiation(ra, elevation_m) if ra > 0 else 0.0

    es = saturation_vapour_pressure(temperature_c)
    ea = min(saturation_vapour_pressure(dewpoint_c), es)
    delta = slope_saturation_curve(temperature_c)
    gamma = psychrometric_constant(pressure_kpa)
    u2 = wind_at_2m(wind_10m_ms, measurement_height_m=10.0)
    if u2_override is not None:
        u2 = u2_override

    cloudiness = _clamp(rs / rso, 0.0, 1.0) if rso > 0 else 1.0
    rnl = (STEFAN_BOLTZMANN_HOURLY * (temperature_c + 273.16) ** 4
           * (0.34 - 0.14 * math.sqrt(max(ea, 0.0))) * (1.35 * cloudiness - 0.35))
    rn = max((1.0 - ALBEDO_REFERENCE_GRASS) * rs - rnl, -5.0)

    # Daylight is decided by physics (Ra > 0), not by clock time: at high latitude in summer
    # the sun is up outside any fixed hour window.
    daylight = ra > 0.0
    g = 0.1 * rn if daylight else 0.5 * rn

    denominator = delta + gamma * (1.0 + 0.34 * u2)
    radiation_term = MJ_TO_MM * delta * (rn - g) / denominator
    aero_term = gamma * (37.0 / (temperature_c + 273.0)) * u2 * max(es - ea, 0.0) / denominator

    return {
        "et0Mm": radiation_term + aero_term,
        "radiationTermMm": radiation_term,
        "aeroTermMm": aero_term,
        "raMJm2": ra,
        "rsMJm2": rs,
        "daylight": 1.0 if daylight else 0.0,
        "u2": u2,
        "esKpa": es,
        "eaKpa": ea,
    }


def _hour_stamps(hours: Sequence[str]) -> list[_dt.datetime]:
    stamps = []
    for stamp in hours:
        clean = stamp.replace("Z", "").replace(" ", "T")
        stamps.append(_dt.datetime.fromisoformat(clean))
    return stamps


def hourly_series_to_daily(
    payload: dict[str, Any],
    site: Any,
    *,
    u2_override: float | None = None,
    u2_from_wind_raw: bool = False,
) -> dict[str, dict[str, Any]]:
    """Apply :func:`hourly_et0` to every hour and aggregate to days.

    A day is emitted only when all 24 hours are present and complete; a partial day is dropped
    rather than summed over fewer hours, because a 20-hour sum silently understates ET0.
    """
    series = payload["series"]
    stamps = _hour_stamps(payload["hours"])
    buckets: dict[str, list[tuple[_dt.datetime, int]]] = {}
    for index, stamp in enumerate(stamps):
        buckets.setdefault(stamp.date().isoformat(), []).append((stamp, index))

    daily: dict[str, dict[str, Any]] = {}
    for day, members in buckets.items():
        if len(members) != 24:
            continue
        members.sort()
        day_of_year = members[0][0].timetuple().tm_yday
        values = {"et0Mm": 0.0, "radiationTermMm": 0.0, "aeroTermMm": 0.0}
        tmax = tmin = None
        dew_sum = 0.0
        rs_sum = 0.0
        u2_sum = 0.0
        pressure_sum = 0.0
        complete = True

        for stamp, index in members:
            try:
                temp = series["temperature_2m"][index]
                dew = series["dewpoint_2m"][index]
                rs = series["shortwave_radiation"][index]
                wind = series["wind_speed_10m"][index]
                pressure = series["surface_pressure"][index]
            except KeyError as exc:  # pragma: no cover - guarded by sources
                raise KeyError(f"hourly field missing: {exc}") from exc
            if None in (temp, dew, rs, wind, pressure):
                complete = False
                break
            hour = hourly_et0(
                temperature_c=float(temp),
                dewpoint_c=float(dew),
                rs_w_m2=float(rs),
                wind_10m_ms=float(wind),
                pressure_kpa=float(pressure) / 10.0,  # hPa -> kPa
                latitude_deg=site.latitude,
                longitude_deg=site.longitude,
                day_of_year=day_of_year,
                hour_utc=stamp.hour,
                elevation_m=site.elevation_m,
                # ``u2_from_wind_raw`` skips eq. 47, which is how the cost of omitting the
                # 10 m -> 2 m conversion is measured rather than argued about.
                u2_override=float(wind) if u2_from_wind_raw else u2_override,
            )
            for key in values:
                values[key] += hour[key]
            tmax = float(temp) if tmax is None else max(tmax, float(temp))
            tmin = float(temp) if tmin is None else min(tmin, float(temp))
            dew_sum += float(dew)
            rs_sum += float(rs) * SECONDS_PER_HOUR / J_PER_MJ
            u2_sum += hour["u2"]
            pressure_sum += float(pressure)

        if not complete or tmax is None:
            continue
        daily[day] = {
            **values,
            "tmax": tmax,
            "tmin": tmin,
            "dewMean": dew_sum / 24.0,
            "rsMJm2": rs_sum,
            "u2Mean": u2_sum / 24.0,
            "pressureKpa": pressure_sum / 24.0 / 10.0,
            "hoursUsed": 24,
        }
    return daily


def daily_et0(
    *,
    tmax: float,
    tmin: float,
    ea_kpa: float,
    rs_mj: float,
    wind_2m_ms: float,
    pressure_kpa: float,
    day_of_year: int,
    latitude_deg: float,
    elevation_m: float,
) -> dict[str, Any]:
    """FAO-56 daily eq. 6 via the production implementation (G = 0)."""
    return reference_et0(
        tmax=tmax,
        tmin=tmin,
        ea=ea_kpa,
        rs=rs_mj,
        wind_2m=wind_2m_ms,
        pressure_kpa=pressure_kpa,
        day_of_year=day_of_year,
        latitude_deg=latitude_deg,
        elevation_m=elevation_m,
    )


def hargreaves_for_day(tmax: float, tmin: float, latitude_deg: float, day_of_year: int) -> float:
    """Hargreaves-Samani ET0 from temperature and latitude only (FAO-56 eq. 52)."""
    ra, _ = extraterrestrial_radiation(latitude_deg, day_of_year)
    return hargreaves_et0(tmax=tmax, tmin=tmin, ra_mj=ra)["et0MmPerDay"]


def isd_daily_temperature(payload: dict[str, Any], site: Any) -> dict[str, dict[str, Any]]:
    """Daily Tmax/Tmin from ISD hourly temperatures.

    A day is used only when at least ``MIN_ISD_HOURS_PER_DAY`` hours carry a temperature; the
    rejected days are counted by the caller and reported as missingness, not filled.
    """
    temps = payload["series"]["temp_c"]
    stamps = _hour_stamps(payload["hours"])
    buckets: dict[str, list[float]] = {}
    for stamp, value in zip(stamps, temps):
        if value is None:
            continue
        buckets.setdefault(stamp.date().isoformat(), []).append(float(value))

    daily: dict[str, dict[str, Any]] = {}
    for day, values in buckets.items():
        if len(values) < MIN_ISD_HOURS_PER_DAY:
            continue
        day_of_year = _dt.date.fromisoformat(day).timetuple().tm_yday
        daily[day] = {
            "tmax": max(values),
            "tmin": min(values),
            "hoursUsed": len(values),
            "et0": hargreaves_for_day(max(values), min(values), site.latitude, day_of_year),
        }
    return daily
