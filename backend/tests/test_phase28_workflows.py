"""Phase 28 workflows, tested from the outside in, as Phase 30 left them.

Two of the three original workflows are unchanged in shape: water demand and the measured
light-stress comparison. The third - harvest prediction - was removed in Phase 30 because no
harvest model met the 30 % independent-error criterion, and its tests were replaced with tests
that prove the capability is gone rather than quietly broken.

These tests are written against the HTTP surface, because the contract a user actually relies on is
the response body. Every assertion is one of three kinds:

* **the envelope is complete** — units, ranges, evidence, uncertainty, limitations and a method are
  present for every scenario, so the completion gate is checked by a test and not by a claim;
* **the science is real** — the numbers equal the served model's own output, the equations are
  reproduced independently, and the measured bench comes from the committed, hash-verified table;
* **the refusal holds** — unsupported crops, out-of-domain input and missing measurements are
  reported rather than papered over.

The tests deliberately avoid asserting the exact prediction value in most places: a retrained
artifact must not break the workflow, but a workflow that stops using the artifact must break these
tests. Where a number is pinned, it is pinned against the artifact's own report.
"""

from __future__ import annotations

import math

import pytest

from app import research
from app.workflows import units

HARVEST = "/api/workflows/harvest-prediction"


def _mounted_paths() -> set[str]:
    """The real application's own OpenAPI document, not this file's trimmed test app."""
    from app.main import app as full_app

    return set(full_app.openapi()["paths"])
WATER = "/api/workflows/water-demand"
CEA = "/api/workflows/light-stress/controlled-environment"
CEA_SELECTION = {"factor": "co2Ppm", "band": "ambient"}

DHAKA = {
    "crop": "lettuce", "growingAreaM2": 10.0, "daysAfterTransplant": 20,
    "tmaxC": 33.0, "tminC": 22.0, "relativeHumidityPct": 55.0,
    "solarRadiationMJm2": 20.0, "windSpeedMs": 2.0, "dayOfYear": 80,
    "latitude": 23.8, "elevationM": 8.0, "plantsPerM2": 25.0,
}
HOT = {**DHAKA, "label": "hot", "tmaxC": 38.0, "tminC": 27.0,
       "relativeHumidityPct": 35.0, "solarRadiationMJm2": 26.0, "windSpeedMs": 3.5}
# The harvest workflow's input schema was removed with the workflow; these are kept only to prove
# that a request shaped like the old control set is now rejected rather than served.
GROWTH = {
    "daysAfterTransplant": 21.0, "airTemperature": 24.0, "rootTemperature": 24.0,
    "ppfd": 400.0, "photoperiodHours": 16.0, "plantDensityPerM2": 25.0,
}


# ----------------------------------------------------------------- the catalogue


def test_catalogue_lists_only_workflows_that_can_be_completed(client):
    """Phase 31: the catalogue is the set of workflows a user can actually complete.

    Phase 30 carried the removed harvest forecast as an "unavailable" entry. That entry has now
    gone too: a catalogue row whose only content is "this was removed" is still a retired feature
    in the product, and the failure record it pointed at lives in ml/evaluation and in docs.
    """
    body = client.get("/api/workflows").json()
    ids = [item["id"] for item in body["workflows"]]
    assert ids == ["water-demand", "light-stress"]
    assert all(item["status"] == "complete" for item in body["workflows"])
    assert "harvest-prediction" not in ids
    # Every advertised endpoint must be mounted, or the catalogue is advertising a dead route.
    for item in body["workflows"]:
        for endpoint in item["endpoints"].values():
            path = endpoint.split(" ", 1)[1]
            assert path in _mounted_paths(), path

    gaps = {gap["id"]: gap for gap in body["documentedGaps"]}
    # The gap was narrowed from "no environmental-stress workflow" to "no response surface" when the
    # measured comparison shipped. It is still not complete, and the reason is still a data gap.
    assert gaps["environmental-stress-response-surface"]["status"] == "not-complete"
    assert "response surface" in gaps["environmental-stress-response-surface"]["blocker"]


def test_every_advertised_endpoint_exists(client):
    body = client.get("/api/workflows").json()
    for workflow in body["workflows"]:
        for name, endpoint in workflow["endpoints"].items():
            route = endpoint.split(" ", 1)[1]
            response = client.post(route, json={"scenarios": [{"crop": "lettuce"}]}) if (
                endpoint.startswith("POST")) else client.get(route)
            # POST bodies here are deliberately invalid; what matters is that the route is mounted
            # (422 for validation) rather than missing (404).
            assert response.status_code != 404, f"{name} {endpoint} is not mounted"


# -------------------------------------------------------------------- unit registry


def test_unit_registry_reports_dimensions_and_never_converts(client):
    body = client.get("/api/workflows/units").json()
    assert body["units"]["mm/day"]["dimension"] == "flux"
    assert body["units"]["mL/pot/day"]["dimension"] == "flow"
    assert body["units"]["g/plant"]["dimension"] == "mass"
    assert body["units"]["degC"]["dimension"] == "temperature"
    assert "converts" in body["note"]


def _unit_names(payload):
    found = set()

    def walk(node):
        if isinstance(node, dict):
            if set(node) >= {"unit", "dimension", "description"}:
                found.add(node["unit"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)
    return found


def test_units_returned_by_every_workflow_are_registered(client):
    water = client.post(WATER + "/run", json={"scenarios": [DHAKA]}).json()
    light = client.post("/api/workflows/light-stress/run",
                        json={"scenarios": [{"regime": "control"}]}).json()
    cea = client.post(CEA + "/run", json={"selections": [CEA_SELECTION]}).json()
    for payload in (water, light, cea):
        for name in _unit_names(payload):
            assert name in units.UNITS, f"unregistered unit {name!r}"


def test_every_quantity_in_the_units_map_has_a_dimension(client):
    for path, body in ((WATER + "/run", {"scenarios": [DHAKA]}),
                       (CEA + "/run", {"selections": [CEA_SELECTION]})):
        payload = client.post(path, json=body).json()
        assert payload["units"], f"{path} returned no units map"
        for field, meta in payload["units"].items():
            assert meta["registered"] is True, f"{field} carries an unregistered unit"
            assert meta["dimension"] in units.DIMENSIONS


# -------------------------------------------------------------------- water workflow


def test_water_capability_names_units_and_ranges_for_every_field(client):
    body = client.get(WATER + "/capability").json()
    names = {field["name"] for field in body["fields"]}
    assert {"growingAreaM2", "tmaxC", "tminC", "relativeHumidityPct", "dayOfYear",
            "latitude", "elevationM"} <= names
    for field in body["fields"]:
        assert field["unit"] in units.UNITS
        assert field["max"] > field["min"]
        assert field["why"].strip(), f"{field['name']} has no scientific explanation"
    crops = {crop["key"]: crop for crop in body["crops"]}
    assert crops["lettuce"]["hasMeasuredBench"] is True
    assert crops["tomato"]["hasMeasuredBench"] is False


def test_water_every_layer_is_present(client):
    body = client.post(WATER + "/run", json={"scenarios": [DHAKA]}).json()
    scenario = body["scenarios"][0]
    for key in ("inputs", "et0", "demand", "measuredBench"):
        assert key in scenario, f"missing {key}"
    assert scenario["et0"]["primaryMethod"] == "penman-monteith"
    assert scenario["et0"]["terms"]["radiationMm"] is not None
    assert scenario["demand"]["et0Reference"]["litresPerDay"] > 0
    assert scenario["demand"]["cropRelative"]["litresPerDay"] > 0
    assert scenario["demand"]["agreement"]["arbitrated"] is False
    assert body["evidence"]["layers"], "no evidence layers"
    assert body["limitations"], "no limitations"
    assert body["method"]["referenceEquation"].startswith("FAO-56")


def test_water_reference_equation_is_reproduced_independently(client):
    """ET0 x Kc x canopy cover x area, recomputed from the response, must match the response."""
    body = client.post(WATER + "/run", json={"scenarios": [DHAKA]}).json()
    scenario = body["scenarios"][0]
    et0_mm = scenario["et0"]["valueMmPerDay"]
    kc = scenario["demand"]["et0Reference"]["cropCoefficient"]
    scale = scenario["demand"]["et0Reference"]["canopyScale"]
    area = scenario["inputs"]["growingAreaM2"]
    expected = et0_mm * kc * scale * area
    # The response rounds its components (ET0 to 3 dp, the canopy scale to 4 dp), so a recomputation
    # from the printed terms can only agree to that precision. A centilitre is well inside it.
    assert scenario["demand"]["et0Reference"]["litresPerDay"] == pytest.approx(expected, abs=0.01)
    # 1 mm over 1 m2 is 1 L, so the per-m2 figure is the mm figure.
    assert scenario["demand"]["et0Reference"]["mmPerDay"] == pytest.approx(
        scenario["demand"]["et0Reference"]["litresPerDay"] / area, abs=1e-3)


def test_water_climate_changes_the_reference_column_and_not_the_assumption_column(client):
    body = client.post(WATER + "/run", json={"scenarios": [DHAKA, HOT]}).json()
    base, hot = body["scenarios"]
    assert hot["et0"]["valueMmPerDay"] > base["et0"]["valueMmPerDay"]
    assert hot["demand"]["et0Reference"]["litresPerDay"] > base["demand"]["et0Reference"]["litresPerDay"]
    # The crop-relative equation takes no climate input. Asserting the equality keeps the workflow
    # honest: the day someone wires climate into it, this test must be revisited rather than
    # silently passing a claim in the response that is no longer true.
    assert hot["demand"]["cropRelative"]["litresPerDay"] == base["demand"]["cropRelative"]["litresPerDay"]
    assert base["demand"]["climateSensitivity"]["cropRelativeRespondsToClimate"] is False


def test_water_growth_stage_moves_both_equations(client):
    early = {**DHAKA, "daysAfterTransplant": 4}
    late = {**DHAKA, "daysAfterTransplant": 25}
    body = client.post(WATER + "/run", json={"scenarios": [early, late]}).json()
    a, b = body["scenarios"]
    assert b["inputs"]["growthFraction"] > a["inputs"]["growthFraction"]
    assert b["demand"]["et0Reference"]["litresPerDay"] > a["demand"]["et0Reference"]["litresPerDay"]
    assert b["demand"]["cropRelative"]["litresPerDay"] > a["demand"]["cropRelative"]["litresPerDay"]


def test_water_names_the_fallback_method_when_radiation_is_missing(client):
    """Without radiation and wind there is no Penman-Monteith, and the response names what it used.

    There is exactly one fallback: the published Hargreaves-Samani equation. Phase 31 removed the
    fitted emulator from the serving path, so a response can no longer answer with a learned
    estimate here - which is why this test now pins the method rather than accepting either.
    """
    no_radiation = {k: v for k, v in DHAKA.items() if k not in ("solarRadiationMJm2", "windSpeedMs")}
    body = client.post(WATER + "/run", json={"scenarios": [no_radiation]}).json()
    scenario = body["scenarios"][0]
    assert scenario["et0"]["primaryMethod"] == "hargreaves"
    assert "emulator" not in scenario["et0"]["methods"]
    assert scenario["et0"]["terms"]["radiationMm"] is None
    assert scenario["et0"]["methods"]["hargreaves"]["requires"] == (
        "daily tmax, tmin, latitude and day of year")
    assert scenario["et0"]["valueMmPerDay"] > 0


def test_water_area_scales_the_volume_and_not_the_flux(client):
    small = {**DHAKA, "growingAreaM2": 5.0}
    large = {**DHAKA, "growingAreaM2": 20.0}
    body = client.post(WATER + "/run", json={"scenarios": [small, large]}).json()
    a, b = body["scenarios"]
    assert b["demand"]["et0Reference"]["litresPerDay"] == pytest.approx(
        4 * a["demand"]["et0Reference"]["litresPerDay"], rel=1e-4)
    assert b["demand"]["et0Reference"]["mmPerDay"] == pytest.approx(
        a["demand"]["et0Reference"]["mmPerDay"], rel=1e-6)


def test_water_per_plant_figure_is_absent_unless_density_is_supplied(client):
    without = {k: v for k, v in DHAKA.items() if k != "plantsPerM2"}
    body = client.post(WATER + "/run", json={"scenarios": [without]}).json()
    assert body["scenarios"][0]["demand"]["et0Reference"]["litresPerPlantPerDay"] is None
    with_density = client.post(WATER + "/run", json={"scenarios": [DHAKA]}).json()
    per_plant = with_density["scenarios"][0]["demand"]["et0Reference"]["litresPerPlantPerDay"]
    assert per_plant == pytest.approx(
        with_density["scenarios"][0]["demand"]["et0Reference"]["litresPerDay"] / (25.0 * 10.0),
        abs=1e-3)


def test_water_measured_bench_is_served_for_lettuce_with_its_caveat(client):
    body = client.post(WATER + "/run", json={"scenarios": [DHAKA]}).json()
    bench = body["scenarios"][0]["measuredBench"]
    assert bench["available"] is True
    assert bench["applies"] is True
    assert bench["measuredMlPerPotPerDay"] > 0
    assert bench["measuredDates"] == 11
    assert bench["hashVerified"] is True
    assert bench["study"]["doi"] == "10.5281/zenodo.5550230"
    assert "pot surface area is not published" in bench["comparisonCaveat"]


def test_water_refuses_to_extrapolate_the_lettuce_measurement_to_another_crop(client):
    tomato = {**DHAKA, "crop": "tomato"}
    body = client.post(WATER + "/run", json={"scenarios": [tomato]}).json()
    bench = body["scenarios"][0]["measuredBench"]
    assert bench["applies"] is False
    assert bench["measuredMlPerPotPerDay"] is None
    assert "no measurement" in bench["reason"].lower()
    # The computed demand is still produced; only the measurement is withheld.
    assert body["scenarios"][0]["demand"]["et0Reference"]["litresPerDay"] > 0


def test_water_deltas_are_relative_to_the_first_scenario(client):
    body = client.post(WATER + "/run", json={"scenarios": [DHAKA, HOT]}).json()
    base = body["scenarios"][0]["demand"]["et0Reference"]["litresPerDay"]
    delta = body["comparison"]["deltas"][0]
    assert delta["vs"] == body["scenarios"][0]["label"]
    assert delta["demandLPerDayDelta"] == pytest.approx(
        body["scenarios"][1]["demand"]["et0Reference"]["litresPerDay"] - base, abs=1e-2)
    assert delta["demandPctDelta"] == pytest.approx(100 * delta["demandLPerDayDelta"] / base, abs=1e-2)


def test_water_rejects_an_unsupported_crop_and_an_impossible_area(client):
    assert client.post(WATER + "/run", json={
        "scenarios": [{**DHAKA, "crop": "maize"}]}).status_code == 422
    assert client.post(WATER + "/run", json={
        "scenarios": [{**DHAKA, "growingAreaM2": 0}]}).status_code == 422
    assert client.post(WATER + "/run", json={"scenarios": []}).status_code == 422
    assert client.post(WATER + "/run", json={
        "scenarios": [{**DHAKA, "relativeHumidityPct": 120}]}).status_code == 422


def test_water_caps_the_number_of_scenarios(client):
    body = {"scenarios": [DHAKA] * 5}
    assert client.post(WATER + "/run", json=body).status_code == 422


# ------------------------------------------------ harvest: the removed capability
#
# Phase 28 shipped a harvest forecast whose model had not passed validation. Phase 30 evaluated
# it properly - leave-one-study-out over published studies the model had never seen - and it
# missed the 30 % criterion by more than a factor of ten, so the forecast was removed. Phase 31
# removed the remaining capability/parity endpoints and the UI tab as well: nothing is served, and
# nothing advertises a removed capability. The evaluations stay committed as data.


def test_the_harvest_surface_is_entirely_gone(client):
    for suffix in ("/run", "/capability", "/parity"):
        assert client.post(HARVEST + suffix, json={"scenarios": [GROWTH]}).status_code == 404
        assert client.get(HARVEST + suffix).status_code == 404
    assert not [p for p in _mounted_paths() if "harvest-prediction" in p]


def test_the_harvest_failure_record_is_retained_as_data(client):
    """Removal must not erase the reason. The record is in the repository, not in the API."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    records = list((root / "ml" / "evaluation").glob("*harvest*.json"))
    assert records, "harvest evaluation records must remain committed"
    assert (root / "docs" / "PHASE31_REMOVED_MODELS.md").is_file()


def test_the_old_harvest_controls_cannot_reach_anything(client):
    """The failure mode this platform has had: a control that validates and does nothing."""
    for body in ({"scenarios": [GROWTH]}, {"scenarios": [{"ppfdUmol": 400}]}, {}):
        assert client.post(HARVEST + "/run", json=body).status_code == 404


# ------------------------------------- controlled-environment wheat (measured, no model)


def test_cea_capability_is_measured_and_advertises_no_model(client):
    body = client.get(CEA + "/capability").json()
    assert body["evidenceClass"] == "measured-observation"
    assert body["isSimulation"] is False
    assert body["isModelPrediction"] is False
    assert body["dataset"]["doi"] == "10.5281/zenodo.17764612"
    assert body["dataset"]["license"] == "CC BY 4.0"
    model = body["predictiveModel"]
    assert model["attempted"] is True
    assert model["served"] is False
    assert model["criterion"] == 30.0
    assert model["holdoutMapePct"] > model["criterion"]
    # An attempted-and-failed response surface must remain inspectable, not be deleted.
    assert model["evidenceFile"].endswith(".json")
    for factor in body["factors"]:
        assert factor["publicName"] and factor["unit"] in units.UNITS
        assert sum(band["experiments"] for band in factor["bands"]) == body["dataset"]["experiments"]


def test_cea_bands_partition_the_measured_experiments(client):
    body = client.get(CEA + "/capability").json()
    for factor in body["factors"]:
        bands = [band["id"] for band in factor["bands"]]
        assert len(bands) == len(set(bands))
        assert all(band["experiments"] >= 0 for band in factor["bands"])
        assert sum(band["experiments"] for band in factor["bands"]) == body["dataset"]["experiments"]


def test_cea_factors_are_mapped_by_public_name(client):
    """Regression: the factor list exposed meanPpfdUmolPerM2S while the API accepted ppfdUmolPerM2S."""
    capability = client.get(CEA + "/capability").json()
    public = {factor["publicName"] for factor in capability["factors"]}
    offered = set(capability["fields"][0]["options"])
    assert offered == public
    for name in public:
        band = capability["fields"][1]["options"][name][0]
        response = client.post(CEA + "/run", json={"selections": [{"factor": name, "band": band}]})
        assert response.status_code == 200, name


def test_cea_returns_measured_group_summaries_without_a_claim_of_causation(client):
    body = client.post(CEA + "/run", json={"selections": [
        {"factor": "co2Ppm", "band": "ambient"},
        {"factor": "ppfdUmolPerM2S", "band": "high"},
    ]}).json()
    assert body["status"] == "complete"
    assert body["isModelPrediction"] is False
    groups = {group["band"]: group for group in body["groups"]}
    ambient, high = groups["ambient"], groups["high"]
    assert ambient["measured"]["n"] == 29 and high["measured"]["n"] == 7
    for group in (ambient, high):
        measured = group["measured"]
        assert measured["meanCiLow"] < measured["mean"] < measured["meanCiHigh"]
        assert measured["min"] <= measured["median"] <= measured["max"]
        assert group["unit"] == "kg/m2"
        # Every experiment id in a group is a real experiment, and the count matches.
        assert len(group["experiments"]) == measured["n"]
    assert high["measured"]["mean"] > ambient["measured"]["mean"]
    # The comparison is a measured difference, not a modelled effect, and it says so.
    difference = body["differences"][0]
    assert "not" in difference["note"].lower()
    assert body["method"]["unitOfIndependence"].startswith("experiment")
    assert "no significance test" in body["method"]["noTest"]


def test_cea_never_presents_the_dli_association_as_a_response_function(client):
    body = client.post(CEA + "/run", json={"selections": [CEA_SELECTION]}).json()
    relationship = body["dliRelationship"]
    assert -1.0 <= relationship["pearson"] <= 1.0
    assert -1.0 <= relationship["spearman"] <= 1.0
    assert "not a response function" in relationship["note"]
    assert body["predictiveModel"]["served"] is False


def test_cea_provenance_names_the_hash_verified_source(client):
    body = client.post(CEA + "/run", json={"selections": [CEA_SELECTION]}).json()
    provenance = body["provenance"]
    assert len(provenance["rawFileSha256"]) == 64
    assert provenance["verifiedAgainstManifest"] is True
    assert provenance["source"]["doi"] == "10.5281/zenodo.17764612"
    assert provenance["experimentRows"] == len({point["experimentId"]
                                                for point in body["dliRelationship"]["points"]})
    group_experiments = {experiment for group in body["groups"]
                         for experiment in group["experiments"]}
    assert group_experiments <= {point["experimentId"]
                                 for point in body["dliRelationship"]["points"]}


def test_cea_rejects_an_unknown_factor_band_and_too_many_selections(client):
    for body in ({"selections": [{"factor": "vpdKpa", "band": "ambient"}]},
                 {"selections": [{"factor": "co2Ppm", "band": "extreme"}]},
                 {"selections": [CEA_SELECTION] * 7},
                 {"selections": []},
                 {"selections": [{**CEA_SELECTION, "crop": "wheat"}]}):
        assert client.post(CEA + "/run", json=body).status_code == 422


def test_cea_run_is_deterministic(client):
    first = client.post(CEA + "/run", json={"selections": [CEA_SELECTION]}).json()
    second = client.post(CEA + "/run", json={"selections": [CEA_SELECTION]}).json()
    assert first["groups"] == second["groups"]
    assert first["rows"] == second["rows"]


def test_workflow_outputs_are_finite_and_unit_aware(client):
    cea = client.post(CEA + "/run", json={"selections": [CEA_SELECTION]}).json()
    group = cea["groups"][0]
    for key in ("mean", "median", "sd", "min", "max", "meanCiLow", "meanCiHigh"):
        assert math.isfinite(group["measured"][key])
    assert cea["units"]["grainYieldKgPerM2"]["unit"] == group["unit"] == "kg/m2"
    assert cea["units"]["grainYieldKgPerM2"]["registered"] is True
    water = client.post(WATER + "/run", json={"scenarios": [DHAKA]}).json()
    assert "et0MmPerDay" in water["units"]
    assert water["units"]["et0MmPerDay"]["unit"] == "mm/day"
