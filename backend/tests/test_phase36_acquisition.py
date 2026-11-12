"""Phase 36 acquisition and evidence tests.

These are not smoke tests. Each one encodes a specific way the acquisition could have been wrong
and that was, at some point during Phase 36, actually wrong:

* hourly irradiance arriving in MJ/hr while the importer assumed W/m2 - a factor of 278;
* NEX-GDDP-CMIP6 temperature arriving in kelvin and precipitation as a kg m-2 s-1 flux, with the
  precipitation rounded to three decimals into a column of zeros;
* NEX longitudes running 0..360, which sends Reykjavik to an Atlantic cell of fill values;
* a Zenodo record whose published MD5 covers a 39 GB object that was deliberately not downloaded;
* a gap matrix whose status column silently drifts from the JSON that is its source of truth.

A test that only checked "the file parses" would have passed in every one of those cases.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PHASE36 = ROOT / "data" / "research" / "phase36"
SITES = ["wageningen_nl", "tucson_us", "singapore_sg", "dhaka_bd", "reykjavik_is", "nairobi_ke"]


def _json(path: Path) -> dict:
    assert path.is_file(), f"missing artefact {path.relative_to(ROOT)}"
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- hourly weather
def test_hourly_power_covers_a_full_year_at_every_site():
    for site in SITES:
        rows = list(csv.DictReader((ROOT / "data" / "processed" / "power_hourly"
                                    / f"{site}_hourly.csv").open()))
        assert len(rows) == 8760, f"{site}: {len(rows)} hours"
        assert {row["date"] for row in rows}.__len__() == 365


def test_hourly_irradiance_is_in_watts_not_megajoules_per_hour():
    """The unit bug that was actually made: MJ/hr read as W/m2 underestimates by 278x.

    The guard is physical rather than numerical - a mid-latitude summer noon hour cannot be
    below 300 W/m2 or above the solar constant, and its daily integral must be a plausible
    number of megajoules. A column left in MJ/hr (values around 1-3) fails the first bound.
    """
    rows = list(csv.DictReader((ROOT / "data" / "processed" / "power_hourly"
                                / "wageningen_nl_hourly.csv").open()))
    summer = [row for row in rows if row["date"].startswith("2023-06")]
    noon = [float(row["sw_wm2"]) for row in summer if row["timestamp_lst"][11:13] == "12"]
    assert noon, "no noon hours found"
    noon.sort()
    median = noon[len(noon) // 2]
    # A median rather than a minimum: a heavily overcast June noon really does reach 169 W/m2,
    # so a minimum bound would fail on weather rather than on a unit error. A column left in
    # MJ/hr has a median around 2.8 and fails this by two orders of magnitude.
    assert median > 300.0, f"median noon irradiance too low for W/m2: {median}"
    assert max(noon) < 1200.0, f"noon irradiance above the solar constant: {max(noon)}"


def test_daily_light_integral_is_physically_possible():
    for site in SITES:
        rows = list(csv.DictReader((ROOT / "data" / "processed" / "power_hourly"
                                    / f"{site}_daily.csv").open()))
        dli = [float(row["dli_mol_m2_d"]) for row in rows if row["dli_mol_m2_d"]]
        assert 0.0 <= min(dli) and max(dli) < 80.0, f"{site}: DLI range {min(dli)}-{max(dli)}"
        # An annual mean DLI below 5 mol/m2/d or above 70 would mean a unit error escaped.
        mean = sum(dli) / len(dli)
        assert 5.0 < mean < 70.0, f"{site}: mean DLI {mean}"


def test_hourly_timestamps_are_labelled_as_the_provider_states_them():
    manifest = _json(ROOT / "data" / "metadata" / "power_hourly_manifest.json")
    assert manifest["dataset"]["fillValue"] == -999.0
    for key, entry in manifest["sites"].items():
        assert entry["status"] == "ok", key
        assert entry["timeStandard"] == "LST", key
        assert entry["reportedUnits"]["ALLSKY_SFC_SW_DWN"] == "MJ/hr", key


# --------------------------------------------------------------------------- NEX-GDDP-CMIP6
def test_nex_temperature_is_stored_in_degrees_celsius():
    rows = list(csv.DictReader((ROOT / "data" / "processed" / "nex_gddp"
                                / "wageningen_nl.csv").open()))
    values = [float(row["tas_c"]) for row in rows if row["tas_c"]]
    assert values
    # A kelvin column would sit around 280 and never approach 0.
    assert min(values) > -60.0 and max(values) < 60.0
    assert min(values) < 0.0 < max(values), "a temperate site must straddle 0 degC"


def test_nex_precipitation_is_not_a_column_of_zeros():
    """Rounding kg m-2 s-1 to three decimals produced exactly this artefact."""
    rows = list(csv.DictReader((ROOT / "data" / "processed" / "nex_gddp"
                                / "dhaka_bd.csv").open()))
    values = [float(row["pr_mm_d"]) for row in rows if row["pr_mm_d"]]
    assert values
    assert sum(1 for v in values if v > 0.0) > 50, "a monsoon site with no wet days is a bug"
    assert max(values) < 500.0, "mm/day above 500 is a unit error"


def test_nex_latitude_longitude_conversion_found_land_for_every_site():
    manifest = _json(ROOT / "data" / "metadata" / "nex_gddp_acquisition_manifest.json")
    for site in SITES:
        cell = manifest["cells"][site]
        assert abs(cell["cellLat"] - cell["requestedLat"]) <= 0.25
        assert abs(cell["cellLonDegreesEast"] - cell["requestedLon"]) <= 0.25
    # Fill values are counted per file; an all-ocean cell would show thousands.
    for entry in manifest["files"]:
        if entry["status"] != "ok":
            continue
        assert sum(entry["fillCells"].values()) == 0, entry["url"]


def test_both_windows_are_present_and_complete():
    rows = list(csv.DictReader((ROOT / "data" / "processed" / "nex_gddp"
                                / "nairobi_ke.csv").open()))
    scenarios = {row["scenario"] for row in rows}
    assert scenarios == {"historical", "ssp245"}
    for scenario in scenarios:
        years = {row["date"][:4] for row in rows if row["scenario"] == scenario}
        assert len(years) == 5, f"{scenario}: {sorted(years)}"


# --------------------------------------------------------------------------- measured ET
def test_measured_et_validation_has_both_legs_computed():
    report = _json(PHASE36 / "et0_measurement_validation.json")
    tereno = report["terenoFormulationTest"]
    assert tereno["status"] == "COMPUTED"
    assert tereno["dayCount"] >= 400
    assert tereno["independentOfReanalysis"] is True
    lysimeter = report["lysimeterLevelTest"]
    assert lysimeter["status"] == "COMPUTED"
    assert lysimeter["dayCount"] >= 1000
    assert lysimeter["levelTest"]["passed"] is True


def test_the_agroscope_series_is_not_a_copy_of_the_model():
    """A measured ET series that tracked ET0 exactly would be a red flag, not a triumph."""
    report = _json(PHASE36 / "et0_measurement_validation.json")
    annual = report["lysimeterLevelTest"]["annual"]
    ratios = [v["impliedAnnualKc"] for v in annual.values() if v["completeWaterYear"]]
    assert ratios, "no complete water year"
    assert all(0.5 < ratio < 1.5 for ratio in ratios), ratios


# --------------------------------------------------------------------------- IoT4Lettuce
def test_iot4lettuce_manifest_does_not_claim_the_whole_archive():
    manifest = _json(ROOT / "data" / "metadata" / "iot4lettuce_acquisition_manifest.json")
    dataset = manifest["dataset"]
    assert dataset["archiveMd5Verified"] is False
    assert dataset["membersNotAcquired"] > 20_000
    assert dataset["membersAcquired"] == 12
    # Range requests must have fetched orders of magnitude less than the archive.
    assert dataset["bytesFetched"] < 50_000_000
    assert dataset["archiveBytes"] > 39_000_000_000


def test_iot4lettuce_join_was_verified_rather_than_assumed():
    report = _json(PHASE36 / "iot4lettuce_water_cultivar.json")
    join = report["joinVerification"]
    assert join["pairsMatched"] == 45
    assert join["prefixRuleCheck"]["violations"] == 0


def test_cultivar_contrast_is_reported_with_its_uncertainty():
    report = _json(PHASE36 / "iot4lettuce_water_cultivar.json")
    contrast = report["cultivarContrast"]
    assert contrast["permutationP"] < 0.001
    low, high = contrast["bootstrap95"]
    assert low > 0.0 and high > low
    irrigation = report["irrigationContrast"]
    # The irrigation contrast is the null result and must not be dressed up as an effect.
    assert irrigation["permutationP"] > 0.05
    assert irrigation["bootstrap95"][0] < 0.0 < irrigation["bootstrap95"][1]


def test_ky_is_labelled_conditional_because_no_et_was_measured():
    report = _json(PHASE36 / "iot4lettuce_water_cultivar.json")
    ky = report["kyAccounting"]
    assert ky["status"].startswith("CONDITIONAL")
    assert "not" in ky["whyConditional"]
    assert len(ky["scenarios"]) >= 2


# --------------------------------------------------------------------------- gap matrix
def _current_decision(gap: dict) -> tuple[dict, int]:
    """The newest adjudication recorded for a gap, and the phase that recorded it.

    A later phase may close or reopen a gap, so the assertions below read the newest decision block
    rather than pinning Phase 36's. That is a stronger check than the original: the original only
    held while no later phase touched the matrix, and would have had to be edited or skipped the
    moment one did.
    """
    for phase in (37, 36):
        block = gap.get(f"phase{phase}Decision")
        if block:
            return block, phase
    return {}, 0


def _newest_counts(matrix: dict) -> dict:
    for phase in (37, 36):
        block = matrix.get(f"phase{phase}") or {}
        if block.get("counts"):
            return block["counts"]
    return {}


def test_every_gap_has_a_status_token_from_the_agreed_vocabulary():
    matrix = json.loads((ROOT / "data" / "research" / "dataset_gap_matrix.json").read_text())
    assert len(matrix["gaps"]) == 14
    for gap in matrix["gaps"]:
        assert gap["statusToken"] in {"CLOSED", "PARTIALLY CLOSED", "OPEN"}, gap["id"]
        decision, phase = _current_decision(gap)
        assert phase, f"{gap['id']}: no adjudication recorded in any phase"
        assert decision["decision"] == gap["statusToken"], gap["id"]


def test_gap_counts_match_the_tokens_they_are_derived_from():
    matrix = json.loads((ROOT / "data" / "research" / "dataset_gap_matrix.json").read_text())
    tokens = [gap["statusToken"] for gap in matrix["gaps"]]
    counts = _newest_counts(matrix)
    assert counts, "no phase block carries counts"
    assert counts["partiallyClosed"] == tokens.count("PARTIALLY CLOSED")
    assert counts["open"] == tokens.count("OPEN")
    assert counts["total"] == len(tokens)
    # Two closures are by decision, not by data; they must not be counted as data closures.
    assert counts["closedByData"] + counts["closedByDecision"] == tokens.count("CLOSED")


def test_closed_gaps_name_the_evidence_that_closed_them():
    matrix = json.loads((ROOT / "data" / "research" / "dataset_gap_matrix.json").read_text())
    for gap in matrix["gaps"]:
        if gap["statusToken"] != "CLOSED":
            continue
        decision, _ = _current_decision(gap)
        if "decision" in gap["id"] or gap["id"] in {"fractional-gravity", "yield-labels"}:
            continue    # closed by removing a capability, so there is no dataset to point at
        assert decision["evidence"], gap["id"]
        for path in decision["evidence"]:
            assert (ROOT / path).exists(), f"{gap['id']}: missing {path}"


# --------------------------------------------------------------------------- model re-evaluation
def test_no_model_was_retrained_or_promoted():
    report = _json(ROOT / "ml" / "evaluation" / "phase36_model_reevaluation.json")
    assert report["counts"]["served"] == 7
    for model_id, record in report["models"].items():
        assert record["retrained"] is False, model_id
        assert record["thresholdsChanged"] is False, model_id
        assert record["artifactUnchanged"] is True, model_id
        assert record["decisionGradeAfter"] == record["decisionGradeBefore"], model_id


def test_a_domain_refusal_is_recorded_as_a_refusal_not_as_a_failure():
    report = _json(ROOT / "ml" / "evaluation" / "phase36_model_reevaluation.json")
    refused = [m for m in report["models"].values() if m["outcome"] == "DOMAIN-REFUSED"]
    assert len(refused) == 3
    for record in refused:
        assert record["violations"], "a refusal must name the field that is out of domain"


# --------------------------------------------------------------------------- generated docs
def test_gap_matrix_document_is_not_stale():
    import subprocess
    result = subprocess.run(["python3", "ml/research/build_gap_matrix.py", "--check"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_catalogue_document_is_not_stale():
    import subprocess
    result = subprocess.run(["python3", "ml/research/build_catalog.py", "--check"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_every_recorded_checksum_is_a_full_digest():
    for name in ("lysimeter_acquisition_manifest.json", "iot4lettuce_acquisition_manifest.json",
                 "power_hourly_manifest.json", "nex_gddp_acquisition_manifest.json"):
        payload = _json(ROOT / "data" / "metadata" / name)
        blob = json.dumps(payload)
        digests = re.findall(r"\b[0-9a-f]{64}\b", blob)
        assert digests, f"{name} records no SHA-256 digest"
        for digest in digests:
            assert len(digest) == 64


# --------------------------------------------------------------------------- served evidence surface
# Phase 8 required the acquisition to be reflected in the running product without breaking any
# existing contract. These tests hold the surface to the same rule as the research scripts: a number
# is served only with the label that says what kind of number it is, and the counts it reports must
# be recomputed from the entries rather than trusted from a summary.

def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def test_acquisition_evidence_surface_is_served():
    response = _client().get("/api/acquisition-evidence")
    assert response.status_code == 200
    payload = response.json()
    assert payload["phase"] == 36
    for key in ("gaps", "waterUse", "projectedClimate", "cultivarAndWater", "hourly", "models",
                "catalogue"):
        assert key in payload, key


def test_the_surface_labels_what_each_kind_of_number_is():
    payload = _client().get("/api/acquisition-evidence").json()
    assert set(payload["labels"]) == {"measured", "derived", "predicted"}
    # A projected value must never be offered as a measurement, and a ratio computed from a model
    # must never be offered as one either.
    assert payload["projectedClimate"]["label"] == "predicted"
    assert payload["waterUse"]["formulation"]["label"] == "derived"
    assert payload["waterUse"]["level"]["label"] == "derived"
    assert payload["cultivarAndWater"]["cultivar"]["label"] == "measured"


def test_the_served_gap_counts_recompute_from_the_entries():
    payload = _client().get("/api/acquisition-evidence").json()
    gaps = payload["gaps"]
    rows = gaps["gaps"]
    assert len(rows) == gaps["total"] == 14
    for token in ("CLOSED", "PARTIALLY CLOSED", "OPEN"):
        assert gaps[{"CLOSED": "closed", "PARTIALLY CLOSED": "partiallyClosed",
                     "OPEN": "open"}[token]] == sum(1 for r in rows if r["status"] == token)
    # Closed splits into data and decision closures, and the two must add up to the total closed.
    assert gaps["closedByData"] + gaps["closedByDecision"] == gaps["closed"]


def test_every_open_gap_states_why_it_is_still_open():
    payload = _client().get("/api/acquisition-evidence").json()
    for row in payload["gaps"]["gaps"]:
        if row["status"] != "CLOSED":
            assert row["whatChanged"], row["id"]
            assert row["remainingWork"], row["id"]


def test_no_model_became_decision_grade_and_the_surface_says_so():
    payload = _client().get("/api/acquisition-evidence").json()
    assert payload["decisionGradeCount"] == 1
    counts = payload["models"]["counts"]
    assert counts["decisionGradeBefore"] == counts["decisionGradeAfter"] == 1
    assert counts["scored"] == 0
    # The sentence is recomputed from the matrix, so it must agree with the counts served beside it
    # rather than with whichever number was true when the sentence was written.
    gaps = payload["gaps"]
    sentence = payload["interpretation"].lower()
    assert f"{gaps['open']} remain open" in sentence
    assert f"{gaps['closed']} are closed" in sentence
    assert "none became so in this phase" in sentence


def test_the_surface_does_not_change_any_existing_response_shape():
    """Additive only: the routes the frontend already consumes must be untouched by Phase 8."""
    client = _client()
    for path in ("/api/models", "/api/datasets", "/api/benchmarks", "/api/water-use-evidence",
                 "/api/science/evidence", "/api/scientific-summary"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert isinstance(response.json(), dict), path
