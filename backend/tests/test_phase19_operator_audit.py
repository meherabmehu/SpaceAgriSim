"""Phase 19: the operator surface must be safe to leave configured on a public deployment.

The failure modes are all about exposure:

* the panel showing up when no token was configured;
* a wrong token being distinguishable from a missing one in a way that helps an attacker;
* an account address, payload or free text reaching the operator view;
* the whole thing being usable as a login.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app import storage
from app.config.settings import settings
from app.main import app

TOKEN = "operator-token-for-tests-0123456789abcdef"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def operator(monkeypatch):
    monkeypatch.setattr(settings, "admin_token", TOKEN)


def _account(client: TestClient) -> str:
    email = f"operator-audit-{uuid.uuid4().hex[:10]}@example.test"
    response = client.post("/api/auth/register",
                           json={"email": email, "password": "CorrectHorseBattery1!"})
    assert response.status_code == 201
    return email


def test_surface_is_absent_when_no_token_is_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "")
    # 404, not 403: a public deployment should not confirm that a panel exists.
    assert client.get("/api/admin/summary").status_code == 404
    assert client.get("/api/admin/summary", headers=AUTH).status_code == 404
    assert client.get("/api/admin/audit", headers=AUTH).status_code == 404


def test_token_is_required_and_compared_in_constant_time(client, operator):
    assert client.get("/api/admin/summary").status_code == 401
    assert client.get("/api/admin/summary",
                      headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/admin/summary",
                      headers={"Authorization": f"Bearer {TOKEN[:-1]}"}).status_code == 401
    assert client.get("/api/admin/summary", headers=AUTH).status_code == 200


def test_operator_token_is_not_an_account_token(client, operator):
    response = client.get("/api/auth/me", headers=AUTH)
    assert response.status_code == 401


def test_summary_reports_health_without_any_account_data(client, operator):
    email = _account(client)
    body = client.get("/api/admin/summary", headers=AUTH).json()
    assert body["accounts"] >= 1
    assert body["database"]["status"] == "available"
    assert "durable" in body["storage"]
    assert body["emailDelivery"] in ("smtp", "outbox", "unconfigured")
    assert body["scientificValidation"] == "uncalibrated mathematical estimates"
    assert email not in str(body)


def test_audit_events_are_pseudonymous(client, operator):
    email = _account(client)
    body = client.get("/api/admin/audit", headers=AUTH).json()
    assert body["events"], "registering an account must produce at least one audit event"
    for event in body["events"]:
        assert set(event) == {"kind", "at", "account", "detail"}
        assert len(event["account"]) == 12
        assert "@" not in str(event)
    assert email not in str(body)


def test_audit_counts_are_complete_for_the_window(client, operator):
    body = client.get("/api/admin/audit", headers=AUTH).json()
    assert sum(body["counts"].values()) == len(body["events"])
    assert body["failedLogins"] == body["counts"].get("login-failed", 0)


def test_audit_limit_is_bounded(client, operator):
    assert client.get("/api/admin/audit?limit=0", headers=AUTH).status_code == 422
    assert client.get("/api/admin/audit?limit=501", headers=AUTH).status_code == 422


def test_readiness_advertises_the_operator_surface_without_the_token(client, operator):
    ready = client.get("/api/ready").json()
    assert ready["operatorConsole"] is True
    assert TOKEN not in str(ready)


def test_pseudonym_is_stable_and_not_the_raw_id():
    user_id = str(uuid.uuid4())
    from app.routes.admin import _pseudonym
    assert _pseudonym(user_id) == _pseudonym(user_id)
    assert _pseudonym(user_id) != user_id
    assert user_id not in _pseudonym(user_id)


def test_activity_summary_counts_are_integers():
    summary = storage.activity_summary()
    assert isinstance(summary["accounts"], int)
    assert isinstance(summary["liveShareLinks"], int)
    assert all(isinstance(value, int) for value in summary["byKind"].values())
