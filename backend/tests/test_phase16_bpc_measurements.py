"""Phase 16 - the BPC measurement table must stay traceable to the report.

The value of a structured extraction is that every number can be walked back to
a sentence in a pinned NASA report. These tests do exactly that: the quote must
be on the cited page of the pinned PDF, the derived rows must recompute from
their named inputs, and the table must not quietly acquire a claim the report
does not make.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MEASUREMENTS = ROOT / "data" / "literature" / "ntrs_bpc_measurements.json"
LITERATURE = ROOT / "data" / "literature" / "ntrs_bpc.json"
PDF = ROOT / "data" / "raw" / "NTRS" / "19900016137.pdf"

STUDY_AREA_M2 = 20.0
CARBON_SPECIFIC_UMOL_TO_G = 44.01e-6  # g CO2 per umol


@pytest.fixture(scope="module")
def table() -> dict:
    return json.loads(MEASUREMENTS.read_text())


@pytest.fixture(scope="module")
def rows(table) -> dict[str, dict]:
    return {row["id"]: row for row in table["measurements"]}


@pytest.fixture(scope="module")
def derived(table) -> dict[str, dict]:
    return {row["id"]: row for row in table["derived"]}


@pytest.fixture(scope="module")
def pdf_text() -> dict[int, str]:
    pymupdf = pytest.importorskip("pymupdf", reason="PDF text check needs pymupdf")
    doc = pymupdf.open(PDF)
    return {index + 1: " ".join(page.get_text().split()) for index, page in enumerate(doc)}


# -- provenance ---------------------------------------------------------------
def test_measurement_file_is_pinned_to_the_same_pdf_as_the_literature_bundle(table):
    pinned = json.loads(LITERATURE.read_text())["reports"]["19900016137"]
    assert table["source"]["ntrs_id"] == "19900016137"
    digest = hashlib.sha256(PDF.read_bytes()).hexdigest()
    assert table["source"]["pdf_sha256"] == digest
    assert pinned["pages"] == 32
    assert table["source"]["url"] == f"https://ntrs.nasa.gov/citations/{table['source']['ntrs_id']}"


# -- the core promise: every number points at a sentence ------------------------
@pytest.mark.parametrize("row_id", [row["id"] for row in json.loads(MEASUREMENTS.read_text())["measurements"]])
def test_every_measurement_quote_appears_on_its_cited_page(row_id, rows, pdf_text):
    row = rows[row_id]
    page = row["page"]
    assert page in pdf_text, f"{row_id}: page {page} is not in the PDF"
    assert row["quote"] in pdf_text[page], (
        f"{row_id}: quote not found on page {page}. Quoted: {row['quote']!r}"
    )


def test_every_measurement_carries_page_quote_and_reading(rows):
    for row_id, row in rows.items():
        assert {"page", "quote", "reading", "quantity", "unit"} <= set(row), row_id
        assert len(row["quote"]) > 15, row_id
        assert row["kind"] in {"reported", "derived"}, row_id


# -- derived rows must recompute ----------------------------------------------
def test_co2_per_area_mean_is_the_stated_rate_times_the_photoperiod(derived):
    row = derived["derived.co2_g_per_m2_day_mean"]
    recomputed = 15.0 * 20.0 * 3600.0 * CARBON_SPECIFIC_UMOL_TO_G
    assert recomputed == pytest.approx(row["value"], rel=0.01)


def test_co2_per_area_peak_is_derived_from_the_peak_rate(derived):
    row = derived["derived.co2_g_per_m2_day_peak"]
    recomputed = 27.0 * 20.0 * 3600.0 * CARBON_SPECIFIC_UMOL_TO_G
    assert recomputed == pytest.approx(row["value"], rel=0.01)


def test_reported_net_co2_follows_from_the_daily_grams_and_stand_area(derived):
    row = derived["derived.co2_g_per_m2_day_reported_net"]
    assert 860.0 / STUDY_AREA_M2 == pytest.approx(row["value"], rel=0.01)


def test_the_light_period_and_net_anchors_agree_within_the_reports_own_ten_percent(derived):
    light = derived["derived.co2_g_per_m2_day_mean"]["value"]
    net = derived["derived.co2_g_per_m2_day_reported_net"]["value"]
    # The report subtracts dark respiration from the light-period figure and
    # quotes ~10 % as the gap; two independent routes to the same number.
    assert 0.85 <= net / light <= 0.95


def test_water_peak_and_mean_agree_with_the_reported_per_area_average(derived, rows):
    peak = derived["derived.water_l_per_m2_day_peak"]["value"]
    mean_per_area = rows["bpc.transpiration_per_area"]["value"]
    assert 120.0 / STUDY_AREA_M2 == pytest.approx(peak, rel=0.001)
    assert 90.0 / STUDY_AREA_M2 == pytest.approx(mean_per_area, rel=0.001)
    assert mean_per_area < peak


def test_dry_biomass_productivity_uses_harvest_grams_area_and_campaign_length(derived):
    row = derived["derived.dry_biomass_g_per_m2_day"]
    recomputed = 40_000.0 / STUDY_AREA_M2 / 86.0
    assert recomputed == pytest.approx(row["value"], rel=0.01)


def test_oxygen_anchor_is_stoichiometric_on_the_measured_co2_not_a_measurement(derived):
    o2 = derived["derived.o2_g_per_m2_day_mean"]
    assert o2["value"] == pytest.approx(derived["derived.co2_g_per_m2_day_mean"]["value"] * 32 / 44, rel=0.01)
    assert "stoichiometric" in o2["note"]


def test_every_derived_row_names_its_inputs(derived, rows):
    known = set(rows) | set(derived)
    for row_id, row in derived.items():
        assert row["formula"], row_id
        assert row["inputs"], row_id
        for name in row["inputs"]:
            assert name in known, f"{row_id} cites unknown input {name}"


# -- the line the table must not cross ----------------------------------------
def test_the_table_keeps_the_campaign_limits_next_to_the_numbers(table):
    joined = " ".join(table["limits"]).lower()
    for phrase in ("one chamber", "ground-based", "not evidence about reduced gravity", "not the measured quantity"):
        assert phrase in joined, phrase


def test_no_measurement_is_labelled_lunar_or_martian(table):
    blob = json.dumps(table).lower()
    for banned in ("lunar yield", "martian yield", "moon yield", "mars yield"):
        assert banned not in blob


def test_the_no_digitisation_decision_is_recorded_with_its_reason(table):
    note = table["conventions"]["no_digitisation"].lower()
    assert "rejected" in note
    assert "38" in note and "27" in note
