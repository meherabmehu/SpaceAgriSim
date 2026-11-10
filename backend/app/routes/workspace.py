"""Evidence-labelled scenario comparison, deterministic advice, optimization and exports."""
from __future__ import annotations

import csv
import io
import json
import logging
from itertools import product
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.models.simulation import SimulationRequest, strip_removed_fields
from app.routes.simulation import simulate
from app import mailer, observability, storage
from app.config.settings import settings
from app.auth import current_user

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
    # Phase 30 removed the fractional-gravity response, so a "Moon" or "Mars" scenario can no longer
    # differ from Earth by gravity. What still differs is the radiation environment, which is what
    # these named cases vary - and each name says so.
    for name, radiation in [("Earth background", 0.01), ("Lunar surface", 0.5),
                            ("Mars surface", 0.2)]:
        params = request.model_copy(update={"radiation": radiation})
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
                           "fixed":["crop","radiation","temperature","humidity","growingArea","simulationDays","waterRecyclingEfficiency"]},
            "limitations":LIMITATIONS+["Discrete candidate frontier, not a global optimum. Recommendation prioritizes yield; light input is not a modeled power demand."]}


class SaveScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1,max_length=100,pattern=r".*\S.*")
    configuration: SimulationRequest


@router.get("/scenarios")
def scenarios(user: dict = Depends(current_user)):
    try:
        rows = storage.list_scenarios(user["id"])
    except Exception as exc:
        logger.exception("Scenario history unavailable")
        raise HTTPException(503,"Scenario history unavailable; check database configuration") from exc
    for row in rows:
        row["configuration"] = json.loads(row["configuration"])
    return {"scenarios":rows,"scope":"private account scenario history"}


@router.get("/scenarios/{scenario_id}")
def get_scenario(scenario_id: str, user: dict = Depends(current_user)):
    """Read back one saved scenario by id.

    Until this existed a scenario could only be listed, so there was no way for a client to prove
    that a specific saved configuration had been stored intact.
    """
    try:
        row = storage.get_scenario(user["id"], scenario_id)
    except Exception as exc:
        logger.exception("Scenario lookup unavailable")
        raise HTTPException(503,"Scenario history unavailable; check database configuration") from exc
    if row is None:
        # 404 rather than 403 for another account's id: the API must not be an existence oracle.
        raise HTTPException(404, "Scenario not found")
    row["configuration"] = json.loads(row["configuration"])
    return row


class UpdateScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=100, pattern=r".*\S.*")
    configuration: SimulationRequest | None = None


@router.patch("/scenarios/{scenario_id}")
def update_scenario(scenario_id: str, request: UpdateScenario,
                    user: dict = Depends(current_user)):
    """Rename and/or replace the configuration of one owned scenario."""
    if not settings.history_writes_enabled:
        raise HTTPException(403,"Shared history writes are disabled by the operator")
    if request.name is None and request.configuration is None:
        raise HTTPException(422, "Supply a name, a configuration, or both")
    try:
        row = storage.update_scenario(
            user["id"], scenario_id,
            name=request.name.strip() if request.name is not None else None,
            configuration=(request.configuration.model_dump_json()
                           if request.configuration is not None else None))
    except Exception as exc:
        logger.exception("Scenario update unavailable")
        raise HTTPException(503,"Scenario history unavailable; check database configuration") from exc
    if row is None:
        raise HTTPException(404, "Scenario not found")
    storage.record_activity(user["id"], "scenario-updated")
    row["configuration"] = json.loads(row["configuration"])
    return row


@router.delete("/scenarios/{scenario_id}", status_code=204)
def delete_scenario(scenario_id: str, user: dict = Depends(current_user)):
    """Delete one owned scenario and any share links that pointed at it.

    Erasure is allowed even when history writes are disabled: an account's own data is not a
    write the operator's policy switch was meant to block.
    """
    try:
        deleted = storage.delete_scenario(user["id"], scenario_id)
    except Exception as exc:
        logger.exception("Scenario deletion unavailable")
        raise HTTPException(503,"Scenario history unavailable; check database configuration") from exc
    if not deleted:
        raise HTTPException(404, "Scenario not found")
    storage.record_activity(user["id"], "scenario-deleted")
    return Response(status_code=204)


@router.post("/scenarios",status_code=201)
def save_scenario(request: SaveScenario, user: dict = Depends(current_user)):
    if not settings.history_writes_enabled:
        raise HTTPException(403,"Shared history writes are disabled by the operator")
    try:
        row = storage.save_scenario(request.name.strip(), request.configuration.model_dump_json(), user["id"])
    except Exception as exc:
        logger.exception("Scenario save unavailable")
        raise HTTPException(503,"Scenario history unavailable; check database configuration") from exc
    row["configuration"] = json.loads(row["configuration"])
    return row


# ---------------------------------------------------------------------------------------------
# Share links (Phase 19)
#
# A share link is read-only and deliberately one-way: it exposes the saved configuration and the
# numbers that configuration reproduces, never the owner's address or the rest of their history.
# Links are capped per scenario, expire, and can be revoked wholesale.
# ---------------------------------------------------------------------------------------------

SHARE_DISCLAIMER = ("Read-only shared scenario. Exploratory mathematical estimates; not "
                    "independently calibrated or NASA validated.")


@router.post("/scenarios/{scenario_id}/share", status_code=201)
def share_scenario(scenario_id: str, user: dict = Depends(current_user)):
    try:
        token = storage.create_share_link(scenario_id, user["id"], settings.share_link_days)
    except storage.ShareLimitReached as exc:
        raise HTTPException(409, f"This scenario already has {exc.limit} active share links; "
                                 "revoke them before creating another") from exc
    except Exception as exc:
        logger.exception("Share link creation unavailable")
        raise HTTPException(503, "Share links unavailable; check database configuration") from exc
    if token is None:
        # Same answer for "does not exist" and "belongs to someone else".
        raise HTTPException(404, "Scenario not found")
    storage.record_activity(user["id"], "share-link-created")
    return {"token": token, "url": f"/shared/{token}", "expiresInDays": settings.share_link_days,
            "scope": "read-only; no account data", "disclaimer": SHARE_DISCLAIMER}


@router.delete("/scenarios/{scenario_id}/share")
def unshare_scenario(scenario_id: str, user: dict = Depends(current_user)):
    try:
        revoked = storage.revoke_share_links(scenario_id, user["id"])
    except Exception as exc:
        logger.exception("Share link revocation unavailable")
        raise HTTPException(503, "Share links unavailable; check database configuration") from exc
    if not revoked:
        raise HTTPException(404, "No active share links for this scenario")
    storage.record_activity(user["id"], "share-link-revoked")
    return {"revoked": revoked}


@router.get("/shared/{token}")
def shared_scenario(token: str):
    """Public, unauthenticated, read-only view of one shared scenario."""
    if not 16 <= len(token) <= 200:
        raise HTTPException(404, "Shared scenario not found")
    try:
        row = storage.resolve_share_link(token)
    except Exception as exc:
        logger.exception("Shared scenario lookup unavailable")
        raise HTTPException(503, "Share links unavailable; check database configuration") from exc
    if row is None:
        raise HTTPException(404, "Shared scenario not found or no longer available")
    configuration = json.loads(row["configuration"])
    return {"name": row["name"], "configuration": configuration,
            "createdAt": row["created_at"], "modelVersion": row["model_version"],
            "expiresAt": row["expires_at"],
            # Reproduced from the stored configuration rather than stored alongside it, so a
            # shared page always shows what the current model produces for that input.
            "result": run(SimulationRequest(**strip_removed_fields(configuration))),
            "scope": "public read-only share", "disclaimer": SHARE_DISCLAIMER,
            "limitations": LIMITATIONS}


def _pool_status() -> dict:
    """Pool capacity for the readiness payload. Never raises: readiness must still answer."""
    try:
        return storage.pool_status()
    except Exception as exc:  # noqa: BLE001 - a diagnostic must not break the probe
        logger.warning("Readiness: pool inspection failed (%s)", type(exc).__name__)
        return {"dialect": None, "pooled": False, "error": type(exc).__name__}


@router.get("/ready")
def readiness():
    try:
        database_status = storage.database_health()
    except storage.DatabaseConfigurationError as exc:
        # A misconfigured URL is the operator's problem to fix, so say which way it is wrong
        # instead of the bare "Database unavailable" that hid it. No URL, host or password here.
        observability.record_db_failure("configuration")
        logger.error("Readiness: database configuration rejected (%s)", exc.reason)
        raise HTTPException(503, {
            "error": "database_misconfigured",
            "message": f"Database unavailable: {exc.detail}",
            "reason": exc.reason,
            "remedy": "Set SPACEAGRISIM_DATABASE_URL to a sqlite:/// path or a PostgreSQL URL; "
                      "postgres:// and postgresql:// are accepted and mapped to the psycopg driver.",
        }) from exc
    except Exception as exc:
        logger.exception("Readiness database check failed")
        observability.record_db_failure("connect")
        diagnosis = storage._driver_diagnosis(exc)
        # A SQLSTATE means the server answered and rejected us; no SQLSTATE means the connection
        # never got that far, which is a different job for the operator.
        remedy = (
            "The database server answered and refused the connection. The SQLSTATE says why: "
            "28P01 is a rejected password, 3D000 a database that does not exist."
            if diagnosis.get("sqlstate") else
            "The connection never reached a database server, so there is no SQLSTATE to read. "
            "Check the host and port in SPACEAGRISIM_DATABASE_URL, and whether the instance still "
            "exists and is running; a suspended or deleted managed database fails exactly this way."
        )
        raise HTTPException(503, {
            "error": "database_unavailable",
            "message": f"Database unavailable: {type(exc).__name__}",
            "reason": "connection-failed",
            # SQLSTATE and exception type only; the driver's message contains the host.
            **diagnosis,
            "remedy": remedy,
        }) from exc
    # A registered migration that has not applied is a deployment that skipped a step. Read-only
    # inspection, no DDL: this endpoint must never change the schema it is reporting on.
    try:
        migrations = storage.migration_state()
    except Exception as exc:  # noqa: BLE001 - the readiness answer must not itself raise
        logger.exception("Readiness: migration inspection failed")
        migrations = {"applied": [], "pending": [], "appliedCount": 0, "pendingCount": None,
                      "total": None, "error": type(exc).__name__}

    if database_status.get("status") != "available":
        # Reachable server with no schema at all. Checked before the migration list so an operator
        # gets "the schema was never created" rather than a list of every step: the pending ids are
        # still included, but the headline says what actually happened. Saying "ready" here is how
        # a half-migrated deployment serves 500s while the probe stays green.
        raise HTTPException(503, {
            "error": "database_schema_incomplete",
            "message": ("Database reachable but its schema is incomplete; the migration has not "
                        "run against this database"),
            "reason": "schema-incomplete",
            "missingTables": [name for name in database_status.get("missingTables", "").split(",")
                              if name],
            "pendingMigrations": [item["id"] for item in migrations.get("pending") or []],
            "remedy": ("Start the application once with the configured database URL so the "
                       "additive migration runs, then re-check /api/ready."),
        })
    # Columns or indexes missing on an otherwise-initialised schema: the deployment reached the
    # database but skipped an additive step.
    if migrations.get("pending"):
        raise HTTPException(503, {
            "error": "database_migration_pending",
            "message": "Database reachable but required migrations have not been applied",
            "reason": "migration-pending",
            "pendingMigrations": [item["id"] for item in migrations["pending"]],
            "missing": [missing for item in migrations["pending"] for missing in item["missing"]],
            "remedy": ("Restart the service once against this database so the additive migration "
                       "runs, then re-check /api/ready. The migration never drops or rewrites "
                       "existing rows."),
        })
    return {"status":"ready","simulation":"available","database":database_status["status"],"databaseDialect":database_status["dialect"],
            "databaseSchema":database_status.get("schema","present"),
            "databaseMigrations":{"applied":migrations.get("appliedCount"),"total":migrations.get("total"),
                                  "pending":migrations.get("pendingCount")},
            "databasePool":_pool_status(),
            # Phase 19: an operator can see from /ready whether saved data survives a restart and
            # whether account email can actually be delivered, instead of finding out from a user.
            "storage":storage.storage_durability(),
            "emailDelivery":mailer.delivery_mode(),
            "shareLinks":settings.max_share_links_per_scenario > 0,
            # Which address the request budget is charged to. "socket" behind a gateway means
            # every caller shares one budget; set SPACEAGRISIM_TRUSTED_PROXY_HOPS after checking
            # the forwarding chain on the actual platform.
            "rateLimitIdentity":("forwarded" if settings.trusted_proxy_hops else "socket"),
            # Whether the operator surface is configured. The token itself is never echoed.
            "operatorConsole":bool(settings.admin_token),
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
