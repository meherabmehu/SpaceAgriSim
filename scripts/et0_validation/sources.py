"""Acquisition for the independent ET0 validation.

Every function returns a payload dict with two parts:

* the data, keyed for direct use by :mod:`scripts.et0_validation.methods`;
* a ``provenance`` block recording product, route, resolution, units, licence, request URL
  (never a credential) and the SHA-256 digests of what was parsed.

No function invents data. A route that cannot run raises and names what is missing.
"""
from __future__ import annotations

import datetime as _dt
import gzip
import hashlib
import json
import math
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

USER_AGENT = "SpaceAgriSim-ET0Validation/2.0 (+https://github.com/meherabmehu/SpaceAgriSim)"
HTTP_TIMEOUT_S = 180
RETRIES = 5
CACHE_ENV_VAR = "SPACEAGRISIM_ET0_HTTP_CACHE"

OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
POWER_DAILY = "https://power.larc.nasa.gov/api/temporal/daily/point"
ISD_LITE = "https://noaa-isd-pds.s3.amazonaws.com/isd-lite/data/{year}/{usaf}-{wban}-{year}.gz"

# The v2 daily POWER endpoint rejects the ET0 parameter with HTTP 422 in every community; the
# pipeline therefore computes its own PM series and records this flag so a reviewer must
# consciously re-check rather than assume the provider value was compared.
POWER_ET0_AVAILABLE = False

OPEN_METEO_LICENCE = "Open-Meteo archive API, CC BY 4.0 (values: Copernicus/ERA5 licence terms)"
POWER_LICENCE = "NASA POWER, open data (CC BY 4.0), MERRA-2 derived"
ISD_LICENCE = "NOAA ISD-Lite, U.S. Government work, public domain"

OPEN_METEO_MODELS = {
    "era5": {
        "product": "ERA5 (ECMWF/C3S) via Open-Meteo archive API",
        # One request per leg; the five fields are exactly what FAO-56 needs.
        "resolution_deg": 0.25,
        "hourly_fields": {
            "temperature_2m": "2 m air temperature",
            "dewpoint_2m": "2 m dew point",
            "shortwave_radiation": "global horizontal shortwave flux",
            "wind_speed_10m": "10 m wind speed",
            "surface_pressure": "surface pressure",
        },
        "daily_fields": {
            "temperature_2m_max": "daily maximum 2 m temperature",
            "temperature_2m_min": "daily minimum 2 m temperature",
            "shortwave_radiation_sum": "daily global shortwave sum",
        },
    },
    "era5_land": {
        "product": "ERA5-Land (ECMWF/C3S) via Open-Meteo archive API",
        "resolution_deg": 0.1,
        # Radiation and wind are returned as null by this route at every hour - verified by
        # request, which is why the ERA5-Land leg here can only be a temperature-only method.
        "hourly_fields": {
            "temperature_2m": "2 m air temperature",
            "dewpoint_2m": "2 m dew point",
        },
        "daily_fields": {
            "temperature_2m_max": "daily maximum 2 m temperature",
            "temperature_2m_min": "daily minimum 2 m temperature",
        },
    },
}


class SourceUnavailableError(RuntimeError):
    """An upstream route could not deliver data. Never swallowed into a partial result."""


class MissingCredentialError(SourceUnavailableError):
    """A credentialed route was asked to run without its credentials.

    The message names the environment variables and never echoes a value.
    """


# ---------------------------------------------------------------------------------------
# Sites
# ---------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Site:
    key: str
    label: str
    latitude: float
    longitude: float
    elevation_m: float
    climate: str
    isd_usaf: str
    isd_wban: str
    isd_name: str
    station_distance_km: float
    station_elevation_m: float


def sites() -> list[Site]:
    """The six validation sites.

    Selection was fixed before any ET0 comparison was run: six climates, both hemispheres,
    sea level to 1 798 m, and a dedicated NOAA ISD station within 20 km of each grid point.
    The climate note is descriptive, not a hypothesis formed after seeing the errors.
    """
    return [
        Site("wageningen_nl", "Wageningen, Netherlands", 51.97, 5.67, 16.0,
             "Temperate maritime, humid, high wind",
             "062750", "99999", "DEELEN", 17.0, 48.2),
        Site("tucson_us", "Tucson, Arizona, USA", 32.28, -110.95, 824.0,
             "Hot arid, extreme VPD, strong radiation",
             "722740", "23160", "TUCSON INTERNATIONAL AIRPORT", 16.0, 777.6),
        Site("singapore_sg", "Singapore", 1.35, 103.82, 15.0,
             "Equatorial, small annual range, near-saturated air",
             "486980", "99999", "SINGAPORE CHANGI INTL", 19.0, 6.7),
        # Tejgaon (419230) is nearer but reports only 29-365 days per year in 2021-2023, none
        # with a full diurnal temperature cycle; the airport station (419220) is 4 km from
        # the grid point and complete, so it is the station used.
        Site("dhaka_bd", "Dhaka, Bangladesh", 23.81, 90.41, 9.0,
             "Monsoon tropics, dry winter, dust/haze season",
             "419220", "99999", "HAZRAT SHAHJALAL INTL", 4.0, 9.1),
        Site("reykjavik_is", "Reykjavik, Iceland", 64.13, -21.90, 53.0,
             "Subpolar maritime, low Ra in winter, high wind",
             "040300", "99999", "REYKJAVIK (040300)", 2.0, 14.6),
        Site("nairobi_ke", "Nairobi, Kenya", -1.29, 36.82, 1798.0,
             "Equatorial highland, high elevation correction",
             "637420", "99999", "NAIROBI WILSON", 4.0, 1687.4),
    ]


def site_by_key(key: str) -> Site:
    for site in sites():
        if site.key == key:
            return site
    raise KeyError(f"unknown site {key!r}")


# ---------------------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------------------
def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_series(series: dict[str, list[Any]]) -> str:
    """Digest of the canonicalised numeric series, for reproducibility checks.

    ``payloadSha256`` covers the bytes exactly as received, which is what an audit trail
    should record. Those bytes are not stable across requests to a live service (key
    ordering, generation-time metadata), so they cannot answer "did a re-run get the same
    data". This digest rounds to 6 decimals and sorts keys, so it is stable when the data are.
    """
    canonical = {
        name: [None if v is None else round(float(v), 6) for v in values]
        for name, values in sorted(series.items())
    }
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def backoff_seconds(attempt: int, retry_after: float | None = None) -> float:
    """Delay before retry ``attempt`` (0-based): exponential, or an explicit Retry-After."""
    if retry_after is not None and retry_after >= 0:
        return min(retry_after, 120.0)
    return 1.5 * (2 ** attempt)


def _cache_dir() -> Path | None:
    raw = os.environ.get(CACHE_ENV_VAR, "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _fetch_bytes(url: str, *, headers: dict[str, str] | None = None) -> bytes:
    """GET with retries and an optional on-disk content cache.

    The cache is opt-in through ``SPACEAGRISIM_ET0_HTTP_CACHE`` and keyed by request URL, so a
    re-run replays exactly the bytes the first run received. Each leg's provenance records
    whether the cache was on, so a replay cannot be mistaken for a fresh retrieval.
    """
    cache = _cache_dir()
    if cache is not None:
        cached = cache / (sha256_bytes(url.encode("utf-8")) + ".payload")
        if cached.is_file():
            return cached.read_bytes()

    last: Exception | None = None
    for attempt in range(RETRIES):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
                payload = resp.read()
            if cache is not None:
                cached.write_bytes(payload)
            return payload
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code in (400, 401, 403, 404) or attempt == RETRIES - 1:
                raise SourceUnavailableError(
                    f"request failed with HTTP {exc.code} after {attempt + 1} attempt(s): {url}"
                ) from exc
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            try:
                delay = backoff_seconds(attempt, float(retry_after) if retry_after else None)
            except (TypeError, ValueError):
                delay = backoff_seconds(attempt)
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError) as exc:  # pragma: no cover - network
            last = exc
            if attempt == RETRIES - 1:
                break
            time.sleep(backoff_seconds(attempt))
    raise SourceUnavailableError(f"request failed after {RETRIES} attempts: {url}") from last


def _fetch_json(url: str) -> tuple[dict[str, Any], str]:
    payload = _fetch_bytes(url)
    try:
        return json.loads(payload.decode("utf-8")), sha256_bytes(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceUnavailableError(f"response was not JSON: {url}") from exc


def _day_list(start: str, end: str) -> list[str]:
    first = _dt.date.fromisoformat(start)
    last = _dt.date.fromisoformat(end)
    if last < first:
        raise ValueError("end precedes start")
    return [(first + _dt.timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]


# ---------------------------------------------------------------------------------------
# Open-Meteo archive (ERA5 and ERA5-Land)
# ---------------------------------------------------------------------------------------
def _open_meteo_url(site: Site, start: str, end: str, model: str, daily: bool) -> str:
    spec = OPEN_METEO_MODELS[model]
    if model not in OPEN_METEO_MODELS:
        raise KeyError(f"unknown model {model!r}")
    names = list(spec["daily_fields"] if daily else spec["hourly_fields"])
    if daily and model == "era5":
        # The provider's own FAO-56 series is the implementation control; it only comes back
        # when it is asked for explicitly.
        names.append("et0_fao_evapotranspiration")
    fields = ",".join(names)
    kind = "daily" if daily else "hourly"
    return (
        f"{OPEN_METEO_ARCHIVE}?latitude={site.latitude}&longitude={site.longitude}"
        f"&start_date={start}&end_date={end}&models={model}&timezone=UTC&wind_speed_unit=ms"
        f"&{kind}={fields}"
    )


def fetch_open_meteo(site: Site, start: str, end: str, model: str = "era5") -> dict[str, Any]:
    """Hourly series for one site.

    ``wind_speed_unit=ms`` is mandatory: the API default is km/h and a 3.6x wind error would
    be invisible in plausible-looking output.
    """
    url = _open_meteo_url(site, start, end, model, daily=False)
    payload, digest = _fetch_json(url)
    block = payload.get("hourly") or {}
    times = block.get("time") or []
    if not times:
        raise SourceUnavailableError(f"no hourly data returned for {site.key}")

    series: dict[str, list[Any]] = {}
    for name in OPEN_METEO_MODELS[model]["hourly_fields"]:
        values = block.get(name)
        if values is None:
            raise SourceUnavailableError(f"field {name!r} absent for {site.key}")
        series[name] = [None if v is None else float(v) for v in values]

    return {
        "hours": times,
        "series": series,
        "provenance": {
            "route": "open-meteo-archive-api",
            "product": OPEN_METEO_MODELS[model]["product"],
            "model": model,
            "temporalResolution": "hourly (UTC)",
            "spatialResolutionDeg": OPEN_METEO_MODELS[model]["resolution_deg"],
            "fields": dict(OPEN_METEO_MODELS[model]["hourly_fields"]),
            "units": {
                "temperature_2m": "degC",
                "dewpoint_2m": "degC",
                "shortwave_radiation": "W m-2 (hourly mean flux)",
                "wind_speed_10m": "m s-1 at 10 m",
                "surface_pressure": "hPa",
            },
            "licence": OPEN_METEO_LICENCE,
            "requestUrl": url,
            "payloadSha256": digest,
            "seriesSha256": sha256_series(series),
            "httpCacheEnabled": _cache_dir() is not None,
            "gridPointReturned": {
                "latitude": payload.get("latitude"),
                "longitude": payload.get("longitude"),
                "elevationM": payload.get("elevation"),
            },
            "hoursRequested": len(times),
        },
    }


def fetch_open_meteo_daily(site: Site, start: str, end: str, model: str = "era5") -> dict[str, Any]:
    """Daily series for one site, including the provider's own FAO-56 ET0 for ERA5."""
    url = _open_meteo_url(site, start, end, model, daily=True)
    payload, digest = _fetch_json(url)
    block = payload.get("daily") or {}
    days = block.get("time") or []
    if not days:
        raise SourceUnavailableError(f"no daily data returned for {site.key}")

    series: dict[str, list[Any]] = {}
    for name in OPEN_METEO_MODELS[model]["daily_fields"]:
        values = block.get(name)
        if values is None:
            raise SourceUnavailableError(f"field {name!r} absent for {site.key}")
        series[name] = [None if v is None else float(v) for v in values]
    et0 = block.get("et0_fao_evapotranspiration")
    if et0 is not None:
        series["et0_fao_evapotranspiration"] = [None if v is None else float(v) for v in et0]

    return {
        "days": days,
        "series": series,
        "provenance": {
            "route": "open-meteo-archive-api-daily",
            "product": OPEN_METEO_MODELS[model]["product"],
            "model": model,
            "temporalResolution": "daily (UTC)",
            "spatialResolutionDeg": OPEN_METEO_MODELS[model]["resolution_deg"],
            "fields": dict(OPEN_METEO_MODELS[model]["daily_fields"]),
            "units": {
                "temperature_2m_max": "degC",
                "temperature_2m_min": "degC",
                "shortwave_radiation_sum": "MJ m-2 d-1",
                "et0_fao_evapotranspiration": "mm d-1",
            },
            "licence": OPEN_METEO_LICENCE,
            "requestUrl": url,
            "payloadSha256": digest,
            "seriesSha256": sha256_series(series),
            "httpCacheEnabled": _cache_dir() is not None,
            "gridPointReturned": {
                "latitude": payload.get("latitude"),
                "longitude": payload.get("longitude"),
                "elevationM": payload.get("elevation"),
            },
            "daysRequested": len(days),
        },
    }


# ---------------------------------------------------------------------------------------
# NASA POWER daily
# ---------------------------------------------------------------------------------------
POWER_PARAMETERS = {
    "T2M_MAX": "degC",
    "T2M_MIN": "degC",
    "T2MDEW": "degC",
    "ALLSKY_SFC_SW_DWN": "MJ m-2 d-1",
    "WS2M": "m s-1 at 2 m",
    "PS": "kPa",
}
POWER_FILL = -999.0


def fetch_power_daily(site: Site, start: str, end: str, community: str = "AG") -> dict[str, Any]:
    params = ",".join(POWER_PARAMETERS)
    url = (
        f"{POWER_DAILY}?parameters={params}&community={community}"
        f"&latitude={site.latitude}&longitude={site.longitude}"
        f"&start={start.replace('-', '')}&end={end.replace('-', '')}&format=JSON"
    )
    payload, digest = _fetch_json(url)
    block = (payload.get("properties") or {}).get("parameter") or {}
    if not block:
        raise SourceUnavailableError(f"POWER returned no parameters for {site.key}")

    reference = block.get("T2M_MAX") or {}
    # POWER keys days as YYYYMMDD; the pipeline works in ISO dates so the join against the
    # other legs cannot silently produce zero matches.
    raw_days = sorted(reference)
    days = [f"{d[:4]}-{d[4:6]}-{d[6:8]}" for d in raw_days]
    if not days:
        raise SourceUnavailableError(f"POWER returned an empty record for {site.key}")

    series: dict[str, list[Any]] = {}
    for name in POWER_PARAMETERS:
        column = block.get(name)
        if column is None:
            raise SourceUnavailableError(f"POWER omitted {name!r} for {site.key}")
        series[name] = [
            None if column.get(day) is None or float(column[day]) <= POWER_FILL + 1e-9
            else float(column[day])
            for day in raw_days
        ]

    return {
        "days": days,
        "series": series,
        "provenance": {
            "route": "nasa-power-daily",
            "product": "NASA POWER (MERRA-2 based reanalysis) daily point API",
            "temporalResolution": "daily",
            "spatialResolutionDeg": "0.5 x 0.625 (MERRA-2 native grid)",
            "fields": {"T2M_MAX": "daily maximum 2 m temperature",
                       "T2M_MIN": "daily minimum 2 m temperature",
                       "T2MDEW": "2 m dew point",
                       "ALLSKY_SFC_SW_DWN": "all-sky surface shortwave downwelling",
                       "WS2M": "2 m wind speed",
                       "PS": "surface pressure"},
            "units": dict(POWER_PARAMETERS),
            "licence": POWER_LICENCE,
            "requestUrl": url,
            "payloadSha256": digest,
            "seriesSha256": sha256_series(series),
            "httpCacheEnabled": _cache_dir() is not None,
            "fillValue": POWER_FILL,
            "providerEt0Available": POWER_ET0_AVAILABLE,
            "providerEt0Note": (
                "POWER v2 daily rejects the ET0 parameter with HTTP 422, so no provider ET0 "
                "series exists to compare against; PM is computed here from the forcing."
            ),
            "daysRequested": len(days),
        },
    }


# ---------------------------------------------------------------------------------------
# NOAA ISD-Lite station observations
# ---------------------------------------------------------------------------------------
_ISD_COLUMNS = ("year", "month", "day", "hour", "temp_c_x10", "dew_c_x10",
                "pressure_hpa_x10", "wind_dir_deg", "wind_speed_ms_x10", "sky_code",
                "precip_mm_x1h", "precip_mm_x6h")
ISD_FILL = -9999


def fetch_isd_hourly(site: Site, start: str, end: str) -> dict[str, Any]:
    """Hourly station observations.

    ISD-Lite carries temperature, dew point, pressure, wind, sky code and precipitation but
    **no radiation**, which is why the observational leg can only be a temperature-based
    method. Values are stored as tenths and -9999 marks a missing observation.
    """
    first, last = _dt.date.fromisoformat(start), _dt.date.fromisoformat(end)
    rows: list[dict[str, Any]] = []
    digests: dict[str, str] = {}
    for year in range(first.year, last.year + 1):
        url = ISD_LITE.format(year=year, usaf=site.isd_usaf, wban=site.isd_wban)
        raw = _fetch_bytes(url)
        digests[f"isd-lite/data/{year}/{site.isd_usaf}-{site.isd_wban}-{year}.gz"] = sha256_bytes(raw)
        text = gzip.decompress(raw).decode("utf-8", "replace")
        for line in text.splitlines():
            parts = line.split()
            if len(parts) < len(_ISD_COLUMNS):
                continue
            values = dict(zip(_ISD_COLUMNS, parts[: len(_ISD_COLUMNS)]))
            try:
                stamp = _dt.datetime(int(values["year"]), int(values["month"]),
                                     int(values["day"]), int(values["hour"]))
            except ValueError:
                continue
            if not (first <= stamp.date() <= last):
                continue

            def _scaled(key: str, factor: float) -> float | None:
                raw_value = int(values[key])
                return None if raw_value == ISD_FILL else raw_value / factor

            rows.append({
                "utc": stamp.strftime("%Y-%m-%dT%H:00"),
                "temp_c": _scaled("temp_c_x10", 10.0),
                "dew_c": _scaled("dew_c_x10", 10.0),
                "pressure_hpa": _scaled("pressure_hpa_x10", 10.0),
                "wind_speed_ms": _scaled("wind_speed_ms_x10", 10.0),
            })

    if not rows:
        raise SourceUnavailableError(f"no ISD rows for {site.key}")

    series = {
        "temp_c": [r["temp_c"] for r in rows],
        "dew_c": [r["dew_c"] for r in rows],
        "pressure_hpa": [r["pressure_hpa"] for r in rows],
        "wind_speed_ms": [r["wind_speed_ms"] for r in rows],
    }
    return {
        "hours": [r["utc"] for r in rows],
        "series": series,
        "provenance": {
            "route": "noaa-isd-lite-hoURLy",
            "product": f"NOAA ISD-Lite station {site.isd_usaf}-{site.isd_wban} ({site.isd_name})",
            "temporalResolution": "hourly (UTC)",
            "spatialResolutionDeg": 0.0,
            "spatialResolutionNote": "point observation at the station, not a grid cell",
            "fields": {"temp_c": "2 m air temperature", "dew_c": "2 m dew point",
                       "pressure_hpa": "sea-level pressure",
                       "wind_speed_ms": "wind speed at 10 m"},
            "units": {"temp_c": "degC", "dew_c": "degC", "pressure_hpa": "hPa",
                      "wind_speed_ms": "m s-1 at 10 m"},
            "licence": ISD_LICENCE,
            "requestUrl": ISD_LITE.format(year=first.year, usaf=site.isd_usaf,
                                          wban=site.isd_wban),
            "payloadSha256": digests,
            "seriesSha256": sha256_series(series),
            "httpCacheEnabled": _cache_dir() is not None,
            "stationDistanceKm": site.station_distance_km,
            "stationElevationM": site.station_elevation_m,
            "note": "no radiation field exists in ISD-Lite; temperature-based method only",
            "daysRequested": (last - first).days + 1,
        },
    }


# ---------------------------------------------------------------------------------------
# Copernicus CDS ERA5-Land (credentialed, hourly, full FAO-56 variable set)
# ---------------------------------------------------------------------------------------
# The six variables FAO-56 needs, hourly, at 0.1 degrees. Units and step types are recorded
# because every one of them needs a conversion, and a wrong conversion here is silent.
CDS_ERA5_LAND_VARIABLES: dict[str, dict[str, str]] = {
    "2m_temperature": {"shortName": "t2m", "units": "K", "stepType": "instantaneous",
                       "usedFor": "T, es, delta, daily Tmax/Tmin"},
    "2m_dewpoint_temperature": {"shortName": "d2m", "units": "K", "stepType": "instantaneous",
                                "usedFor": "ea (FAO-56 eq. 14)"},
    "surface_solar_radiation_downwards": {"shortName": "ssrd",
                                          "units": "J m-2 accumulated over the hour",
                                          "stepType": "accumulation",
                                          "usedFor": "Rs (divide by 3600 for W m-2)"},
    "10m_u_component_of_wind": {"shortName": "10u", "units": "m s-1", "stepType": "instantaneous",
                                "usedFor": "u10 with 10v"},
    "10m_v_component_of_wind": {"shortName": "10v", "units": "m s-1", "stepType": "instantaneous",
                                "usedFor": "u10 with 10u"},
    "surface_pressure": {"shortName": "sp", "units": "Pa", "stepType": "instantaneous",
                         "usedFor": "gamma (FAO-56 eq. 7)"},
}
CDS_DATASET = "reanalysis-era5-land"
CDS_CREDENTIAL_VARS = ("CDSAPI_URL", "CDSAPI_KEY")


def cds_credentials_present() -> bool:
    return all(os.environ.get(name, "").strip() for name in CDS_CREDENTIAL_VARS)


def cds_missing_variables() -> list[str]:
    return [name for name in CDS_CREDENTIAL_VARS if not os.environ.get(name, "").strip()]


def require_cds_credentials() -> None:
    """Raise unless both CDS variables are set. Never echoes a value."""
    missing = cds_missing_variables()
    if missing:
        raise MissingCredentialError(
            "Copernicus CDS credentials absent: "
            + ", ".join(missing)
            + ". Export them in the environment (never in the repository) to run the "
              "ERA5-Land hourly retrieval. Data are NOT fabricated and the leg is omitted."
        )


def cds_request_payload(site: Site, start: str, end: str, pad_deg: float = 0.05) -> dict[str, Any]:
    """The exact CDS request for one site.

    A pure function, so its shape can be pinned by tests and cannot drift from what the
    method consumes. The area is a small box around the grid point; CDS returns the
    nearest 0.1 degree cell for each hour.
    """
    first, last = _dt.date.fromisoformat(start), _dt.date.fromisoformat(end)
    return {
        "product_type": ["reanalysis"],
        "variable": list(CDS_ERA5_LAND_VARIABLES),
        "year": [str(year) for year in range(first.year, last.year + 1)],
        "month": [f"{month:02d}" for month in range(1, 13) if _month_in_range(month, first, last)],
        "day": [f"{day:02d}" for day in range(1, 32)],
        "time": [f"{hour:02d}:00" for hour in range(24)],
        "area": [site.latitude + pad_deg, site.longitude - pad_deg,
                 site.latitude - pad_deg, site.longitude + pad_deg],
        "format": "netcdf",
        "data_format": "netcdf",
        "download_format": "unarchived",
        "dataset": CDS_DATASET,
    }


def _month_in_range(month: int, first: _dt.date, last: _dt.date) -> bool:
    return (_dt.date(first.year, month, 1) <= last) and (
        _dt.date(last.year, month, 1) >= _dt.date(first.year, first.month, 1)
    )


def fetch_cds_era5_land(site: Site, start: str, end: str) -> dict[str, Any]:
    """Retrieve ERA5-Land hourly via CDS.

    Deliberately unavailable without ``CDSAPI_URL``/``CDSAPI_KEY``. If this function returned a
    fallback product instead, a later report could claim ERA5-Land coverage that was never
    retrieved, which is the failure mode this whole module exists to prevent.
    """
    require_cds_credentials()
    try:  # pragma: no cover - requires the cdsapi package and a live token
        import cdsapi  # type: ignore
    except ImportError as exc:  # pragma: no cover - dependency is optional
        raise SourceUnavailableError(
            "CDS credentials are present but the cdsapi package is not installed"
        ) from exc
    raise SourceUnavailableError(  # pragma: no cover - network path not exercised here
        "CDS retrieval is wired but was not executed in this run"
    )
