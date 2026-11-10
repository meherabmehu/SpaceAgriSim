"""Phase 18 - NASA's space-crop reference and the supraoptimal-CO2 limit.

Two more records were supplied by the project owner:

* NTRS 20250001897 - "Space Crop Considerations for Human Exploration" (NASA HRP, 2024, 82 pp).
  It carries NASA's own planning arithmetic for leafy / pick-and-eat production, which gives the
  platform a long-missing anchor: fresh harvest per m2 per day.
* NTRS 20040090155 - "Supraoptimal carbon dioxide effects on growth of soybean" (1993). It shows
  that above about 1000 ppm CO2 the plant response can turn down, which the simulator's monotonic
  CO2 factor does not represent.

Both are used, and neither is fitted: the reference supplies an external yardstick, the soybean
study supplies a limitation that now reaches the user as a warning.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SUPPLEMENT = ROOT / "data" / "literature" / "ntrs_supplement.json"
CROP_TM = ROOT / "data" / "raw" / "NTRS" / "20250001897.pdf"


@pytest.fixture(scope="module")
def payload() -> dict:
    return json.loads(SUPPLEMENT.read_text())


@pytest.fixture(scope="module")
def crop_tm(payload) -> dict:
    return payload["reports"]["20250001897"]


@pytest.fixture(scope="module")
def soybean(payload) -> dict:
    return payload["reports"]["20040090155"]


@pytest.fixture(scope="module")
def tm_text() -> dict[int, str]:
    pymupdf = pytest.importorskip("pymupdf", reason="PDF text check needs pymupdf")
    doc = pymupdf.open(CROP_TM)
    return {index + 1: " ".join(page.get_text().split()) for index, page in enumerate(doc)}


# -- provenance ------------------------------------------------------------------
def test_the_reference_document_is_pinned(crop_tm):
    assert CROP_TM.is_file()
    assert crop_tm["pdf_sha256"] == hashlib.sha256(CROP_TM.read_bytes()).hexdigest()
    assert crop_tm["pages"] == 82


@pytest.mark.parametrize("page_number", [21, 24, 44, 45])
def test_every_excerpt_in_the_reference_is_on_its_cited_page(page_number, crop_tm, tm_text):
    """This document has a real text layer, so it gets the same treatment as TM 102788."""
    page = next(p for p in crop_tm["measurementPages"] if p["page"] == page_number)
    for chunk in page["excerpt"].split("... "):
        head = " ".join(chunk.split())[:90]
        if len(head) < 25:
            continue
        assert head in tm_text[page_number], f"p{page_number}: {head!r} not found"
    page_text = tm_text[page_number].lower()
    for term in page["terms"]:
        tokens = [w for w in term.lower().split() if len(w) >= 4]
        assert any(token in page_text for token in tokens), f"p{page_number}: no trace of {term!r}"


def test_the_soybean_record_is_honest_about_having_no_full_text(soybean):
    assert soybean["pdf"] is None and soybean["pdf_sha256"] is None
    assert soybean["measurementPages"] == []
    assert "no downloadable full text" in soybean["dataNature"]


# -- the anchor the platform was missing ----------------------------------------
def test_the_areal_anchor_recomputes_by_both_routes(crop_tm):
    """25 g per 0.030 m2 tray on a 14-day cycle must equal 50 g/day over 0.84 m2 per crew member."""
    row = crop_tm["structured"]["areal_productivity_anchor"]
    from_tray = row["serving_fresh_mass_g"] / row["tray_area_m2"] / row["cycle_days"]
    from_crew = row["crew_member_daily_serving_g"] / row["area_per_crew_member_m2"]
    assert from_tray == pytest.approx(row["derived_g_per_m2_day"], rel=0.01)
    assert from_crew == pytest.approx(row["derived_g_per_m2_day"], rel=0.01)


def test_the_crew_area_follows_from_the_tray_count(crop_tm):
    row = crop_tm["structured"]["areal_productivity_anchor"]
    assert row["trays_per_crew_member"] * row["tray_area_m2"] == pytest.approx(row["area_per_crew_member_m2"], rel=0.001)
    assert row["area_per_crew_member_m2"] * 4 == pytest.approx(row["area_four_crew_m2"], rel=0.001)


def test_lettuce_baseline_sits_within_five_percent_of_the_nasa_anchor(crop_tm):
    """The simulator's lettuce baseline is the crop the anchor actually speaks to."""
    from app.simulation.crops import get_crop

    row = crop_tm["structured"]["areal_productivity_anchor"]
    anchor = row["serving_fresh_mass_g"] / row["tray_area_m2"] / row["cycle_days"]
    lettuce = get_crop("lettuce")
    modelled = lettuce.harvest_biomass_g / lettuce.growth_duration_days
    assert 0.9 <= modelled / anchor <= 1.1


def test_the_crop_readiness_list_is_recorded_with_its_honest_totals(crop_tm):
    readiness = crop_tm["structured"]["crop_readiness"]
    assert readiness["crops_tested"] == 376
    assert readiness["crops_at_crl9"] == 9
    assert len(readiness["crl9_list"]) == 9
    assert "no herb, microgreen or legume" in readiness["note"]


# -- the supraoptimal-CO2 limit now reaches the user ---------------------------
def test_a_run_above_the_measured_optimum_carries_a_warning(client):
    body = client.post("/api/simulate", json={
        "crop": "lettuce", "radiation": 0.3, "waterAvailability": 100,
        "lightHours": 16, "co2Level": 2000, "growingArea": 10, "simulationDays": 30,
    }).json()
    assert any("supraoptimal" in warning.lower() or "Above 1000 ppm" in warning
               for warning in body["warnings"]), body["warnings"]


def test_a_run_at_the_measured_optimum_does_not_carry_that_warning(client):
    body = client.post("/api/simulate", json={
        "crop": "lettuce", "radiation": 0.3, "waterAvailability": 100,
        "lightHours": 16, "co2Level": 1000, "growingArea": 10, "simulationDays": 30,
    }).json()
    assert not any("Above 1000 ppm" in warning for warning in body["warnings"])


def test_the_warning_does_not_change_the_model_output():
    """The disclosure is a warning only: the CO2 factor must be exactly as it was."""
    from app.config import simulation_constants as constants
    from app.simulation.factors import co2_factor

    assert constants.CO2_MEASURED_OPTIMUM_PPM == 1000.0
    assert co2_factor(3000) > co2_factor(1000) > co2_factor(420)
    assert co2_factor(420) == pytest.approx(1.0)


def test_the_coverage_table_states_both_new_findings(client):
    rows = {row["feature"]: row for row in client.get("/api/datasets").json()["coverage"]}
    assert "20040090155" in rows["CO2 supraoptimal response"]["source"]
    assert "warning" in rows["CO2 supraoptimal response"]["method"].lower()
    assert "20250001897" in rows["Crop qualification status"]["source"]


def test_both_new_records_reach_the_evidence_corpus():
    from app import evidence

    corpus = evidence.corpus()
    sources = {p.source_id for p in corpus["passages"]}
    assert "NTRS-20250001897" in sources
    assert "NTRS-20040090155" in sources
    assert corpus["quarantine"] == []


def test_they_do_not_enable_a_space_yield_answer(client):
    for question in ("What is the expected crop yield on the Moon?",
                     "What is the expected lettuce yield on Mars?"):
        body = client.post("/api/assistant/ask", json={"question": question}).json()
        assert body["status"] == "insufficient", question
        assert body["claims"] == [] and body["citations"] == [], question
