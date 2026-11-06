import csv
import io
import json
import pytest
from app import storage
from app.config.settings import settings


def test_compare_has_matched_resources_and_actual_outputs(client):
    response=client.post("/api/compare",json={"simulationDays":7,"growingArea":2})
    assert response.status_code==200
    rows=response.json()["scenarios"]
    assert [row["name"] for row in rows]==["Earth","Moon","Mars","Custom habitat"]
    assert all(row["result"]["inputs"]["growingArea"]==2 for row in rows)
    assert rows[0]["result"]["cropYield"]>rows[1]["result"]["cropYield"]


def test_advisor_numerical_claims_use_simulation_output(client):
    result=client.post("/api/advisor",json={"waterAvailability":60}).json()
    water=result["result"]["lifeSupport"]["water"]
    insight=next(item for item in result["insights"] if item["title"]=="Water loop")
    assert f"{water['deficit']:.2f} L" in insight["text"]
    assert insight["severity"]=="warning"


def test_optimizer_frontier_is_not_dominated_and_keeps_hazards_fixed(client):
    response=client.post("/api/optimize",json={"simulationDays":7,"gravity":.38,"radiation":.2})
    assert response.status_code==200
    body=response.json()
    assert body["candidateCount"]==81
    assert len(body["pareto"])>0
    for point in body["pareto"]:
        assert point["configuration"]["gravity"]==.38
        assert point["configuration"]["radiation"]==.2
        for other in body["pareto"]:
            assert not (other["yieldG"]>point["yieldG"] and other["netWaterL"]<point["netWaterL"] and other["dailyLightIntegral"]<=point["dailyLightIntegral"])
    assert body["recommendation"]["yieldG"]==max(item["yieldG"] for item in body["pareto"])
    assert len(body["sensitivity"])==5


@pytest.mark.parametrize("format,content_type",[("json","application/json"),("csv","text/csv"),("pdf","application/pdf")])
def test_reports_are_real_downloadable_documents(client,format,content_type):
    response=client.post(f"/api/reports/{format}",json={"simulationDays":3})
    assert response.status_code==200
    assert response.headers["content-type"].startswith(content_type)
    assert f".{format}" in response.headers["content-disposition"]
    if format=="json":
        assert len(response.json()["dailyGrowthData"])==4
    elif format=="csv":
        rows=list(csv.reader(io.StringIO(response.text)))
        assert len(rows)==7
        assert rows[3][0]=="0"
    else:
        assert response.content.startswith(b"%PDF-")
        assert b"%%EOF" in response.content


def test_history_roundtrip_bounded_and_readiness(client,tmp_path,monkeypatch):
    storage.database.cache_clear()
    monkeypatch.setattr(settings,"database_url",f"sqlite:///{(tmp_path/'scenarios.db').as_posix()}")
    monkeypatch.setattr(settings,"max_history",2)
    try:
        for name in ("first","second","third"):
            response=client.post("/api/scenarios",json={"name":name,"configuration":{"crop":"radish"}})
            assert response.status_code==201,response.text
        rows=client.get("/api/scenarios").json()["scenarios"]
        assert len(rows)==2
        assert [row["name"] for row in rows]==["third","second"]
        assert rows[0]["configuration"]["crop"]=="radish"
        assert client.get("/api/ready").status_code==200
    finally:
        storage.database().dispose()
        storage.database.cache_clear()


def test_blank_scenario_name_rejected(client):
    assert client.post("/api/scenarios",json={"name":"   ","configuration":{}}).status_code==422


def test_request_guard_limits_body_and_attaches_request_id(client):
    assert client.get("/api/health").headers.get("x-request-id")
    response=client.post("/api/simulate",content="x"*65537)
    assert response.status_code==413
    assert response.json()["error"]=="body_too_large"


def test_request_guard_rate_limit_is_retryable():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.middleware import RequestGuard
    app=FastAPI()
    app.add_middleware(RequestGuard,max_per_minute=1)
    @app.get("/")
    def health():
        return {"status":"ok"}
    with TestClient(app) as client:
        assert client.get("/").status_code==200
        response=client.get("/")
        assert response.status_code==429
        assert response.headers["retry-after"]=="60"


def test_operator_can_disable_shared_history_writes(client,monkeypatch):
    monkeypatch.setattr(settings,"history_writes_enabled",False)
    response=client.post("/api/scenarios",json={"name":"test","configuration":{}})
    assert response.status_code==403
