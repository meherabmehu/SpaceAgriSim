"""Phase 28: the two complete workflows, tested from the outside in.

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
WATER = "/api/workflows/water-demand"

DHAKA = {
    "crop": "lettuce", "growingAreaM2": 10.0, "daysAfterTransplant": 20,
    "tmaxC": 33.0, "tminC": 22.0, "relativeHumidityPct": 55.0,
    "solarRadiationMJm2": 20.0, "windSpeedMs": 2.0, "dayOfYear": 80,
    "latitude": 23.8, "elevationM": 8.0, "plantsPerM2": 25.0,
}
HOT = {**DHAKA, "label": "hot", "tmaxC": 38.0, "tminC": 27.0,
       "relativeHumidityPct": 35.0, "solarRadiationMJm2": 26.0, "windSpeedMs": 3.5}
GROWTH = {
    "daysAfterTransplant": 21.0, "airTemperature": 24.0, "rootTemperature": 24.0,
    "ppfd": 400.0, "photoperiodHours": 16.0, "plantDensityPerM2": 25.0,
}


# ----------------------------------------------------------------- the catalogue


def test_catalogue_lists_two_complete_workflows_and_the_gap(client):
    body = client.get("/api/workflows").json()
    ids = [item["id"] for item in body["workflows"]]
    assert ids == ["water-demand", "harvest-prediction"]
    assert all(item["status"] == "complete" for item in body["workflows"])

    harvest = next(item for item in body["workflows"] if item["id"] == "harvest-prediction")
    # The model's own status is carried in the catalogue: a workflow can be complete while the
    # model behind it is not validated, and the API must not conflate the two.
    assert harvest["modelStatus"] == "trained-exploratory"
    assert harvest["modelValidatedForForecasting"] is False

    gaps = {gap["id"]: gap for gap in body["documentedGaps"]}
    assert gaps["environmental-stress"]["status"] == "not-complete"
    assert "warning" in gaps["environmental-stress"]["blocker"]


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


def test_units_returned_by_both_workflows_are_registered(client):
    water = client.post(WATER + "/run", json={"scenarios": [DHAKA]}).json()
    harvest = client.post(HARVEST + "/run", json={"scenarios": [GROWTH]}).json()
    for payload in (water, harvest):
        for name in _unit_names(payload):
            assert name in units.UNITS, f"unregistered unit {name!r}"


def test_every_quantity_in_the_units_map_has_a_dimension(client):
    for path, body in ((WATER + "/run", {"scenarios": [DHAKA]}),
                       (HARVEST + "/run", {"scenarios": [GROWTH]})):
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

    The project's own study found the trained emulator beats Hargreaves on an unseen site, so the
    fallback order is emulator first, physics second; the test accepts either and demands the
    response say which. Pinning "hargreaves" here would have encoded a false claim.
    """
    no_radiation = {k: v for k, v in DHAKA.items() if k not in ("solarRadiationMJm2", "windSpeedMs")}
    body = client.post(WATER + "/run", json={"scenarios": [no_radiation]}).json()
    scenario = body["scenarios"][0]
    assert scenario["et0"]["primaryMethod"] in ("emulator", "hargreaves")
    assert scenario["et0"]["primaryMethod"] != "penman-monteith"
    assert scenario["et0"]["terms"]["radiationMm"] is None
    assert scenario["et0"]["methods"]["hargreaves"]["requires"] == "temperature and latitude only"
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


# ---------------------------------------------------------------- harvest workflow


def test_harvest_prediction_equals_the_served_model(client):
    """The workflow must not re-implement the model; it must call it."""
    body = client.post(HARVEST + "/run", json={"scenarios": [GROWTH]}).json()
    scenario = body["scenarios"][0]
    dli = GROWTH["ppfd"] * GROWTH["photoperiodHours"] * 3600.0 / 1e6
    model = research.load_model(body["model"]["id"])
    raw, _ = research.predict_values(model, [GROWTH["daysAfterTransplant"],
                                             GROWTH["airTemperature"],
                                             GROWTH["rootTemperature"], dli])
    per_area = research.inverse_target_transform(model, raw)
    assert scenario["prediction"]["perAreaYieldGPerM2"] == pytest.approx(round(per_area, 1))
    assert scenario["prediction"]["freshShootMassGPerPlant"] == pytest.approx(
        per_area / GROWTH["plantDensityPerM2"], abs=0.01)


def test_harvest_interval_brackets_the_prediction(client):
    body = client.post(HARVEST + "/run", json={"scenarios": [GROWTH]}).json()
    prediction = body["scenarios"][0]["prediction"]
    assert prediction["intervalLowG"] < prediction["freshShootMassGPerPlant"] < prediction["intervalHighG"]
    assert prediction["intervalOutOfFoldCoverage"] == pytest.approx(0.8993, abs=1e-3)
    assert "descriptive" in prediction["intervalCoverageNote"]


def test_harvest_light_and_photoperiod_both_matter(client):
    same_ppfd_shorter_day = {**GROWTH, "photoperiodHours": 12.0}
    brighter = {**GROWTH, "ppfd": 600.0}
    body = client.post(HARVEST + "/run",
                       json={"scenarios": [GROWTH, same_ppfd_shorter_day, brighter]}).json()
    base, short_day, bright = body["scenarios"]
    assert short_day["prediction"]["dailyLightIntegralMolPerM2Day"] < base["prediction"]["dailyLightIntegralMolPerM2Day"]
    assert short_day["prediction"]["freshShootMassGPerPlant"] < base["prediction"]["freshShootMassGPerPlant"]
    assert bright["prediction"]["freshShootMassGPerPlant"] > base["prediction"]["freshShootMassGPerPlant"]


def test_harvest_density_converts_per_area_into_per_plant(client):
    dense = {**GROWTH, "plantDensityPerM2": 50.0}
    body = client.post(HARVEST + "/run", json={"scenarios": [GROWTH, dense]}).json()
    base, dense_result = body["scenarios"]
    assert dense_result["prediction"]["perAreaYieldGPerM2"] == pytest.approx(
        base["prediction"]["perAreaYieldGPerM2"], rel=1e-6)
    assert dense_result["prediction"]["freshShootMassGPerPlant"] == pytest.approx(
        base["prediction"]["freshShootMassGPerPlant"] / 2.0, rel=1e-3)


def test_harvest_warns_outside_the_measured_domain_instead_of_refusing(client):
    hot = {**GROWTH, "airTemperature": 35.0, "rootTemperature": 35.0}
    body = client.post(HARVEST + "/run", json={"scenarios": [hot]}).json()
    scenario = body["scenarios"][0]
    assert scenario["validation"]["insideTrainingDomain"] is False
    assert scenario["validation"]["warnings"]
    assert any("airTemperature" in warning for warning in scenario["validation"]["warnings"])
    # One warning per out-of-range feature, not a duplicate from the model layer.
    assert len(scenario["validation"]["warnings"]) == len(set(scenario["validation"]["warnings"]))
    assert scenario["prediction"]["freshShootMassGPerPlant"] > 0


def test_harvest_warns_when_density_leaves_the_identity_range(client):
    body = client.post(HARVEST + "/run",
                       json={"scenarios": [{**GROWTH, "plantDensityPerM2": 500.0}]}).json()
    scenario = body["scenarios"][0]
    assert scenario["prediction"]["densityInsideSupportedRange"] is False
    assert any("plantDensityPerM2" in warning for warning in scenario["validation"]["warnings"])


def test_harvest_keeps_the_failed_predecessor_visible(client):
    body = client.post(HARVEST + "/run", json={"scenarios": [GROWTH]}).json()
    record = body["scenarios"][0]["recordPrediction"]
    assert record["modelId"] == "lettuce-earth-growth-v2"
    assert record["freshShootMassGPerPlant"] > 0
    # v2 cannot express photoperiod or density; saying so is the point of showing it at all.
    assert set(record["ignoresInputs"]) == {"photoperiodHours", "plantDensityPerM2"}


def test_harvest_reports_the_failed_independent_holdout(client):
    body = client.post(HARVEST + "/run", json={"scenarios": [GROWTH]}).json()
    independent = body["validation"]["independentCheck"]
    assert independent["passed"] is False
    assert independent["acceptanceCriterionPct"] == 30.0
    assert independent["metrics"]["MAPE"] > 30.0
    assert "not validated for harvest forecasting" in independent["verdict"]
    assert body["modelValidatedForForecasting"] is False
    # The workflow itself is complete; only the model is unvalidated.
    assert body["workflowComplete"] is True


def test_harvest_does_not_count_development_data_as_validation(client):
    body = client.post(HARVEST + "/run", json={"scenarios": [GROWTH]}).json()
    development = body["validation"]["developmentCheck"]
    assert development["countsAsValidation"] is False
    assert development["usedForModelSelection"] is True


def test_harvest_comparison_refuses_to_overclaim_a_difference(client):
    body = client.post(HARVEST + "/run",
                       json={"scenarios": [GROWTH, {**GROWTH, "daysAfterTransplant": 22.0}]}).json()
    delta = body["comparison"]["deltas"][0]
    assert delta["intervalsOverlap"] in (True, False)
    if delta["intervalsOverlap"]:
        assert delta["distinguishableAtStatedCoverage"] is False
        assert "cannot tell these two scenarios apart" in delta["note"]


def test_harvest_parity_matches_the_artifact_and_labels_the_sets(client):
    body = client.get(HARVEST + "/parity").json()
    model = research.load_model(body["modelId"])
    development = model["validation"]["development"]["scored"]
    independent = model["validation"]["independent"]["scored"]
    assert len(body["points"]) == len(development) + len(independent) == 7
    sets = {point["set"] for point in body["points"]}
    assert sets == {"development", "independent"}
    for point in body["points"]:
        expected = "independent" if point["set"] == "independent" else "development"
        assert point["countsAsValidation"] is (expected == "independent")
    assert body["passed"] is False
    assert "overpredicts" in body["caveat"]


def test_harvest_requires_every_feature(client):
    response = client.post(HARVEST + "/run", json={"scenarios": [{"daysAfterTransplant": 21}]})
    assert response.status_code == 422
    partial = client.post(HARVEST + "/run", json={"scenarios": [{
        "daysAfterTransplant": 21, "airTemperature": 24, "rootTemperature": 24}]})
    assert partial.status_code == 422


def test_harvest_rejects_unknown_fields_rather_than_ignoring_them(client):
    """A typo must not silently leave a control unwired — the failure this platform has had."""
    response = client.post(HARVEST + "/run", json={"scenarios": [{**GROWTH, "ppfdUmol": 400}]})
    assert response.status_code == 422


def test_harvest_capability_explains_every_control(client):
    body = client.get(HARVEST + "/capability").json()
    assert body["intervalAvailable"] is True
    assert body["unmeasuredCrops"] == ["tomato", "radish"]
    for field in body["fields"]:
        assert field["unit"] in units.UNITS
        assert field["why"].strip()
        assert field["max"] > field["min"]


def test_harvest_run_is_deterministic(client):
    first = client.post(HARVEST + "/run", json={"scenarios": [GROWTH]}).json()
    second = client.post(HARVEST + "/run", json={"scenarios": [GROWTH]}).json()
    assert first["scenarios"][0]["prediction"] == second["scenarios"][0]["prediction"]


def test_workflow_outputs_are_finite_and_unit_aware(client):
    harvest = client.post(HARVEST + "/run", json={"scenarios": [GROWTH]}).json()
    prediction = harvest["scenarios"][0]["prediction"]
    for key in ("freshShootMassGPerPlant", "perAreaYieldGPerM2", "intervalLowG",
                "intervalHighG", "dailyLightIntegralMolPerM2Day"):
        assert math.isfinite(prediction[key])
        assert key in harvest["units"], f"{key} has no declared unit"
    water = client.post(WATER + "/run", json={"scenarios": [DHAKA]}).json()
    assert "et0MmPerDay" in water["units"]
    assert water["units"]["et0MmPerDay"]["unit"] == "mm/day"
