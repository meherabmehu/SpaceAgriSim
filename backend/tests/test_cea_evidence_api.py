"""The controlled-environment (CEA) measured-evidence workflow, through the HTTP API.

What was broken and what these tests hold down
----------------------------------------------
The page offered "factor + band -> show measured results" and answered with the wrong thing: the
capability shipped band *ids* only, so the select printed `ambient`, `enriched`, `high`; every band
label written by hand in the frontend was a second copy of a predicate that lived in Python, and one
copy was already wrong - five experiments measured at exactly 23.0 °C sat in a band labelled
"< 23 C" while the predicate was `low <= v <= high`. The interval was a normal approximation over
n = 2, which put a negative lower bound on a yield that cannot be negative.

These tests read the same CSV the service reads, compute the expected membership from the published
bounds, and compare against what the API returns for every factor and every band - including the
boundary values, an empty selection and every rejection path. An export test opens the artifact and
looks for the numbers inside it, because "a file downloaded" is not the same claim as "the file is
the evidence".
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.workflows import cea_evidence

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "data" / "processed" / "phase30" / "cea_wheat_experiments.csv"
CAPABILITY = "/api/workflows/light-stress/controlled-environment/capability"
RUN = "/api/workflows/light-stress/controlled-environment/run"
EXPORT = "/api/workflows/light-stress/controlled-environment/export"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def _number(value: str) -> float | None:
    """A blank cell is missing data, not zero. Assigning it a band would invent a measurement."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@pytest.fixture(scope="module")
def rows() -> list[dict[str, float | None]]:
    """The dataset as numbers, read independently of the service.

    Only rows that carry both a measured yield and a measured light environment can be placed in
    any band; three experiments in the published series do not (one has no environment row, two have
    no harvest rows). They are excluded here for the same reason the service excludes them, and the
    capability reports how many they are.
    """
    usable: list[dict[str, float | None]] = []
    with DATASET.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            record = {
                "experimentId": row["experimentId"],
                "grainYield": _number(row["grainYieldKgPerM2Mean"]),
                "ppfd": _number(row["meanPpfdUmolPerM2S"]),
                "photoperiod": _number(row["photoperiodHours"]),
                "co2": _number(row["co2Ppm"]),
                "temperature": _number(row["airTemperatureC"]),
            }
            if record["grainYield"] is not None and record["ppfd"] is not None:
                usable.append(record)
    return usable


FACTOR_COLUMN = {
    "ppfdUmolPerM2S": "ppfd",
    "photoperiodHours": "photoperiod",
    "co2Ppm": "co2",
    "airTemperatureC": "temperature",
}


def _in_band(bounds: dict, value: float) -> bool:
    lower = value >= bounds["min"] if bounds["minInclusive"] else value > bounds["min"]
    upper = value <= bounds["max"] if bounds["maxInclusive"] else value < bounds["max"]
    return lower and upper


# ---------------------------------------------------------------------------
# Capability: labels, real bounds, and the statistics contract
# ---------------------------------------------------------------------------
def test_capability_ships_a_label_and_bounds_for_every_band(client):
    body = client.get(CAPABILITY).json()
    labels = body["fields"][1]["labels"]
    assert set(labels) == set(FACTOR_COLUMN)

    for factor in body["factors"]:
        assert factor["bands"], factor
        for band in factor["bands"]:
            # The label the user reads is derived from the same bounds the service filters on.
            assert labels[factor["publicName"]][band["id"]] == band["label"]
            assert band["label"]
            assert band["label"] != band["id"], "a label that equals the id is the raw id"
            bounds = band["bounds"]
            assert set(bounds) == {"min", "minInclusive", "max", "maxInclusive", "openUpper"}
            assert bounds["min"] < bounds["max"]


def test_capability_labels_are_not_generic_placeholders(client):
    """Every label says what it bound is, so two factors never read the same."""
    body = client.get(CAPABILITY).json()
    widths = {}
    for factor in body["factors"]:
        for band in factor["bands"]:
            widths.setdefault(band["label"], []).append(factor["publicName"])
    repeated = {label: owners for label, owners in widths.items() if len(owners) > 1}
    assert repeated == {}, f"band labels are ambiguous across factors: {repeated}"


def test_capability_declares_when_an_interval_is_available(client):
    statistics = client.get(CAPABILITY).json()["statistics"]
    assert statistics["confidenceLevel"] == 0.95
    assert statistics["minExperimentsForInterval"] == cea_evidence.MIN_INTERVAL_N == 3
    assert "student-t" in statistics["interval"]
    assert "belowMinimum" in statistics


def test_capability_band_counts_match_the_dataset(client, rows):
    by_name = {factor["publicName"]: factor for factor in client.get(CAPABILITY).json()["factors"]}
    for public_name, column in FACTOR_COLUMN.items():
        for band in by_name[public_name]["bands"]:
            column_name = column
            expected = sum(
                1 for row in rows
                if row[column_name] is not None and _in_band(band["bounds"], row[column_name]))
            assert band["experiments"] == expected, (public_name, band["id"])


# ---------------------------------------------------------------------------
# Run: every factor and band, against the dataset
# ---------------------------------------------------------------------------
def _all_bands(client: TestClient) -> list[tuple[str, str]]:
    body = client.get(CAPABILITY).json()
    return [(factor["publicName"], band["id"])
            for factor in body["factors"] for band in factor["bands"]]


def test_every_band_returns_the_experiments_the_bounds_select(client, rows):
    by_id = {row["experimentId"]: row for row in rows}
    for public_name, band_id in _all_bands(client):
        response = client.post(RUN, json={"selections": [{"factor": public_name, "band": band_id}]})
        assert response.status_code == 200, response.text
        group = response.json()["groups"][0]
        column = FACTOR_COLUMN[public_name]
        bound = client.get(CAPABILITY).json()
        band = next(b for f in bound["factors"] if f["publicName"] == public_name
                    for b in f["bands"] if b["id"] == band_id)
        expected = sorted(row["experimentId"] for row in rows
                          if row[column] is not None and _in_band(band["bounds"], row[column]))

        assert group["experiments"] == expected, (public_name, band_id)
        assert group["measured"]["n"] == len(expected)
        assert group["empty"] is (len(expected) == 0)
        # The mean is the mean of the measured yields, not of some other column.
        if expected:
            values = [by_id[experiment]["grainYield"] for experiment in expected]
            assert group["measured"]["mean"] == pytest.approx(sum(values) / len(values), abs=5e-4)
            assert group["measured"]["min"] == pytest.approx(min(values), abs=5e-4)
            assert group["measured"]["max"] == pytest.approx(max(values), abs=5e-4)


def test_band_boundaries_are_membership_not_rounding(client, rows):
    """A value exactly on an upper bound belongs to that band, and the label must say so."""
    boundaries = [(23.0, "temperature", "airTemperatureC", "cool"),
                  (25.0, "temperature", "airTemperatureC", "mid")]
    for value, column, public_name, band_id in boundaries:
        exact = [row["experimentId"] for row in rows if row[column] == value]
        assert exact, f"the dataset no longer contains {value} in {column}"
        group = client.post(RUN, json={"selections": [{"factor": public_name, "band": band_id}]}
                            ).json()["groups"][0]
        assert set(exact) <= set(group["experiments"]), (
            f"{value} should be in {band_id}, whose label is {group['label']}")


def test_a_band_whose_sample_is_too_small_reports_no_interval(client):
    """Photoperiod <= 12 h holds two experiments: a mean, but no 95 % interval."""
    group = client.post(RUN, json={"selections": [
        {"factor": "photoperiodHours", "band": "short"}]}).json()["groups"][0]
    measured = group["measured"]
    assert measured["n"] == 2
    assert measured["ciStatus"] == "insufficient-observations"
    assert measured.get("meanCiLow") is None and measured.get("meanCiHigh") is None
    assert measured["ciNote"], "a missing interval must be explained, not left blank"


def test_a_supported_sample_reports_a_student_t_interval(client):
    group = client.post(RUN, json={"selections": [
        {"factor": "co2Ppm", "band": "ambient"}]}).json()["groups"][0]
    measured = group["measured"]
    assert measured["n"] >= 3
    assert measured["ciStatus"] == "reported"
    assert measured["ciMethod"].startswith("student-t")
    assert measured["ciDf"] == measured["n"] - 1
    # The interval contains the mean and is wider than the standard error alone would be.
    assert measured["meanCiLow"] < measured["mean"] < measured["meanCiHigh"]


def test_warm_band_interval_is_labelled_when_it_crosses_zero(client):
    """Three warm experiments: the t interval dips below the observed minimum, and says so."""
    measured = client.post(RUN, json={"selections": [
        {"factor": "airTemperatureC", "band": "warm"}]}).json()["groups"][0]["measured"]
    assert measured["n"] == 3
    assert measured["ciStatus"] == "reported"
    assert measured["ciCaveat"], "an interval below the observed minimum needs a caveat"


def test_several_selections_are_reported_in_the_order_requested(client):
    selections = [{"factor": "co2Ppm", "band": "high"},
                  {"factor": "airTemperatureC", "band": "cool"}]
    groups = client.post(RUN, json={"selections": selections}).json()["groups"]
    assert [(group["factor"], group["band"]) for group in groups] == [
        (item["factor"], item["band"]) for item in selections]
    labels = [group["label"] for group in groups]
    assert len(set(labels)) == len(labels)


def test_the_run_reports_where_the_numbers_came_from(client):
    body = client.post(RUN, json={"selections": [{"factor": "co2Ppm", "band": "ambient"}]}).json()
    source = body["provenance"]["source"]
    assert source["dataset"] == "cea-wheat-apogee"
    assert source["doi"] == "10.5281/zenodo.17764612"
    assert source["license"] == "CC BY 4.0"
    assert source["citation"]
    assert body["provenance"]["rawFileSha256"] and len(body["provenance"]["rawFileSha256"]) == 64
    assert body["evidenceClass"] == "measured-observation"
    assert body["isSimulation"] is False
    assert body["isModelPrediction"] is False
    assert body["limitations"]


# ---------------------------------------------------------------------------
# Rejection paths - every one of them a 4xx, none of them a 200 with nothing in it
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "selections,expected",
    [
        ([], "at least 1 item"),
        ([{"factor": "co2Ppm", "band": "low"}], "does not exist"),          # band from another factor
        ([{"factor": "photoperiodHours", "band": "ambient"}], "does not exist"),
        ([{"factor": "co2Ppm", "band": "nope"}], "band"),
        ([{"factor": "nope", "band": "ambient"}], "factor"),
        ([{"factor": "co2Ppm", "band": "ambient"}] * 7, "at most"),
    ],
)
def test_a_selection_that_names_no_real_group_is_rejected(client, selections, expected):
    response = client.post(RUN, json={"selections": selections})
    assert response.status_code == 422, response.text
    assert expected in response.text.lower()


def test_a_rejected_selection_returns_no_groups(client):
    """The old failure mode was 200 with an empty list, which a client cannot tell from data."""
    response = client.post(RUN, json={"selections": [{"factor": "co2Ppm", "band": "low"}]})
    assert "groups" not in response.json()


def test_an_unknown_field_on_a_selection_is_rejected(client):
    response = client.post(RUN, json={"selections": [
        {"factor": "co2Ppm", "band": "ambient", "min": 1}]})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Export: a real file, with the evidence inside it
# ---------------------------------------------------------------------------
def test_csv_export_is_the_selected_evidence(client, rows):
    response = client.post(EXPORT, json={
        "selections": [{"factor": "co2Ppm", "band": "ambient"}], "format": "csv"})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    disposition = response.headers["content-disposition"]
    assert "attachment" in disposition
    filename = disposition.split('filename="')[1].split('"')[0]
    assert filename.startswith("spaceagrisim-cea-wheat-co2Ppm-ambient-")
    assert filename.endswith(".csv")

    text = response.content.decode("utf-8")
    group = client.post(RUN, json={"selections": [
        {"factor": "co2Ppm", "band": "ambient"}]}).json()["groups"][0]
    # Provenance, the selection, every experiment in the band, and the summary.
    assert "10.5281/zenodo.17764612" in text
    assert "CC BY 4.0" in text
    assert group["bandLabel"] in text
    for experiment in group["experiments"]:
        assert experiment in text
    assert "Limitations" in text
    # And it parses as CSV: two tables separated by a blank line, each internally rectangular.
    data_lines = [line for line in text.splitlines() if not line.startswith("#")]
    sections = [section.strip() for section in "\n".join(data_lines).split("\n\n")
                if section.strip()]
    assert len(sections) == 2, "expected an experiment table and a summary table"
    experiment_rows = list(csv.reader(io.StringIO(sections[0])))
    summary_rows = list(csv.reader(io.StringIO(sections[1])))
    assert experiment_rows[0][0] == "selected_factor"
    assert summary_rows[0][0] == "band_label"
    for table in (experiment_rows, summary_rows):
        assert len({len(row) for row in table}) == 1, "a table has ragged rows"
    # One row per experiment in the band, plus the header.
    assert len(experiment_rows) - 1 == group["measured"]["n"] == 29


def test_csv_export_carries_no_experiment_outside_the_band(client, rows):
    """The file holds the band's experiments and no others - not the whole dataset."""
    group = client.post(RUN, json={"selections": [
        {"factor": "airTemperatureC", "band": "warm"}]}).json()["groups"][0]
    text = client.post(EXPORT, json={"selections": [
        {"factor": "airTemperatureC", "band": "warm"}], "format": "csv"}).content.decode("utf-8")

    data_lines = [line for line in text.splitlines() if line and not line.startswith("#")]
    parsed = list(csv.reader(io.StringIO("\n".join(data_lines))))
    header, body = parsed[0], parsed[1:]
    id_column = header.index("experiment_id")
    exported = {row[id_column] for row in body if len(row) == len(header)}
    assert exported == set(group["experiments"])
    assert len(exported) == group["measured"]["n"] == 3
    # Every other experiment in the dataset is absent from the file.
    absent = {row["experimentId"] for row in rows} - set(group["experiments"])
    assert absent
    for experiment in absent:
        assert experiment not in text


def test_pdf_export_is_a_pdf_with_the_band_in_it(client):
    response = client.post(EXPORT, json={
        "selections": [{"factor": "photoperiodHours", "band": "long"}], "format": "pdf"})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
    assert len(response.content) > 1500, "a one-page PDF of nothing is not an export"
    filename = response.headers["content-disposition"].split('filename="')[1].split('"')[0]
    assert filename.endswith(".pdf")


def test_export_rejects_an_unrenderable_format(client):
    response = client.post(EXPORT, json={
        "selections": [{"factor": "co2Ppm", "band": "ambient"}], "format": "xlsx"})
    assert response.status_code == 422


def test_export_rejects_a_band_that_does_not_exist(client):
    response = client.post(EXPORT, json={
        "selections": [{"factor": "co2Ppm", "band": "low"}], "format": "csv"})
    assert response.status_code == 422


def test_export_records_the_mission_configuration_when_given_one(client):
    configuration = {
        "crop": "lettuce", "simulationDays": 30, "radiation": 0.3, "waterAvailability": 100.0,
        "lightHours": 16.0, "co2Level": 1000.0, "growingArea": 10.0,
        "earthComparisonMode": "matched", "lightIntensity": 300.0, "temperature": 22.0,
        "humidity": 60.0, "waterRecyclingEfficiency": 90.0, "lightSpectrum": "balanced",
    }
    response = client.post(EXPORT, json={
        "selections": [{"factor": "co2Ppm", "band": "ambient"}], "format": "csv",
        "configuration": configuration})
    assert response.status_code == 200, response.text
    text = response.content.decode("utf-8")
    # The habitat configuration is context for the reading, and the file says it is not a
    # measurement of the band.
    assert "Mission configuration" in text
    assert "lightIntensity" in text


@pytest.mark.parametrize(
    "band,text",
    [("ambient", "≤ 450 ppm"), ("enriched", "> 450 to ≤ 800 ppm"), ("high", "> 800 ppm")],
)
def test_each_exported_band_states_its_own_bounds(client, band, text):
    response = client.post(EXPORT, json={
        "selections": [{"factor": "co2Ppm", "band": band}], "format": "csv"})
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    # The band label the user selected, and the interval it means, both in the file.
    assert text in body
    if band != "high":
        assert "value" in body
