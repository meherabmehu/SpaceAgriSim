"""Read a Copernicus CDS ERA5-Land NetCDF file into the six FAO-56 input series.

Written against the CDS short names (``t2m``, ``d2m``, ``ssrd``, ``10u``, ``10v``, ``sp``) and
their real units, because every one of them needs a conversion and a wrong conversion is
silent: 273 K reads as a hot day, a J m^-2 accumulation reads as permanent noon, and Pa reads
as a ten-fold inflated psychrometric constant.

The reader is exercised end to end on synthetic NetCDF files carrying those names, units and
step types. That proves the parsing and the unit handling. **It does not prove that CDS returns
what its documentation says**, and no document here claims a real retrieval has been validated
while none has run.
"""
from __future__ import annotations

import datetime as _dt
import math
from pathlib import Path
from typing import Any

import numpy as np

# Variable name in the file -> (FAO-56 meaning, conversion applied on read)
REQUIRED_VARIABLES = {
    "t2m": "2 m temperature (K -> degC)",
    "d2m": "2 m dew point (K -> degC)",
    "ssrd": "surface solar radiation downwards (J m-2 per hour -> W m-2)",
    "10u": "10 m u wind component (m s-1)",
    "10v": "10 m v wind component (m s-1)",
    "sp": "surface pressure (Pa -> hPa)",
}
SECONDS_PER_HOUR = 3600.0
KELVIN_OFFSET = 273.15
PA_PER_HPA = 100.0

# Daily Rs must be a plausible fraction of extraterrestrial radiation. The upper bound is
# 0.85 (clear sky attenuates even at altitude); the lower bound 0.05 rejects a radiation series
# that has been divided when it should not have been, which otherwise looks like overcast.
MIN_RS_FRACTION_OF_RA = 0.05
MAX_RS_FRACTION_OF_RA = 0.85


class Era5LandFileError(RuntimeError):
    """The file cannot be interpreted as an ERA5-Land hourly NetCDF."""


def _open(path: str | Path):
    try:
        from scipy.io import netcdf_file  # type: ignore
    except ImportError as exc:  # pragma: no cover - scipy is a test/runtime dependency
        raise Era5LandFileError("scipy is required to read NetCDF files") from exc
    handle = netcdf_file(str(path), "r", mmap=False)
    return handle


def available_variables(path: str | Path) -> list[str]:
    handle = _open(path)
    try:
        return sorted(handle.variables)
    finally:
        handle.close()


def _array(handle, name: str) -> np.ndarray:
    variable = handle.variables[name]
    data = np.array(variable.data, dtype=float)
    # CDS NetCDF3 files store data with a scale_factor/add_offset pair; scipy applies neither.
    scale = getattr(variable, "scale_factor", None)
    offset = getattr(variable, "add_offset", None)
    if scale is not None:
        data = data * float(scale)
    if offset is not None:
        data = data + float(offset)
    return data


def _normalise_longitude(lon: float) -> float:
    """CDS grids run 0-360, so a western site arrives as 249.05 rather than -110.95."""
    return lon - 360.0 if lon > 180.0 else lon


def _times(handle) -> list[str]:
    if "time" not in handle.variables:
        raise Era5LandFileError("file has no 'time' variable")
    raw = _array(handle, "time")
    units = getattr(handle.variables["time"], "units", b"hours since 1900-01-01 00:00:00")
    if isinstance(units, bytes):
        units = units.decode("utf-8", "replace")
    if "since" not in units:
        raise Era5LandFileError(f"unrecognised time units {units!r}")
    epoch_text = units.split("since", 1)[1].strip().replace("Z", "")
    epoch = _dt.datetime.fromisoformat(epoch_text)
    scale = 24.0 if units.strip().startswith("days") else 1.0
    return [(epoch + _dt.timedelta(hours=float(value) * scale)).strftime("%Y-%m-%dT%H:00")
            for value in raw.reshape(-1)]


def _series(handle, name: str) -> np.ndarray:
    data = _array(handle, name)
    # Collapse latitude/longitude to the single grid point the request box encloses, keeping
    # the leading (time) dimension intact so the series stays aligned with the hour stamps.
    while data.ndim > 1:
        data = data.take(0, axis=-1)
    return data.reshape(-1)


def hourly_series_from_netcdf(path: str | Path) -> dict[str, Any]:
    """Convert a CDS ERA5-Land file into FAO-56 inputs, applying every unit conversion."""
    handle = _open(path)
    try:
        present = set(handle.variables)
        missing = [name for name in REQUIRED_VARIABLES if name not in present]
        if missing:
            raise Era5LandFileError(
                "NetCDF is missing required variable(s) "
                + ", ".join(f"{name!r} ({REQUIRED_VARIABLES[name]})" for name in missing)
                + "; the file contains: "
                + ", ".join(sorted(present))
            )

        hours = _times(handle)
        temperature = _series(handle, "t2m") - KELVIN_OFFSET
        dewpoint = _series(handle, "d2m") - KELVIN_OFFSET
        # ssrd arrives as J m-2 accumulated over the hour. Dividing by 3600 gives W m-2; doing
        # the opposite gives values in the millions, which the plausibility band rejects.
        rs_w_m2 = _series(handle, "ssrd") / SECONDS_PER_HOUR
        u10 = _series(handle, "10u")
        v10 = _series(handle, "10v")
        pressure_hpa = _series(handle, "sp") / PA_PER_HPA

        latitude = float(_array(handle, "latitude").reshape(-1)[0]) if "latitude" in present else None
        longitude = float(_array(handle, "longitude").reshape(-1)[0]) if "longitude" in present else None
        if longitude is not None:
            longitude = _normalise_longitude(longitude)
    finally:
        handle.close()

    length = min(len(temperature), len(dewpoint), len(rs_w_m2), len(u10), len(v10),
                 len(pressure_hpa), len(hours))
    speed = np.hypot(u10[:length], v10[:length])

    for name, values in (("temperature", temperature[:length]),
                         ("shortwave_radiation", rs_w_m2[:length])):
        if not np.all(np.isfinite(values)):
            raise Era5LandFileError(f"{name} contains non-finite values")

    return {
        "hours": hours[:length],
        "series": {
            "temperature_2m": [float(v) for v in temperature[:length]],
            "dewpoint_2m": [float(v) for v in dewpoint[:length]],
            "shortwave_radiation": [float(v) for v in rs_w_m2[:length]],
            "wind_speed_10m": [float(v) for v in speed],
            "surface_pressure": [float(v) for v in pressure_hpa[:length]],
        },
        "conversions": {
            "t2m": "K -> degC (subtract 273.15)",
            "d2m": "K -> degC (subtract 273.15)",
            "ssrd": "J m-2 accumulated per hour -> W m-2 (divide by 3600)",
            "10u/10v": "components -> speed (hypot)",
            "sp": "Pa -> hPa (divide by 100)",
        },
        "gridPoint": {"latitude": latitude, "longitude": longitude},
    }


def radiation_energy_check(
    daily_rs_mj: dict[str, float],
    daily_ra_mj: dict[str, float],
    *,
    min_fraction: float = MIN_RS_FRACTION_OF_RA,
    max_fraction: float = MAX_RS_FRACTION_OF_RA,
) -> dict[str, Any]:
    """Compare daily Rs against extraterrestrial radiation for each shared day.

    The per-hour plausibility band catches "forgot to divide by 3600" (values in the millions)
    but **not** an over-division: that produces a small, plausible-looking flux which reads as
    permanent overcast and quietly zeroes the radiation term. Energy conservation catches it.
    """
    failures: list[dict[str, Any]] = []
    ratios: list[float] = []
    for day in sorted(set(daily_rs_mj) & set(daily_ra_mj)):
        ra = daily_ra_mj[day]
        if not ra or ra <= 0 or not math.isfinite(ra):
            continue
        rs = daily_rs_mj[day]
        if rs is None or not math.isfinite(rs):
            continue
        ratio = rs / ra
        ratios.append(ratio)
        if ratio < min_fraction or ratio > max_fraction:
            failures.append({"day": day, "rsMJm2": rs, "raMJm2": ra, "ratio": ratio})

    return {
        "daysChecked": len(ratios),
        "minRatio": min(ratios) if ratios else None,
        "maxRatio": max(ratios) if ratios else None,
        "meanRatio": (sum(ratios) / len(ratios)) if ratios else None,
        "implausibleDays": failures[:20],
        "implausibleDayCount": len(failures),
        "ok": not failures,
        "interpretation": (
            "Rs/Ra outside [0.05, 0.85] means a radiation unit error: an over-division looks "
            "like permanent overcast and a missed division looks like an impossible flux."
        ),
    }
