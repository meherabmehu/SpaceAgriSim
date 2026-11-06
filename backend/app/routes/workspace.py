"""Evidence-labelled scenario comparison, deterministic advice, optimization and exports."""
from __future__ import annotations

import csv
import io
import json
import logging
from itertools import product
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import text

from app.models.simulation import SimulationRequest
from app.routes.simulation import simulate
from app import storage
from app import research
from app.config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["mission workspace"])
LIMITATIONS = [
    "Exploratory mathematical estimates; not independently calibrated or NASA validated.",
    "No empirical prediction interval is available. Sensitivity is not uncertainty calibration.",
    "Radiation presets are hypothetical absorbed dose rates and do not encode habitat shielding.",
    "No crew safety, disease, nutrient, power-budget or thermal engineering certification is implied.",
]


def run(request: SimulationRequest):
    return simulate(request).model_dump()


@router.post("/compare")
def compare(request: SimulationRequest):
    scenarios = []
    for name, gravity, radiation in [("Earth", 1.0, 0.01), ("Moon", 0.16, 0.5), ("Mars", 0.38, 0.2)]:
        params = request.model_copy(update={"gravity": gravity, "radiation": radiation})
        scenarios.append({"name": name, "result": run(params)})
    scenarios.append({"name": "Custom habitat", "result": run(request)})
    return {"scenarios": scenarios, "method": "matched-resource hypothetical habitats", "limitations": LIMITATIONS}


@router.post("/advisor")
def advisor(request: SimulationRequest):
    result = run(request)
    insights = []
    factors = result["space"]["factors"]
    ranked = sorted(((k,v) for k,v in factors.items() if k != "combined"), key=lambda x:x[1])
    for key, value in ranked[:3]:
        insights.append({"title": f"{key.title()} response", "severity": "warning" if value < .8 else "info",
                         "text": f"The assumed {key} multiplier is {value:.4f}; 1.0 is the model reference. This is a model response, not a measured stress probability.",
                         "source": "assumptions-2.0 deterministic factor evaluation"})
    water = result["lifeSupport"]["water"]
    insights.append({"title": "Water loop", "severity": "warning" if water["deficit"] else "info",
        "text": f"Estimated supply is {water['supplied']:.2f} L, deficit {water['deficit']:.2f} L and fresh make-up {water['netConsumed']:.2f} L over the mission.",
        "source": "water balance: demand = supplied + deficit; make-up = supplied - recovered"})
    insights.append({"title": "Training coverage", "severity": "warning",
        "text": "These crop-growth outputs use the transparent mathematical engine. NASA molecular or image data are not direct validation of biomass, water demand or gas exchange.",
        "source": "prediction provenance"})
    return {"insights": insights, "limitations": LIMITATIONS, "mode": "deterministic scientific advisor", "result": result}


@router.post("/optimize")
def optimize(request: SimulationRequest):
    # Fixed bounded search; environmental hazards, crop, area and mission length are held constant.
    # 81 candidates: no unbounded numerical optimization in an HTTP worker.
    candidates = []
    baseline = run(request)
    for light, water, co2, intensity in product((12.0, 16.0, 18.0), (70.0, 85.0, 100.0),
                                                (420.0, 800.0, 1200.0), (200.0, 300.0, 450.0)):
        params = request.model_copy(update={"lightHours": light, "waterAvailability": water,
                                           "co2Level": co2, "lightIntensity": intensity})
        result = run(params)
        candidates.append({"configuration": params.model_dump(), "yieldG": result["cropYield"],
                           "netWaterL": result["lifeSupport"]["water"]["netConsumed"],
                           "oxygenG": result["estimatedOxygenProduced"],
                           "dailyLightIntegral": result["environment"]["dailyLightIntegralMolM2"]})
    frontier = []
    # Maximize biomass, minimize make-up water AND light input (proxy, not power).
    for item in candidates:
        dominated = any(other["yieldG"] >= item["yieldG"] and other["netWaterL"] <= item["netWaterL"]
                        and other["dailyLightIntegral"] <= item["dailyLightIntegral"]
                        and (other["yieldG"] > item["yieldG"] or other["netWaterL"] < item["netWaterL"]
                             or other["dailyLightIntegral"] < item["dailyLightIntegral"])
                        for other in candidates)
        if not dominated:
            frontier.append(item)
    frontier.sort(key=lambda item: item["yieldG"])
    max_yield = max(item["yieldG"] for item in frontier)
    # Highest-yield point with lowest water and then light among ties.
    recommendation = min((p for p in frontier if p["yieldG"] == max_yield),
                         key=lambda p:(p["netWaterL"], p["dailyLightIntegral"]))
    sensitivity = []
    for field, value in [("lightIntensity", min(request.lightIntensity+50,1000)),
                          ("lightHours", min(request.lightHours+1,24)),
                          ("waterAvailability", min(request.waterAvailability+5,100)),
                          ("temperature", min(request.temperature+1,40)),
                          ("humidity", min(request.humidity+5,100))]:
        trial = run(request.model_copy(update={field:value}))
        sensitivity.append({"parameter":field,"baselineInput":getattr(request,field),"trialInput":value,
                            "yieldDeltaG":round(trial["cropYield"]-baseline["cropYield"],1),
                            "netWaterDeltaL":round(trial["lifeSupport"]["water"]["netConsumed"]-
                                                   baseline["lifeSupport"]["water"]["netConsumed"],2)})
    return {"baseline": {"configuration": request.model_dump(), "yieldG":baseline["cropYield"],
                         "netWaterL":baseline["lifeSupport"]["water"]["netConsumed"]},
            "pareto":frontier,"recommendation":recommendation,"sensitivity":sensitivity,
            "candidateCount":len(candidates),"method":"bounded discrete Pareto search",
            "constraints":{"lightHours":[12,16,18],"waterAvailability":[70,85,100],
                           "co2Level":[420,800,1200],"lightIntensity":[200,300,450],
                           "fixed":["crop","gravity","radiation","temperature","humidity","growingArea","simulationDays","waterRecyclingEfficiency"]},
            "limitations":LIMITATIONS+["Discrete candidate frontier, not a global optimum. Recommendation prioritizes yield; light input is not a modeled power demand."]}


class SaveScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1,max_length=100,pattern=r".*\S.*")
    configuration: SimulationRequest


@router.get("/scenarios")
def scenarios():
    try:
        rows = storage.list_scenarios()
    except Exception as exc:
        logger.exception("Scenario history unavailable")
        raise HTTPException(503,"Scenario history unavailable; check database configuration") from exc
    for row in rows:
        row["configuration"] = json.loads(row["configuration"])
    return {"scenarios":rows,"scope":"shared workspace history; do not store sensitive information"}


@router.post("/scenarios",status_code=201)
def save_scenario(request: SaveScenario):
    if not settings.history_writes_enabled:
        raise HTTPException(403,"Shared history writes are disabled by the operator")
    try:
        row = storage.save_scenario(request.name.strip(), request.configuration.model_dump_json())
    except Exception as exc:
        logger.exception("Scenario save unavailable")
        raise HTTPException(503,"Scenario history unavailable; check database configuration") from exc
    row["configuration"] = json.loads(row["configuration"])
    return row


@router.get("/ready")
def readiness():
    try:
        with storage.database().connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        logger.exception("Readiness database check failed")
        raise HTTPException(503,"Database unavailable") from exc
    return {"status":"ready","simulation":"available","database":"available",
            "scientificValidation":"uncalibrated mathematical estimates"}


@router.post("/reports/{format}")
def report(format: Literal["json","csv","pdf"], request: SimulationRequest):
    result = run(request)
    headers = {"Content-Disposition":f'attachment; filename="spaceagrisim-mission.{format}"',
               "Cache-Control":"no-store"}
    if format == "json":
        return Response(json.dumps(result,indent=2),media_type="application/json",headers=headers)
    if format == "csv":
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(["# SpaceAgriSim: uncalibrated mathematical estimates, not NASA validated"])
        writer.writerow(["# configuration",request.model_dump_json()])
        writer.writerow(["day","standing_biomass_g","cumulative_biomass_g","harvested_g",
                         "water_supplied_L","water_recovered_L","co2_fixed_g","o2_produced_g"])
        for growth,life in zip(result["dailyGrowthData"],result["dailyLifeSupportData"]):
            writer.writerow([growth["day"],growth["spaceBiomass"],growth["spaceCumulative"],growth["spaceHarvested"],
                             life["waterUsed"],life["waterRecovered"],life["co2Removed"],life["o2Produced"]])
        return Response(stream.getvalue(),media_type="text/csv",headers=headers)
    buffer=io.BytesIO()
    pdf=canvas.Canvas(buffer,pagesize=A4)
    pdf.setTitle("SpaceAgriSim scientific mission report")
    y=800
    lines=["SPACEAGRISIM / MISSION REPORT","Uncalibrated mathematical estimates; not NASA validated.",
           "Model: assumptions-2.0. Empirical confidence interval: unavailable.","", "Reproducible configuration:"]
    lines += [f"{key}: {value}" for key,value in request.model_dump().items()]
    lines += ["", "Estimated outputs:",f"Cumulative edible fresh biomass: {result['cropYield']} g",
              f"Harvested: {result['harvest']['harvestedYield']} g",
              f"Standing: {result['harvest']['standingBiomass']} g",
              f"Supplied water: {result['waterUsed']} L",f"Recovered water: {result['waterRecovered']} L",
              f"CO2 fixed: {result['co2Removed']} g",f"O2 produced: {result['estimatedOxygenProduced']} g",
              "", "Limitations:"] + LIMITATIONS + ["", "Methodology: docs/SIMULATION_METHODOLOGY.md", "NASA dataset provenance is separate from crop simulation calibration."]
    import textwrap
    for line in lines:
        for segment in textwrap.wrap(line,width=92) or [""]:
            if y < 45:
                pdf.showPage(); y=800
            pdf.setFont("Helvetica",10)
            pdf.drawString(40,y,segment);y-=16
    pdf.save()
    return Response(buffer.getvalue(),media_type="application/pdf",headers=headers)
