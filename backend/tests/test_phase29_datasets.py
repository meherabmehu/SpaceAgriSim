"""Phase 29: dataset integrity for the environmental-stress evidence base.

The claim this workflow makes is that its numbers are measured observations from a real, verified
publication. These tests hold that claim to its evidence: the raw file is the one the acquisition
manifest recorded, the derived tables reproduce from the raw file deterministically, the published
design is transcribed faithfully, and nothing was imputed, dropped or converted.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed" / "phase29"
RAW = ROOT / "data" / "raw" / "phase26" / "zenodo-greenlight-2024-lettuce"


def _quality() -> dict:
    return json.loads((PROCESSED / "light_stress_quality.json").read_text())


def _rows(name: str) -> list[dict[str, str]]:
    import csv

    with (PROCESSED / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_raw_file_matches_the_acquisition_manifest():
    manifest = json.loads((ROOT / "data" / "metadata" / "phase26_acquisition_manifest.json")
                          .read_text())
    recorded = manifest["datasets"]["zenodo-greenlight-2024-lettuce"]
    raw = RAW / "green_light_lettuce_open_data_(1).xlsx"
    digest = hashlib.sha256(raw.read_bytes()).hexdigest()
    recorded_digests = {entry["sha256"] for entry in recorded["files"]}
    assert digest in recorded_digests
    assert digest == _quality()["source"]["file"]["sha256"]
    assert raw.stat().st_size == _quality()["source"]["file"]["bytes"]


def test_the_evidence_base_is_licensed_and_citable():
    source = _quality()["source"]
    assert source["doi"] == "10.5281/zenodo.20394352"
    assert source["license"] == "CC BY 4.0"
    assert source["file"]["verifiedAgainstManifest"] is True
    assert "Zenodo record 20394352" in source["citation"]


def test_build_is_reproducible_and_writes_nothing_new():
    """Re-running the builder must reproduce the same bytes for the design table."""
    before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
              for path in PROCESSED.glob("*.csv")}
    result = subprocess.run([sys.executable, "ml/research/build_light_stress_dataset.py"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    after = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
             for path in PROCESSED.glob("*.csv")}
    assert after == before


def test_no_row_was_imputed_or_dropped():
    quality = _quality()
    assert quality["exclusions"]["harvest"] == {}
    assert quality["exclusions"]["photosynthesisMissingCells"] == {}
    assert quality["exclusions"]["pigments"] == {}
    transformations = " ".join(quality["transformations"]).lower()
    assert "no imputation" in transformations
    assert "no unit conversion" in transformations


def test_every_harvest_row_carries_a_value_and_a_unit():
    rows = _rows("light_stress_harvest.csv")
    assert len(rows) == _quality()["records"]["harvestRows"]
    for row in rows:
        assert row["value"].strip() != ""
        assert float(row["value"]) > 0
        assert row["unit"].strip() != ""
        assert row["regime"] in {"control", "t1", "t2", "t3"}


def test_the_published_design_is_transcribed_faithfully():
    design = {row["regime"]: row for row in _rows("light_spectrum_treatments.csv")}
    assert set(design) == {"control", "t1", "t2", "t3"}
    for regime in ("control", "t1", "t2", "t3"):
        assert float(design[regime]["ppfdUmolPerM2S"]) == 200.0
        assert float(design[regime]["photoperiodHours"]) == 16.0
        assert float(design[regime]["dailyLightIntegralMolPerM2Day"]) == 11.52
    # t3 is the density change, and the file must say so rather than hide it.
    assert abs(float(design["t3"]["relativePlantingDensity"]) - 1.25) < 1e-9
    assert float(design["control"]["relativePlantingDensity"]) == 1.0


def test_replicate_counts_are_unequal_and_reported():
    """The workbook is unbalanced; a summary that implies equal n would misstate the evidence."""
    per_trait = _quality()["records"]["harvestPerTrait"]
    assert per_trait["leafAreaMm2"] < per_trait["freshWeightG"]
    rows = _rows("light_stress_harvest.csv")
    fresh = [row for row in rows if row["trait"] == "freshWeightG"]
    counts = {regime: sum(1 for row in fresh if row["regime"] == regime)
              for regime in ("control", "t1", "t2", "t3")}
    assert len(set(counts.values())) > 1, "the regime sample sizes are genuinely unequal"
    assert sum(counts.values()) == per_trait["freshWeightG"]


def test_unsupported_conditions_are_named_not_extrapolated():
    limits = " ".join(_quality()["limits"]).lower()
    assert "ppfd" in limits and "photoperiod" in limits
    design_note = _quality()["design"]["designNote"].lower()
    assert "does not support fitting a continuous response surface" in design_note
