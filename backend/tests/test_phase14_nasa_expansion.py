"""Phase 14 — NASA catalogue expansion, and the integrity rules that keep it honest.

Two things are being protected here.

First, provenance: every study added in Phase 14 must have a committed ISA metadata archive
whose bytes still hash to the pinned digest. A catalogue that cites NASA studies without the
bytes it verified is a bibliography, not evidence.

Second, agreement: the corpus publishes a per-kind breakdown next to a total, and the
assistant's screen publishes a passage count. Both have already drifted once — a hard-coded
"46" against a corpus of 47. These tests fail if either can drift again.
"""

import hashlib
import json
import re
from pathlib import Path

import pytest

from app import evidence, research

ROOT = Path(__file__).resolve().parents[2]
PHASE14 = ["OSD-59", "OSD-386", "OSD-670", "OSD-723", "OSD-856"]


def _catalogue() -> dict[str, dict]:
    return {row["id"]: row for row in research.manifest()["datasets"]}


@pytest.mark.parametrize("study_id", PHASE14)
def test_phase14_study_is_pinned_and_its_bytes_are_present(study_id):
    row = _catalogue()[study_id]
    assert row["status"] == "verified-metadata"
    assert re.fullmatch(r"[0-9a-f]{64}", row["metadataSha256"])
    assert row["version"] >= 1
    entry = next(iter(row["files"]))
    path = ROOT / entry["file"] if "file" in entry else None
    archive = next((ROOT / "data" / "raw" / study_id).glob("*ISA.zip"), None)
    assert archive is not None, f"{study_id}: pinned ISA archive is missing from the repository"
    payload = archive.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == row["metadataSha256"]
    assert len(payload) == entry["bytes"]


def test_phase14_checksums_file_matches_the_catalogue():
    checksums = json.loads((ROOT / "data" / "metadata" /
                           "phase14_manifest_checksums.json").read_text())["studies"]
    catalogue = _catalogue()
    for study_id in PHASE14:
        assert checksums[study_id]["sha256"] == catalogue[study_id]["metadataSha256"]
        assert checksums[study_id]["bytes"] == catalogue[study_id]["files"][0]["bytes"]


def test_phase14_studies_declare_what_they_cannot_support():
    """An acquired study must state its limits and must not be presented as training data."""
    catalogue = _catalogue()
    for study_id in PHASE14:
        row = catalogue[study_id]
        assert row["title"] and row["description"]
        assert row["sourceUrl"].startswith("https://osdr.nasa.gov/")
        assert len(row["limitations"]) >= 3, study_id
        assert "Not a training table" in row["trainingEligibility"], study_id
        assert row["sampleCount"] > 0


def test_every_catalogue_row_keeps_the_provenance_it_claims():
    for row in research.manifest()["datasets"]:
        if row["id"] not in PHASE14:
            continue
        assert row["acquisition"].endswith("acquire_phase14_nasa_expansion.py")


# --------------------------------------------------------------------------
# The two counts that must never disagree again
# --------------------------------------------------------------------------
def test_corpus_breakdown_sums_to_the_published_total(client):
    stats = client.get("/api/assistant/corpus").json()
    assert sum(stats["byKind"].values()) == stats["passages"]
    # Every kind a passage can carry must be visible in the breakdown; classification
    # passages were previously counted in the total and missing from the breakdown.
    kinds = {passage.kind for passage in evidence.corpus()["passages"]}
    labels = set(evidence.KIND_LABELS[kind] for kind in kinds)
    assert labels <= set(stats["byKind"])


def test_assistant_screen_does_not_hard_code_the_passage_count():
    """The label must be derived from /assistant/corpus, not typed into the component.

    The defect this guards against is not the number 46 — it is the practice of writing a
    count into the JSX, which makes every later acquisition silently wrong on screen.
    """
    source = (ROOT / "frontend" / "src" / "pages" / "modules" / "ResearchAssistant.jsx").read_text()
    assert not re.search(r"RETRIEVAL OVER \d+", source), (
        "the retrieval label contains a hard-coded count; derive it from the corpus response")
    assert "assistant/corpus" in source
    assert "VERIFIED PASSAGES" in source
