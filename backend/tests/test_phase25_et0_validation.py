"""Phase 25: the independent ET0 validation pipeline.

Three groups of assertions:

* the credentialed ERA5-Land route is impossible to run without credentials and impossible to
  fake - it raises, names the variables, and writes nothing;
* the parts that can be verified without a live CDS token (NetCDF parsing, unit conversions,
  radiation energy balance) are verified against synthetic files carrying the real CDS names;
* the equation, the scoring and the recorded artefacts are checked for the defects this pipeline
  has actually produced in the past.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
for extra in (REPO_ROOT, REPO_ROOT / "backend"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from scripts.et0_validation import era5_land, methods, scoring, sources  # noqa: E402

ARTEFACTS = REPO_ROOT / "data" / "validation" / "et0"
SUMMARY = ARTEFACTS / "validation_summary.json"
HARMONISED = ARTEFACTS / "harmonised_daily.csv"
ATTRIBUTION = ARTEFACTS / "attribution.json"


def _write_netcdf(path, *, hours=24, temperature_k=290.0, dewpoint_k=283.0,
                  ssrd_j=1_200_000.0, u10=3.0, v10=1.0, pressure_pa=95_000.0,
                  drop=(), longitude=90.41):
    """Write a CDS-shaped NetCDF3 file with real short names and step types."""
    from scipy.io import netcdf_file

    handle = netcdf_file(str(path), "w")
    handle.createDimension("time", hours)
    handle.createDimension("latitude", 1)
    handle.createDimension("longitude", 1)

    time = handle.createVariable("time", "i4", ("time",))
    time.units = b"hours since 2021-01-01 00:00:00"
    time[:] = np.arange(hours, dtype="int32")

    lat = handle.createVariable("latitude", "f8", ("latitude",))
    lat[:] = [23.8]
    lon = handle.createVariable("longitude", "f8", ("longitude",))
    lon[:] = [longitude]

    fields = {
        "t2m": (temperature_k, "K"),
        "d2m": (dewpoint_k, "K"),
        "ssrd": (ssrd_j, "J m-2"),
        "10u": (u10, "m s-1"),
        "10v": (v10, "m s-1"),
        "sp": (pressure_pa, "Pa"),
    }
    for name, (value, units) in fields.items():
        if name in drop:
            continue
        variable = handle.createVariable(name, "f8", ("time", "latitude", "longitude"))
        variable.units = units.encode()
        variable[:] = np.full((hours, 1, 1), value, dtype="float64")
    handle.close()
    return path


@pytest.fixture()
def netcdf_file(tmp_path):
    return _write_netcdf(tmp_path / "era5_land.nc")


# ---------------------------------------------------------------------------------------
# The credential gate
# ---------------------------------------------------------------------------------------


def test_credentials_absent_for_an_empty_environment(monkeypatch):
    for name in sources.CDS_CREDENTIAL_VARS:
        monkeypatch.delenv(name, raising=False)
    assert sources.cds_credentials_present() is False
    assert set(sources.cds_missing_variables()) == {"CDSAPI_URL", "CDSAPI_KEY"}


def test_both_credential_variables_are_required(monkeypatch):
    monkeypatch.setenv("CDSAPI_URL", "https://cds.climate.copernicus.eu/api")
    monkeypatch.delenv("CDSAPI_KEY", raising=False)
    assert sources.cds_credentials_present() is False
    assert sources.cds_missing_variables() == ["CDSAPI_KEY"]


def test_blank_values_do_not_count_as_credentials(monkeypatch):
    monkeypatch.setenv("CDSAPI_URL", "   ")
    monkeypatch.setenv("CDSAPI_KEY", "")
    assert sources.cds_credentials_present() is False


def test_cds_route_fails_explicitly_without_credentials(monkeypatch):
    for name in sources.CDS_CREDENTIAL_VARS:
        monkeypatch.delenv(name, raising=False)
    site = sources.site_by_key("dhaka_bd")
    with pytest.raises(sources.MissingCredentialError) as excinfo:
        sources.fetch_cds_era5_land(site, "2021-01-01", "2021-01-02")
    message = str(excinfo.value)
    assert "CDSAPI_URL" in message and "CDSAPI_KEY" in message
    assert "NOT fabricated" in message


def test_missing_credential_error_does_not_echo_a_value(monkeypatch):
    monkeypatch.setenv("CDSAPI_URL", "https://cds.climate.copernicus.eu/api")
    monkeypatch.setenv("CDSAPI_KEY", "secret-token-value")
    monkeypatch.delenv("CDSAPI_URL")
    with pytest.raises(sources.MissingCredentialError) as excinfo:
        sources.require_cds_credentials()
    assert "secret-token-value" not in str(excinfo.value)


# ---------------------------------------------------------------------------------------
# The request that would be made
# ---------------------------------------------------------------------------------------


def test_request_asks_for_exactly_the_fao56_variables():
    payload = sources.cds_request_payload(sources.site_by_key("tucson_us"),
                                          "2021-01-01", "2021-01-31")
    assert set(payload["variable"]) == {
        "2m_temperature", "2m_dewpoint_temperature", "surface_solar_radiation_downwards",
        "10m_u_component_of_wind", "10m_v_component_of_wind", "surface_pressure",
    }


def test_every_variable_declares_units_and_step_type():
    for name, spec in sources.CDS_ERA5_LAND_VARIABLES.items():
        assert spec["units"], name
        assert spec["stepType"] in ("instantaneous", "accumulation"), name
        assert spec["shortName"], name


def test_radiation_is_declared_as_an_accumulation_in_joules():
    spec = sources.CDS_ERA5_LAND_VARIABLES["surface_solar_radiation_downwards"]
    assert spec["stepType"] == "accumulation"
    assert "J m-2" in spec["units"]


def test_request_is_hourly_and_covers_the_window():
    payload = sources.cds_request_payload(sources.site_by_key("dhaka_bd"),
                                          "2021-01-01", "2023-12-31")
    assert payload["dataset"] == "reanalysis-era5-land"
    assert len(payload["time"]) == 24
    assert payload["year"] == ["2021", "2022", "2023"]
    assert payload["format"] == "netcdf"


def test_request_area_is_a_small_box_around_the_site():
    site = sources.site_by_key("reykjavik_is")
    payload = sources.cds_request_payload(site, "2021-01-01", "2021-01-02")
    north, west, south, east = payload["area"]
    assert north > site.latitude > south
    assert east > site.longitude > west
    assert north - south < 0.5


# ---------------------------------------------------------------------------------------
# NetCDF reading: every conversion, on a file with the real names
# ---------------------------------------------------------------------------------------


def test_kelvin_is_converted_to_celsius(netcdf_file):
    payload = era5_land.hourly_series_from_netcdf(netcdf_file)
    assert payload["series"]["temperature_2m"][0] == pytest.approx(290.0 - 273.15)
    assert payload["series"]["dewpoint_2m"][0] == pytest.approx(283.0 - 273.15)


def test_pascals_are_converted_to_hectopascals(netcdf_file):
    payload = era5_land.hourly_series_from_netcdf(netcdf_file)
    assert payload["series"]["surface_pressure"][0] == pytest.approx(950.0)


def test_accumulated_radiation_is_converted_to_a_flux(netcdf_file):
    payload = era5_land.hourly_series_from_netcdf(netcdf_file)
    assert payload["series"]["shortwave_radiation"][0] == pytest.approx(1_200_000 / 3600)


def test_wind_components_become_a_speed(netcdf_file):
    payload = era5_land.hourly_series_from_netcdf(netcdf_file)
    assert payload["series"]["wind_speed_10m"][0] == pytest.approx(math.hypot(3.0, 1.0))


def test_missing_variable_is_named_in_the_error(tmp_path):
    path = _write_netcdf(tmp_path / "incomplete.nc", drop=("ssrd",))
    with pytest.raises(era5_land.Era5LandFileError) as excinfo:
        era5_land.hourly_series_from_netcdf(path)
    message = str(excinfo.value)
    assert "'ssrd'" in message
    assert "t2m" in message  # it says what the file does contain


def test_zero_to_360_longitudes_are_normalised(tmp_path):
    path = _write_netcdf(tmp_path / "west.nc", longitude=249.05)
    payload = era5_land.hourly_series_from_netcdf(path)
    assert payload["gridPoint"]["longitude"] == pytest.approx(-110.95)


def test_non_finite_temperature_is_rejected(tmp_path):
    path = _write_netcdf(tmp_path / "nan.nc", temperature_k=float("nan"))
    with pytest.raises(era5_land.Era5LandFileError):
        era5_land.hourly_series_from_netcdf(path)


def test_hours_are_parsed_from_the_time_units(netcdf_file):
    payload = era5_land.hourly_series_from_netcdf(netcdf_file)
    assert payload["hours"][0] == "2021-01-01T00:00"
    assert len(payload["hours"]) == 24


def test_conversions_are_declared_in_the_payload(netcdf_file):
    payload = era5_land.hourly_series_from_netcdf(netcdf_file)
    assert "3600" in payload["conversions"]["ssrd"]
    assert "273.15" in payload["conversions"]["t2m"]


# ---------------------------------------------------------------------------------------
# Radiation energy balance: both directions of the factor-of-3600 error
# ---------------------------------------------------------------------------------------


def test_plausible_daily_radiation_passes_the_energy_check():
    days = ["2021-06-01", "2021-06-02"]
    check = era5_land.radiation_energy_check({"2021-06-01": 20.0, "2021-06-02": 18.0},
                                             {"2021-06-01": 41.0, "2021-06-02": 40.0})
    assert check["ok"] is True
    assert check["daysChecked"] == 2
    assert len(days) == 2


def test_over_divided_radiation_is_caught_by_the_energy_check():
    """A missed division looks impossible; an *over*-division looks like permanent overcast."""
    check = era5_land.radiation_energy_check({"2021-06-01": 0.4}, {"2021-06-01": 41.0})
    assert check["ok"] is False
    assert check["implausibleDayCount"] == 1


def test_un_divided_radiation_is_caught_by_the_energy_check():
    check = era5_land.radiation_energy_check({"2021-06-01": 1_440.0}, {"2021-06-01": 41.0})
    assert check["ok"] is False


# ---------------------------------------------------------------------------------------
# The hourly equation and its known defects
# ---------------------------------------------------------------------------------------


def test_hourly_ra_sums_to_the_daily_ra():
    """The defect this guards: reusing the daily bracket per hour drives Ra negative."""
    latitude, day = 32.28, 172
    daily_ra, _ = methods.extraterrestrial_radiation(latitude, day)
    total = sum(
        methods.hourly_extraterrestrial_radiation(latitude, day, hour + 0.5)
        for hour in range(24)
    )
    assert total == pytest.approx(daily_ra, rel=0.02)


def test_afternoon_hourly_ra_is_not_negative():
    for hour in range(24):
        assert methods.hourly_extraterrestrial_radiation(32.28, 172, hour + 0.5) >= 0.0


def test_hourly_stefan_boltzmann_is_the_daily_constant_divided_by_24():
    assert methods.STEFAN_BOLTZMANN_HOURLY == pytest.approx(methods.STEFAN_BOLTZMANN / 24.0)


def test_pressure_units_change_the_result_by_the_expected_factor():
    """hPa passed where kPa is expected inflates gamma tenfold - this is that defect's test."""
    common = dict(temperature_c=30.0, dewpoint_c=10.0, rs_w_m2=700.0, wind_10m_ms=3.0,
                  latitude_deg=32.28, longitude_deg=-110.95, day_of_year=180, hour_utc=12,
                  elevation_m=824.0)
    right = methods.hourly_et0(pressure_kpa=93.0, **common)["et0Mm"]
    wrong = methods.hourly_et0(pressure_kpa=930.0, **common)["et0Mm"]
    assert right > 0
    assert wrong != right
    assert abs(wrong) < abs(right)  # an inflated gamma suppresses the radiation term


def test_hourly_terms_add_up_to_the_hourly_total():
    hour = methods.hourly_et0(temperature_c=25.0, dewpoint_c=15.0, rs_w_m2=600.0,
                              wind_10m_ms=2.0, pressure_kpa=100.0, latitude_deg=23.81,
                              longitude_deg=90.41, day_of_year=200, hour_utc=6,
                              elevation_m=9.0)
    assert hour["radiationTermMm"] + hour["aeroTermMm"] == pytest.approx(hour["et0Mm"])


def test_daylight_is_decided_by_radiation_not_by_clock_time():
    """At 68 N in June the sun is up at midnight; at 23.8 N it is not.

    Reykjavik at 64.13 N is deliberately *not* used: it sits just south of the Arctic
    Circle, so its solar-midnight altitude is about -2.4 deg and it has no true midnight sun.
    """
    tromso = methods.hourly_et0(temperature_c=10.0, dewpoint_c=8.0, rs_w_m2=20.0,
                                wind_10m_ms=4.0, pressure_kpa=101.0, latitude_deg=69.65,
                                longitude_deg=18.96, day_of_year=172, hour_utc=0,
                                elevation_m=53.0)
    # 00:00 UTC is 06:00 local solar time in Dhaka, so the night hour there is 18:00 UTC -
    # the longitude shift is exactly what makes this test meaningful.
    dhaka = methods.hourly_et0(temperature_c=28.0, dewpoint_c=26.0, rs_w_m2=0.0,
                               wind_10m_ms=2.0, pressure_kpa=100.5, latitude_deg=23.81,
                               longitude_deg=90.41, day_of_year=172, hour_utc=18,
                               elevation_m=9.0)
    assert tromso["daylight"] == 1.0
    assert dhaka["daylight"] == 0.0


def test_wind_height_conversion_uses_fao56_equation_47():
    assert methods.wind_at_2m(3.0, measurement_height_m=10.0) == pytest.approx(
        3.0 * 4.87 / math.log(67.8 * 10 - 5.42))
    assert methods.wind_at_2m(3.0, measurement_height_m=2.0) == 3.0


def test_u2_override_replaces_the_converted_wind():
    common = dict(temperature_c=25.0, dewpoint_c=12.0, rs_w_m2=500.0, wind_10m_ms=4.0,
                  pressure_kpa=100.0, latitude_deg=32.28, longitude_deg=-110.95,
                  day_of_year=180, hour_utc=10, elevation_m=824.0)
    natural = methods.hourly_et0(**common)
    zeroed = methods.hourly_et0(u2_override=0.0, **common)
    pinned = methods.hourly_et0(u2_override=2.0, **common)
    assert zeroed["u2"] == 0.0 and pinned["u2"] == 2.0
    assert natural["u2"] == pytest.approx(methods.wind_at_2m(4.0, measurement_height_m=10.0))
    # 4 m/s at 10 m is 2.99 m/s at 2 m, so pinning 2.0 m/s must lower ET0 relative to the
    # honest conversion - the point of the sensitivity legs.
    assert natural["u2"] > 2.0
    assert zeroed["et0Mm"] < pinned["et0Mm"] < natural["et0Mm"]


def test_daily_equation_reproduces_the_published_example():
    """FAO-56 Example 17: 5.72 mm/day. A unit slip anywhere in the chain breaks this."""
    # FAO-56 Example 17 (Bangkok, April): Tmax 34.8, Tmin 25.6, RHmean 66 %, u2 2.0,
    # Rs 22.65 MJ m-2 d-1; published ET0 5.72 and the module lands on 5.77.
    result = methods.daily_et0(tmax=34.8, tmin=25.6, ea_kpa=2.833, rs_mj=22.65,
                               wind_2m_ms=2.0, pressure_kpa=101.3, day_of_year=105,
                               latitude_deg=13.73, elevation_m=2.0)
    assert result["et0MmPerDay"] == pytest.approx(5.77, abs=0.05)


def test_hargreaves_reproduces_the_published_example():
    """FAO-56 Example 20: 5.0 mm/day computed, from temperature and latitude only."""
    # FAO-56 Example 20 (Lyon, July): Tmax 26.6, Tmin 14.8, published ET0 5.0.
    value = methods.hargreaves_for_day(tmax=26.6, tmin=14.8, latitude_deg=45.72,
                                       day_of_year=196)
    assert value == pytest.approx(5.03, abs=0.05)


def test_a_partial_day_is_dropped_rather_than_summed():
    """A 20-hour sum silently understates ET0, which is worse than a missing value."""
    site = sources.site_by_key("dhaka_bd")
    hours = [f"2021-06-01T{h:02d}:00" for h in range(20)]
    payload = {"hours": hours, "series": {
        "temperature_2m": [28.0] * 20, "dewpoint_2m": [26.0] * 20,
        "shortwave_radiation": [0.0] * 20, "wind_speed_10m": [2.0] * 20,
        "surface_pressure": [1005.0] * 20,
    }}
    assert methods.hourly_series_to_daily(payload, site) == {}


def test_isd_day_needs_eighteen_hours_of_temperature():
    site = sources.site_by_key("tucson_us")
    stamps = [f"2021-06-01T{h:02d}:00" for h in range(24)]
    short = {"hours": stamps, "series": {"temp_c": [20.0] * 17 + [None] * 7,
                                         "dew_c": [5.0] * 24,
                                         "pressure_hpa": [920.0] * 24,
                                         "wind_speed_ms": [3.0] * 24}}
    full = {"hours": stamps, "series": {"temp_c": [20.0] * 18 + [None] * 6,
                                        "dew_c": [5.0] * 24,
                                        "pressure_hpa": [920.0] * 24,
                                        "wind_speed_ms": [3.0] * 24}}
    assert methods.isd_daily_temperature(short, site) == {}
    assert "2021-06-01" in methods.isd_daily_temperature(full, site)


# ---------------------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------------------


def test_paired_metrics_on_a_known_answer():
    result = scoring.paired([1.0, 2.0, 3.0], [1.0, 2.0, 4.0])
    assert result["n"] == 3
    assert result["mae"] == pytest.approx(1.0 / 3.0)
    assert result["bias"] == pytest.approx(-1.0 / 3.0)
    assert result["rmse"] == pytest.approx(math.sqrt(1.0 / 3.0))


def test_paired_drops_missing_pairs_instead_of_zero_filling():
    """One usable pair cannot support a correlation, so no metric block is returned."""
    assert scoring.paired([1.0, None, 3.0], [1.0, 5.0, None]) is None
    assert scoring.paired([1.0, 2.0, None], [1.0, 2.0, 9.0])["n"] == 2


def test_r2_is_the_squared_correlation_and_slope_is_separate():
    predicted = [1.0, 2.0, 3.0, 4.0]
    reference = [2.0, 4.0, 6.0, 8.0]
    result = scoring.paired(predicted, reference)
    assert result["r2"] == pytest.approx(1.0)
    assert result["slope"] == pytest.approx(0.5)


def test_percent_error_is_refused_near_zero():
    """Reykjavik produced 19 462 % from a 0.02 mm/d denominator; that number means nothing."""
    assert scoring.mean_error_percent([1.0, 1.0], [0.0, 0.02]) is None
    assert scoring.mean_error_percent([1.1], [1.0]) == pytest.approx(10.0)


def test_missingness_reports_the_longest_run():
    result = scoring.missingness([1.0, None, None, 2.0, None])
    assert result["missing"] == 3
    assert result["longestRun"] == 2
    assert result["fraction"] == pytest.approx(0.6)


def test_percentile_interpolates():
    assert scoring._percentile([1.0, 2.0, 3.0], 0.5) == pytest.approx(2.0)
    assert scoring._percentile([], 0.95) is None


# ---------------------------------------------------------------------------------------
# Provenance digests, retries and the optional cache
# ---------------------------------------------------------------------------------------


def test_series_digest_ignores_field_order_and_float_noise():
    a = {"t": [1.0, 2.5], "rh": [80.0, None]}
    b = {"rh": [80.0, None], "t": [1.0, 2.5]}
    c = {"t": [1.0, 2.5000000001], "rh": [80.0, None]}
    assert sources.sha256_series(a) == sources.sha256_series(b)
    assert sources.sha256_series(a) == sources.sha256_series(c)


def test_series_digest_still_catches_a_real_change():
    base = {"t": [1.0, 2.0, 3.0]}
    assert sources.sha256_series(base) != sources.sha256_series({"t": [1.0, 2.0, 3.1]})
    assert sources.sha256_series(base) != sources.sha256_series({"t": [1.0, 2.0, None]})


def test_backoff_grows_and_honours_retry_after():
    assert sources.backoff_seconds(0) == 1.5
    assert sources.backoff_seconds(2) == 6.0
    assert sources.backoff_seconds(0, retry_after=7) == 7.0
    assert sources.backoff_seconds(0, retry_after=10_000) == 120.0


def test_cache_is_off_unless_the_environment_asks_for_it(monkeypatch):
    monkeypatch.delenv(sources.CACHE_ENV_VAR, raising=False)
    assert sources._cache_dir() is None


def test_cached_payload_is_replayed_without_a_request(monkeypatch, tmp_path):
    monkeypatch.setenv(sources.CACHE_ENV_VAR, str(tmp_path))
    url = "https://example.invalid/archive?site=test"
    payload = b'{"hourly": {"time": ["2021-01-01T00"]}}'
    (tmp_path / (sources.sha256_bytes(url.encode("utf-8")) + ".payload")).write_bytes(payload)

    def _explode(*args, **kwargs):  # pragma: no cover - must not be reached
        raise AssertionError("network must not be used for a cache hit")

    monkeypatch.setattr(sources.urllib.request, "urlopen", _explode)
    assert sources._fetch_bytes(url) == payload


def test_client_errors_are_not_retried(monkeypatch):
    monkeypatch.delenv(sources.CACHE_ENV_VAR, raising=False)
    calls = []

    def _fail(request, timeout=None):
        calls.append(request.full_url)
        raise sources.urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)

    monkeypatch.setattr(sources.urllib.request, "urlopen", _fail)
    with pytest.raises(sources.SourceUnavailableError):
        sources._fetch_bytes("https://example.invalid/missing")
    assert len(calls) == 1


def test_power_fill_values_become_missing_not_negative_numbers():
    assert sources.POWER_FILL == -999.0
    assert sources.POWER_ET0_AVAILABLE is False


# ---------------------------------------------------------------------------------------
# The recorded artefacts
# ---------------------------------------------------------------------------------------


def test_artefacts_exist():
    assert HARMONISED.is_file() and SUMMARY.is_file() and ATTRIBUTION.is_file()


def test_harmonised_table_has_one_row_per_site_day():
    with HARMONISED.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 6570
    assert len({row["site"] for row in rows}) == 6
    assert len({(row["site"], row["date"]) for row in rows}) == 6570


def test_era5_land_cds_column_is_empty_everywhere():
    """The route never ran. A single number here would be a fabrication."""
    with HARMONISED.open(newline="", encoding="utf-8") as handle:
        values = [row["era5_land_cds_pm_mm"] for row in csv.DictReader(handle)]
    assert set(values) == {""}


def test_summary_records_the_cds_route_as_not_run():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    routes = summary["provenance"]["routesNotRun"]
    assert "copernicus-cds-era5-land" in routes
    entry = routes["copernicus-cds-era5-land"]
    assert entry["status"] == "not-run"
    assert entry["missingEnvironmentVariables"] == ["CDSAPI_URL", "CDSAPI_KEY"]
    assert summary["provenance"]["cdsCredentialPresent"] is False


def test_cds_comparisons_report_no_leg_rather_than_a_number():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    for comparison_id in ("era5_land_cds_pm_vs_om_et0_era5",
                          "era5_land_cds_pm_vs_power_daily_pm"):
        block = summary["comparisons"][comparison_id]
        assert block["pooled"] is None
        assert "no leg available" in block["status"]


def test_every_comparison_is_recorded_with_its_purpose():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert len(summary["comparisons"]) == 14
    for block in summary["comparisons"].values():
        assert block["description"]
        assert block["left"] and block["right"]


def test_implementation_control_agrees_and_forcing_does_not():
    """The headline result: the code agrees, the weather differs."""
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    implementation = summary["comparisons"]["era5_daily_pm_vs_om_et0_era5"]["pooled"]
    forcing = summary["comparisons"]["era5_daily_pm_vs_power_daily_pm"]["pooled"]
    assert abs(implementation["bias"]) < 0.02
    assert implementation["mae"] < 0.3
    assert forcing["mae"] > 0.4


def test_missingness_shows_the_station_leg_and_the_unrun_leg():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    missingness = summary["missingness"]
    assert missingness["era5_land_cds_pm_mm"]["missing"] == 6570
    assert 0 < missingness["isd_hargreaves_mm"]["missing"] < 200


def test_summary_states_what_it_does_not_support():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    limits = " ".join(summary["claims"]["doesNotSupport"]).lower()
    assert "crop water use" in limits
    assert "era5-land fao-56 skill" in limits


def test_attribution_closes_exactly():
    payload = json.loads(ATTRIBUTION.read_text(encoding="utf-8"))
    for site, block in payload["perSite"].items():
        efficiency = block["shapley"]["efficiency"]
        assert abs(efficiency["residual"]) < 5e-3, site


def test_attribution_ranks_a_driver_for_every_site():
    payload = json.loads(ATTRIBUTION.read_text(encoding="utf-8"))
    for site, block in payload["perSite"].items():
        shapley = block["shapley"]
        assert shapley["daysUsed"] > 900, site
        assert shapley["dominantDriver"] in methods_drivers()
        assert 0.0 <= shapley["dominantDriverShare"] <= 1.0


def methods_drivers():
    from scripts.et0_validation.attribute import DRIVERS
    return DRIVERS


def test_elevation_is_excluded_as_an_explanation_everywhere():
    """The measured claim: elevation changes ET0 far less than the site differences."""
    payload = json.loads(ATTRIBUTION.read_text(encoding="utf-8"))
    for site, block in payload["perSite"].items():
        assert block["elevation"]["maxAbsDeltaMm"] < 0.05, site


def test_attribution_admits_it_cannot_crown_a_winner():
    payload = json.loads(ATTRIBUTION.read_text(encoding="utf-8"))
    assert "not which one is closer" in payload["claims"]["doesNotSupport"]
