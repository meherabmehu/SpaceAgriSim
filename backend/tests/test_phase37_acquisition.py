"""Phase 37 tests: the two new datasets, the gap adjudication and the model-evidence audit.

Each test encodes a way this phase's conclusions could have been wrong, and in several cases
actually were before being caught:

* the dosing workbook's harvest sheet is three 9-column system blocks side by side, and a
  single-column scan silently lost two thirds of the plants (n = 64 instead of 191);
* the same dosing experiment is deposited twice on Zenodo, so counting both deposits would have
  turned one trial into two pieces of evidence;
* the green-light trial has a fourth arm that varies planting density as well as spectrum, so any
  spectrum claim made from it would carry a density confound;
* the "Overall fresh weight" and "Yield component fresh weight" columns differ by roughly 25 %,
  and quoting one while comparing against the other would manufacture a yield change;
* a model verdict is easy to upgrade by accident when new evidence is announced, so the audit is
  pinned to refuse promotion.

A test that only checked "the JSON parses" would have passed in every one of those cases.
"""
from __future__ import annotations
import sys

import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
LED = ROOT / "data" / "research" / "phase37" / "led_spectrum_response"
NUT = ROOT / "data" / "research" / "phase37" / "nutrient_solution"
MODELS = ROOT / "ml" / "evaluation" / "phase37_model_evidence"
MANIFEST = ROOT / "data" / "metadata" / "phase37_acquisition_manifest"
SEARCH = ROOT / "data" / "metadata" / "phase37_search_log"
CATALOG = ROOT / "data" / "research" / "dataset_catalog"
MATRIX = ROOT / "data" / "research" / "dataset_gap_matrix"


def _json(path: pathlib.Path) -> dict:
    assert safedata.exists(path), f"missing artefact {path.relative_to(ROOT)}"
    return safedata.load(path)


# ------------------------------------------------------------------- LED spectrum trial
def test_the_spectrum_claim_rests_on_an_arm_where_only_light_quality_changed():
    """The whole gap turned on separating a colour effect from a photon effect."""
    design = _json(LED)["design"]
    assert design["ppfdTargetUmolPerM2PerS"] == 200
    treatments = design["treatments"]
    assert len(treatments) >= 4
    # Every arm must name the same PPFD target, or the comparison is confounded by light quantity.
    targets = {t["PPFD target"].strip() for t in treatments}
    assert len(targets) == 1, f"arms disagree on PPFD: {targets}"


def test_the_density_confounded_arm_is_excluded_from_every_spectrum_claim():
    payload = _json(LED)
    confound = payload["densityConfound"]
    assert confound["treatment"] == "T3", "the confounded arm must be identified by name"
    assert confound["confoundedWithDensity"] is True
    # And no reported contrast may name that arm.
    for name in payload["freshWeightContrasts"]["contrasts"]:
        assert "T3" not in name and "t3" not in name, \
            f"density-confounded arm used in a spectrum contrast: {name}"


def test_the_harvest_counts_reconcile_with_the_workbook():
    """252 plants in the deposit's own sheet, and every one of them accounted for."""
    payload = _json(LED)
    summary = payload["harvest"]["summary"]["Fresh weight"]
    total = sum(t["n"] for t in summary.values())
    assert total == 252, f"harvested plants {total} does not match the workbook's 252"
    for name, block in summary.items():
        assert block["n"] > 0 and block["mean"] > 0, name


def test_an_effect_claimed_at_p_below_005_is_reported_with_its_interval():
    """No bare p-values: the reader needs the size of the difference and its uncertainty."""
    contrasts = _json(LED)["freshWeightContrasts"]["contrasts"]
    assert contrasts, "no fresh-weight contrasts recorded"
    for name, contrast in contrasts.items():
        assert contrast["available"] is True, name
        assert "permutationP" in contrast and "bootstrap95" in contrast, name
        lo, hi = contrast["bootstrap95"]
        assert lo < contrast["differenceOfMeans"] < hi, name
        # A p-value below the permutation floor would mean the test could not have produced it.
        assert contrast["permutationP"] >= contrast["permutationPFloor"], name


# ------------------------------------------------------------------- nutrient solution
def test_no_nutrient_uptake_rate_is_published_without_a_defensible_pairing():
    """The gap asked for uptake; publishing one from mismatched Pre/Post labels would be invention."""
    payload = _json(NUT)
    uptake = payload.get("uptakeRate")
    assert uptake is None, "an uptake rate was published despite the labels not pairing"
    assert payload["whatIsNotDerivable"], "the refusal must say why"


def test_the_deposits_duplicate_is_recorded_rather_than_counted_twice():
    manifest = _json(MANIFEST)
    dup = manifest["duplicateCheck"]
    assert dup["identicalFraction"] == 1.0
    assert dup["countsAsSecondCampaign"] is False
    ids = {entry["url"] for entry in _json(CATALOG)["datasets"]}
    assert "https://doi.org/10.5281/zenodo.17794636" in ids
    assert "https://doi.org/10.5281/zenodo.18804397" not in ids, (
        "the duplicate deposit must not appear as a separate catalogued dataset"
    )


def test_the_harvest_endpoint_matches_the_one_the_deposit_compares_against():
    """'Overall fw' and 'Yield component fw' differ by ~25 % in the same workbook.

    The deposit's own economic analysis reports the yield component, so using the overall column
    here would make these means incomparable with the study they come from. This caught a real
    mismatch: overall fw gave 73.9 g for Treatment 1 against a published 46.8 g.
    """
    payload = _json(NUT)
    assert payload["harvest"]["endpoint"] == "Yield component fw (g)"
    published = payload["plantCountDiscrepancy"]["plantsInDepositEconomicAnalysis"]
    assert published == 64
    # The workbook holds every plant; the subset the paper used is unidentified and must be said so.
    assert "not identified" in payload["plantCountDiscrepancy"]["note"]


def test_plant_counts_cover_all_three_system_blocks():
    """A single-column scan of this sheet reports 64 plants instead of 191. It did."""
    per_treatment = _json(NUT)["harvest"]["byTreatment"]
    counts = {name: block["n"] for name, block in per_treatment.items()}
    assert counts.get("Treatment 1") == 191, counts
    assert counts.get("Treatment 2") == 194, counts


# ------------------------------------------------------------------- acquisition integrity
def test_every_retained_file_matches_the_publishers_checksum():
    manifest = _json(MANIFEST)
    assert manifest["summary"]["allChecksumsVerified"] is True
    assert manifest["summary"]["failures"] == 0
    for record in manifest["records"].values():
        for file in record["files"]:
            assert file["checksumVerified"] is True, file["name"]
            assert safedata.exists(ROOT / file["storedAs"]), file["storedAs"]


def test_the_rejected_payload_is_not_retained_but_its_checksum_is():
    """EDEN ISS answered nothing; keeping 284 MB to prove that is not worth the clone."""
    manifest = _json(MANIFEST)
    rejected = manifest["rejected"]
    assert len(rejected) == 1
    eden = rejected[0]
    assert eden["wasConsideredFor"] == "mission-energy"
    assert eden["retained"] is False
    census = eden["sensorCensus"]
    assert census["power"] == census["current"] == census["voltage"] == census["energy"] == 0
    assert not safedata.exists(ROOT / "data" / "raw" / "_phase37_inspect")


# ------------------------------------------------------------------- gap adjudication
def test_the_gap_matrix_summary_recomputes_from_its_own_entries():
    matrix = _json(MATRIX)
    tokens = [g.get("statusToken") for g in matrix["gaps"]]
    stored = matrix["phase37"]["counts"]
    assert stored["total"] == len(tokens) == 14
    assert stored["closed"] == tokens.count("CLOSED")
    assert stored["partiallyClosed"] == tokens.count("PARTIALLY CLOSED")
    assert stored["open"] == tokens.count("OPEN")


def test_the_spectrum_gap_is_closed_on_evidence_and_the_nutrient_gap_is_not():
    by_id = {g["id"]: g for g in _json(MATRIX)["gaps"]}
    assert by_id["led-spectrum-response"]["statusToken"] == "CLOSED"
    # Concentration and EC were found; a defensible uptake rate was not. Partial is the honest word.
    assert by_id["nutrient-balance"]["statusToken"] == "PARTIALLY CLOSED"
    assert by_id["mission-energy"]["statusToken"] == "OPEN"


def test_a_closed_gap_points_at_the_evidence_that_closed_it():
    by_id = {g["id"]: g for g in _json(MATRIX)["gaps"]}
    for gap in by_id.values():
        decision = gap.get("phase37Decision")
        if decision and decision["decision"] == "CLOSED":
            assert decision["evidence"], f"{gap['id']} closed with no evidence path"
            for path in decision["evidence"]:
                assert safedata.exists(ROOT / path), f"{gap['id']} cites missing {path}"


def test_every_still_open_gap_states_why_it_stays_open():
    matrix = _json(MATRIX)
    log = _json(SEARCH)
    explained = set(log["whySomeGapsStayOpen"])
    for gap in matrix["gaps"]:
        if gap["statusToken"] == "OPEN":
            assert gap["id"] in explained, f"open gap {gap['id']} has no recorded reason"


def test_the_search_log_names_a_repository_and_a_query_for_what_it_looked_for():
    log = _json(SEARCH)
    assert len(log["repositories"]) >= 5
    assert len(log["queries"]) >= 15
    for query in log["queries"]:
        assert query["repository"] and query["query"], query
    for candidate in log["candidateAdjudication"]:
        assert candidate["decision"] in {"ACCEPTED", "PARTIALLY ACCEPTED", "REJECTED",
                                        "ALREADY INTEGRATED"}, candidate["id"]
        assert candidate["why"].strip(), f"{candidate['id']} rejected with no reason"


# ------------------------------------------------------------------- model evidence
def test_no_model_was_promoted_or_retrained_by_announcing_new_data():
    payload = _json(MODELS)
    assert payload["policy"]["noRetraining"] is True
    assert payload["policy"]["noThresholdMoves"] is True
    assert payload["counts"]["decisionGradeBefore"] == payload["counts"]["decisionGradeAfter"]
    for model_id, record in payload["models"].items():
        assert record["promoted"] is False, model_id
        assert record["retrained"] is False, model_id
        assert record["thresholdsChanged"] is False, model_id


def test_every_served_model_carries_one_of_the_five_permitted_classifications():
    permitted = {"PASS decision-grade", "FAILS-INDEPENDENT-CHECK", "NO-INDEPENDENT-CHECK",
                 "DOMAIN-REFUSED", "INSUFFICIENT-EVIDENCE"}
    payload = _json(MODELS)
    assert len(payload["models"]) == 7, payload["counts"]
    for model_id, record in payload["models"].items():
        assert record["classification"] in permitted, (model_id, record["classification"])


def test_artefact_hashes_still_match_the_registry():
    payload = _json(MODELS)
    assert payload["counts"]["artifactHashesVerified"] == payload["counts"]["served"]
    for model_id, record in payload["models"].items():
        assert record["registrySha256Matches"] is True, model_id


def test_a_model_is_not_called_tested_when_a_required_feature_is_absent():
    """The green-light trial measures no temperature at all; the dosing trial no light."""
    payload = _json(MODELS)
    for model_id, record in payload["models"].items():
        test = record["newEvidenceTest"]
        if test["testable"]:
            for name, block in test["datasets"].items():
                assert not block["absent"], (model_id, name)
                assert not block["outOfDomain"], (model_id, name)
        else:
            assert record["newEvidenceOutcome"] == "NOT-TESTED", model_id


@pytest.mark.parametrize("model_id", [
    "lettuce-earth-growth-v1", "lettuce-earth-growth-v2", "lettuce-earth-growth-v3",
    "mizuna-microbial-relative-load-v2", "radiation-exposure-osd46-v1",
    "radiation-quality-osd46-v1", "tomato-flight-response-v1",
])
def test_every_served_model_has_a_named_reproduction_script_on_disk(model_id):
    record = _json(MODELS)["models"][model_id]
    assert record["reproductionScriptExists"] is True, record["reproductionScript"]
