"""Phase 15 — NASA BPC measurements acquired from NTRS, and the line they must not cross.

The whole point of acquiring literature measurements is that the simulator no longer has to
pretend nobody ever measured canopy water and CO2 exchange. The whole risk of acquiring them
is that ground-chamber wheat numbers get borrowed for a Moon or Mars answer. These tests hold
both ends: the measurements must be retrievable, and they must not make the assistant willing
to answer a question the evidence still does not cover.
"""

import sys
import hashlib
import json
from pathlib import Path

import pytest

from app import evidence

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
LITERATURE = ROOT / "data" / "literature" / "ntrs_bpc"
REPORTS = ["19900016137", "19910010713", "19900007373"]


@pytest.fixture(scope="module")
def literature() -> dict:
    return safedata.load(LITERATURE)


@pytest.mark.parametrize("record_id", REPORTS)
def test_each_report_is_pinned_and_its_pdf_is_present(literature, record_id):
    report = literature["reports"][record_id]
    assert report["url"] == f"https://ntrs.nasa.gov/citations/{record_id}"
    assert report["title"]
    pin = report["pin"]
    assert pin["url"].startswith("https://ntrs.nasa.gov/api/citations/")
    pdf = ROOT / pin["file"]
    assert safedata.exists(pdf), f"{record_id}: pinned PDF is missing from the repository"
    payload = safedata.bytes(pdf)
    assert hashlib.sha256(payload).hexdigest() == pin["sha256"]
    assert len(payload) == pin["bytes"]


def test_reports_carry_page_level_measurements(literature):
    for record_id in REPORTS:
        pages = literature["reports"][record_id]["measurementPages"]
        assert pages, f"{record_id}: no measurement page was selected"
        for page in pages:
            assert page["page"] >= 1
            assert len(page["excerpt"]) > 200
            assert page["terms"]
        # Page numbers must be strictly increasing and unique, so a citation points at one page.
        numbers = [page["page"] for page in pages]
        assert numbers == sorted(set(numbers))


def test_literature_is_in_the_corpus_and_says_it_is_ground_based(client):
    stats = client.get("/api/assistant/corpus").json()
    assert stats["byKind"].get("literature", 0) > 0
    assert sum(stats["byKind"].values()) == stats["passages"]
    literature = [p for p in evidence.corpus()["passages"] if p.kind == "literature"]
    assert literature
    for passage in literature:
        assert passage.measured is True
        assert passage.url.startswith("https://ntrs.nasa.gov/")
        joined = " ".join(passage.limitations).lower()
        assert "ground-based" in joined or "ground" in joined


def test_a_chamber_measurement_question_is_answered_with_a_citation(client):
    body = client.post("/api/assistant/ask", json={
        "question": "What carbon dioxide exchange rates were measured in the BPC?"}).json()
    assert body["status"] in {"grounded", "partial"}
    assert body["citations"]
    assert any(citation["sourceId"].startswith("NTRS-") for citation in body["citations"])


@pytest.mark.parametrize("question", [
    "What is the expected crop yield on the Moon?",
    "What is the expected lettuce yield on Mars?",
])
def test_ground_chamber_data_does_not_enable_a_space_yield_answer(client, question):
    """The acquired measurements must not leak into a Moon or Mars claim."""
    body = client.post("/api/assistant/ask", json={"question": question}).json()
    assert body["status"] == "insufficient"
    assert body["claims"] == []
    assert body["citations"] == []


def test_the_literature_file_is_inside_the_runtime_bundle():
    """A repo-root-only path passes locally and silently empties the corpus in production.

    The serverless bundle carries data/ under backend/scientific_data and the corpus resolves
    everything through BUNDLE when it exists. This asserts the packaged copy is the one the
    application reads, so a missing package step fails here instead of on the deployed site.
    """
    from app import evidence as evidence_module

    assert safedata.exists(evidence_module.LITERATURE)
    if safedata.exists(evidence_module.BUNDLE):
        assert evidence_module.BUNDLE in evidence_module.LITERATURE.parents, (
            "the literature file must be packaged into backend/scientific_data, "
            f"not read from {evidence_module.LITERATURE}")
