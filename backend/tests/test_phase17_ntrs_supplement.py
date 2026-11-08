"""Phase 17 - two NASA records evaluated on request, and the line each one stops at.

Two records were supplied by the project owner:

* NTRS 20160006559 - a KSC poster comparing lettuce and radish under red+blue LEDs
  against white fluorescent light at equal PPF, with measured fresh mass, morphology,
  leaf area and chlorophyll for the exact two crops the simulator models.
* NTRS 20040087496 - Klassen & Bugbee (2002) on ethylene sensitivity in closed chambers,
  which quantifies a risk the simulator has no term for at all.

The tests below hold the honest middle ground this project keeps choosing: both records
become citable evidence, and neither becomes a fitted coefficient.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SUPPLEMENT = ROOT / "data" / "literature" / "ntrs_supplement.json"
POSTER = ROOT / "data" / "raw" / "NTRS" / "20160006559.pdf"


@pytest.fixture(scope="module")
def payload() -> dict:
    return json.loads(SUPPLEMENT.read_text())


@pytest.fixture(scope="module")
def light_study(payload) -> dict:
    return payload["reports"]["20160006559"]


@pytest.fixture(scope="module")
def ethylene(payload) -> dict:
    return payload["reports"]["20040087496"]


# -- provenance -----------------------------------------------------------------
def test_the_light_quality_poster_is_pinned_to_the_acquired_pdf(light_study):
    assert POSTER.is_file(), "the poster PDF must be committed with the record"
    digest = hashlib.sha256(POSTER.read_bytes()).hexdigest()
    assert light_study["pdf_sha256"] == digest
    assert light_study["pages"] == 1
    assert light_study["url"] == "https://ntrs.nasa.gov/citations/20160006559"


def test_the_ethylene_record_is_honest_about_having_no_full_text(ethylene):
    """NTRS exposes no download for this record, so an abstract-only claim must say so."""
    assert ethylene["pdf"] is None
    assert ethylene["pdf_sha256"] is None
    assert "no downloadable full text" in ethylene["dataNature"]
    assert ethylene["measurementPages"] == []


# -- the measured endpoints ------------------------------------------------------
def test_the_light_study_covers_both_simulated_crops(light_study):
    crops = light_study["structured"]["crops"]
    assert set(crops) == {"lettuce", "radish"}
    lettuce_parameters = {row["parameter"] for row in crops["lettuce"]}
    radish_parameters = {row["parameter"] for row in crops["radish"]}
    for name in ("shoot length", "shoot diameter", "total fresh mass", "leaf area", "chlorophyll"):
        assert name in lettuce_parameters, name
    for name in ("leaf fresh mass", "root fresh mass", "total fresh mass", "leaf area"):
        assert name in radish_parameters, name


def test_every_light_quality_row_has_a_value_an_sd_and_a_significance_symbol(light_study):
    allowed = {"***", "**", "*", "NS"}
    for crop, rows in light_study["structured"]["crops"].items():
        for row in rows:
            assert isinstance(row["rb"], (int, float)), (crop, row)
            assert isinstance(row["fl"], (int, float)), (crop, row)
            assert row["rb_sd"] > 0 and row["fl_sd"] > 0, (crop, row)
            assert row["significance"] in allowed, (crop, row)
            assert row["unit"], (crop, row)


def test_the_table_matches_the_finding_the_poster_states_in_words(light_study):
    """The poster's own summary must be visible in its own numbers.

    It says total fresh mass was not significantly different under either treatment,
    that lettuce did better under fluorescent light, and that radish accumulated more
    in the root storage under fluorescent light.
    """
    crops = light_study["structured"]["crops"]
    lettuce_total = next(r for r in crops["lettuce"] if r["parameter"] == "total fresh mass")
    radish_total = next(r for r in crops["radish"] if r["parameter"] == "total fresh mass")
    radish_root = next(r for r in crops["radish"] if r["parameter"] == "root fresh mass")

    assert radish_total["significance"] == "NS"
    assert lettuce_total["significance"] != "NS" and lettuce_total["fl"] > lettuce_total["rb"]
    assert radish_root["fl"] > radish_root["rb"]
    # lettuce leaf area and shoot length respond to the broad-spectrum treatment
    lettuce_area = next(r for r in crops["lettuce"] if r["parameter"] == "leaf area")
    assert lettuce_area["fl"] > lettuce_area["rb"]


def test_the_light_study_records_its_conditions_not_just_its_results(light_study):
    conditions = " ".join(page["excerpt"] for page in light_study["measurementPages"]).lower()
    assert "ppf" in conditions and "18 h" in conditions
    assert "23" in conditions and "70" in conditions and "1200" in conditions


# -- the ethylene record ---------------------------------------------------------
def test_the_ethylene_dose_response_numbers_are_the_published_ones(ethylene):
    statements = " ".join(s["statement"] for s in ethylene["structured"]["abstract_statements"])
    values = {s["value"] for s in ethylene["structured"]["abstract_statements"]}
    assert 36 in values and 63 in values and 60 in values
    assert "50 ppb" in statements
    assert "virtually sterile at 1000 ppb" in statements


def test_ethylene_has_no_coefficient_in_the_simulator():
    """It is disclosed, not modelled - so no ethylene factor may appear in the engine."""
    sources = list((ROOT / "backend" / "app" / "simulation").glob("*.py"))
    sources.append(ROOT / "backend" / "app" / "config" / "simulation_constants.py")
    hits = [path.name for path in sources if "ethylene" in path.read_text().lower()]
    assert hits == [], f"an ethylene term appeared in the model: {hits}"


def test_both_records_are_listed_as_not_used_and_say_why(payload):
    reasons = {row["id"]: row["reason"] for row in payload["not_used"]}
    assert set(reasons) == {"20160006559", "20040087496"}
    assert "fitted" in reasons["20160006559"].lower()
    assert "fabricated" in reasons["20040087496"].lower()


# -- the corpus ______________________________________________________________
def test_both_records_reach_the_evidence_corpus():
    from app import evidence

    corpus = evidence.corpus()
    sources = {p.source_id for p in corpus["passages"]}
    assert "NTRS-20160006559" in sources
    assert "NTRS-20040087496" in sources
    assert corpus["quarantine"] == []


def test_every_supplement_passage_carries_the_ground_based_limitation():
    from app import evidence

    for passage in evidence.corpus()["passages"]:
        if not passage.id.startswith("supplement::"):
            continue
        joined = " ".join(passage.limitations).lower()
        assert "ground-based" in joined, passage.id
        assert "not fitted" in joined or "no coefficient is fitted" in joined, passage.id


def test_the_light_quality_question_is_answerable_from_the_new_record(client):
    body = client.post("/api/assistant/ask",
                       json={"question": "which light spectrum did NASA test for lettuce and radish"}).json()
    assert body["status"] in {"grounded", "partial"}
    assert any(citation["sourceId"] == "NTRS-20160006559" for citation in body["citations"])


def test_the_new_records_do_not_enable_a_space_yield_answer(client):
    for question in ("What is the expected crop yield on the Moon?",
                     "What is the expected lettuce yield on Mars?"):
        body = client.post("/api/assistant/ask", json={"question": question}).json()
        assert body["status"] == "insufficient", question
        assert body["claims"] == [] and body["citations"] == [], question


def test_the_coverage_table_discloses_the_unmodelled_ethylene_risk(client):
    rows = {row["feature"]: row for row in client.get("/api/datasets").json()["coverage"]}
    trace_gas = rows["Trace-gas accumulation (ethylene)"]
    assert "not modelled" in trace_gas["status"]
    assert "20040087496" in trace_gas["source"]
    # and the light-spectrum row now names the acquired NASA comparison
    spectrum = rows["Light spectrum"]
    assert "20160006559" in spectrum["source"]
    assert "no spectral response surface" in spectrum["status"]
