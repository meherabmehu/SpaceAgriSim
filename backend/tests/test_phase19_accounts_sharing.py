"""Phase 19: account lifecycle, audit trail and share links.

These tests target the failure modes that are silent in production:

* a reset link that keeps working after use, or leaves the old password valid;
* a reset that does not invalidate sessions issued before it;
* an "email sent" response when no delivery channel is configured;
* an enumeration oracle in the forgot/verify endpoints;
* a share link that leaks owner data, never expires, or ignores revocation;
* an audit trail that grows without bound.
"""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app import mailer, storage
from app.config.settings import settings
from app.main import app

PASSWORD = "CorrectHorseBattery1!"
NEW_PASSWORD = "AnotherGoodPassphrase9!"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def _register(client: TestClient, label: str = "p19") -> tuple[dict, str]:
    email = f"{label}-{uuid.uuid4().hex[:10]}@example.test"
    response = client.post("/api/auth/register", json={"email": email, "password": PASSWORD})
    assert response.status_code in (200, 201), response.text
    body = response.json()
    return {"Authorization": f"Bearer {body['accessToken']}"}, email


def _token_for(email: str, subject: str = "SpaceAgriSim") -> str:
    message = mailer.last_message_for(email)
    assert message is not None, f"no message was queued for {email}"
    assert subject in message.subject
    return message.body.split("token=")[1].split()[0].strip()


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------

def test_registration_reports_an_unverified_address(client):
    headers, _ = _register(client, "verify-new")
    me = client.get("/api/auth/me", headers=headers).json()["user"]
    assert me["emailVerified"] is False


def test_verification_link_is_single_use(client):
    headers, email = _register(client, "verify-once")
    requested = client.post("/api/auth/verify/request", json={"email": email})
    assert requested.status_code == 202
    token = _token_for(email, "Verify")

    assert client.post("/api/auth/verify/confirm", json={"token": token}).json()["status"] == "verified"
    assert client.post("/api/auth/verify/confirm", json={"token": token}).status_code == 400
    assert client.get("/api/auth/me", headers=headers).json()["user"]["emailVerified"] is True


def test_verification_request_does_not_reveal_registration(client):
    known = client.post("/api/auth/verify/request", json={"email": "nobody-here@example.test"})
    assert known.status_code == 202
    assert known.json()["status"] == "accepted"
    assert "debugToken" not in known.json()


def test_verification_link_is_stored_only_as_a_hash(client):
    _, email = _register(client, "verify-hash")
    client.post("/api/auth/verify/request", json={"email": email})
    token = _token_for(email, "Verify")
    raw = json.dumps([dict(row._mapping) for row in _all("email_tokens")], default=str)
    assert token not in raw, "the plaintext token must never be persisted"
    assert storage._hash_token(token) in raw


def test_production_without_smtp_refuses_instead_of_pretending(client, monkeypatch):
    _, email = _register(client, "verify-nosmtp")
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "smtp_host", "")
    response = client.post("/api/auth/verify/request", json={"email": email})
    assert response.status_code == 503
    assert "SPACEAGRISIM_SMTP_HOST" in response.json()["detail"]
    assert mailer.delivery_mode() == "unconfigured"


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------

def test_reset_changes_the_password_and_retires_the_old_one(client):
    headers, email = _register(client, "reset-main")
    client.post("/api/auth/password/forgot", json={"email": email})
    token = _token_for(email, "Reset")

    changed = client.post("/api/auth/password/reset",
                          json={"token": token, "password": NEW_PASSWORD})
    assert changed.status_code == 200

    assert client.post("/api/auth/login", json={"email": email, "password": PASSWORD}).status_code == 401
    assert client.post("/api/auth/login", json={"email": email, "password": NEW_PASSWORD}).status_code == 200
    # the reset link cannot be replayed
    assert client.post("/api/auth/password/reset",
                       json={"token": token, "password": "ThirdPassphrase77!"}).status_code == 400


def test_reset_invalidates_sessions_issued_before_it(client):
    headers, email = _register(client, "reset-sessions")
    assert client.get("/api/auth/me", headers=headers).status_code == 200

    client.post("/api/auth/password/forgot", json={"email": email})
    token = _token_for(email, "Reset")
    client.post("/api/auth/password/reset", json={"token": token, "password": NEW_PASSWORD})

    stale = client.get("/api/auth/me", headers=headers)
    assert stale.status_code == 401
    assert "password change" in stale.json()["detail"].lower()


def test_forgot_password_does_not_reveal_registration(client):
    response = client.post("/api/auth/password/forgot", json={"email": "ghost-account@example.test"})
    assert response.status_code == 202
    assert mailer.last_message_for("ghost-account@example.test") is None


def test_expired_reset_token_is_rejected(client, monkeypatch):
    _, email = _register(client, "reset-expiry")
    monkeypatch.setattr(settings, "password_reset_minutes", 0)
    client.post("/api/auth/password/forgot", json={"email": email})
    token = _token_for(email, "Reset")
    response = client.post("/api/auth/password/reset",
                           json={"token": token, "password": NEW_PASSWORD})
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Security activity
# ---------------------------------------------------------------------------

def test_activity_log_records_the_accounts_own_events(client):
    headers, email = _register(client, "activity")
    client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    client.post("/api/auth/login", json={"email": email, "password": "wrong-password-here"})
    client.post("/api/auth/verify/request", json={"email": email})

    events = client.get("/api/auth/activity", headers=headers)
    assert events.status_code == 200
    kinds = [event["kind"] for event in events.json()["events"]]
    for expected in ("account-created", "login", "login-failed", "verification-requested"):
        assert expected in kinds
    assert events.json()["events"][0]["createdAt"] >= events.json()["events"][-1]["createdAt"]


def test_activity_requires_authentication(client):
    assert client.get("/api/auth/activity").status_code == 401


def test_activity_history_is_trimmed_to_the_configured_cap(client, monkeypatch):
    headers, email = _register(client, "activity-cap")
    user = storage.find_user_by_email(email)
    monkeypatch.setattr(settings, "max_activity_events", 5)
    for _ in range(20):
        storage.record_activity(user["id"], "login")
    assert len(storage.list_activity(user["id"], limit=200)) == 5


def test_activity_records_carry_no_address_or_free_text(client):
    _, email = _register(client, "activity-shape")
    user = storage.find_user_by_email(email)
    for event in storage.list_activity(user["id"], limit=200):
        assert set(event) == {"kind", "detail", "created_at"}
        assert "@" not in str(event["detail"])


# ---------------------------------------------------------------------------
# Share links
# ---------------------------------------------------------------------------

CONFIGURATION = {"crop": "lettuce", "gravity": 1.0, "radiation": 0.01, "lightHours": 12,
                 "co2Level": 420, "humidity": 60, "waterAvailability": 100,
                 "simulationDays": 30}


def _saved_scenario(client: TestClient, headers: dict, name: str = "Shared run") -> str:
    response = client.post("/api/scenarios", headers=headers,
                           json={"name": name, "configuration": CONFIGURATION})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_share_link_is_readable_without_authentication_and_reproduces_the_run(client):
    headers, _ = _register(client, "share-basic")
    scenario_id = _saved_scenario(client, headers)

    created = client.post(f"/api/scenarios/{scenario_id}/share", headers=headers)
    assert created.status_code == 201, created.text
    token = created.json()["token"]

    shared = client.get(f"/api/shared/{token}")
    assert shared.status_code == 200
    body = shared.json()
    # stored as the fully-defaulted model, so compare the submitted keys rather than the whole dict
    assert {key: body["configuration"][key] for key in CONFIGURATION} == CONFIGURATION
    assert body["name"] == "Shared run"
    assert body["result"]["cropYield"] == pytest.approx(
        client.post("/api/simulate", json=CONFIGURATION).json()["cropYield"])
    assert "not" in body["disclaimer"].lower()


def test_shared_payload_contains_no_owner_data(client):
    headers, email = _register(client, "share-privacy")
    scenario_id = _saved_scenario(client, headers)
    token = client.post(f"/api/scenarios/{scenario_id}/share", headers=headers).json()["token"]
    body = client.get(f"/api/shared/{token}").text
    assert email not in body
    assert "owner" not in body.lower()


def test_share_links_are_capped_per_scenario(client):
    headers, _ = _register(client, "share-cap")
    scenario_id = _saved_scenario(client, headers)
    for _ in range(settings.max_share_links_per_scenario):
        assert client.post(f"/api/scenarios/{scenario_id}/share", headers=headers).status_code == 201
    blocked = client.post(f"/api/scenarios/{scenario_id}/share", headers=headers)
    assert blocked.status_code == 409
    assert "revoke" in blocked.json()["detail"].lower()


def test_share_links_can_be_revoked(client):
    headers, _ = _register(client, "share-revoke")
    scenario_id = _saved_scenario(client, headers)
    token = client.post(f"/api/scenarios/{scenario_id}/share", headers=headers).json()["token"]
    assert client.get(f"/api/shared/{token}").status_code == 200
    assert client.delete(f"/api/scenarios/{scenario_id}/share", headers=headers).json()["revoked"] >= 1
    assert client.get(f"/api/shared/{token}").status_code == 404
    # after revocation the cap is free again
    assert client.post(f"/api/scenarios/{scenario_id}/share", headers=headers).status_code == 201


def test_expired_share_link_is_rejected(client, monkeypatch):
    headers, _ = _register(client, "share-expiry")
    scenario_id = _saved_scenario(client, headers)
    # A negative lifetime puts the expiry in the past, which is what a link created long enough
    # ago looks like to the resolver.
    monkeypatch.setattr(settings, "share_link_days", -1)
    token = client.post(f"/api/scenarios/{scenario_id}/share", headers=headers).json()["token"]
    assert client.get(f"/api/shared/{token}").status_code == 404


def test_cannot_share_another_accounts_scenario(client):
    owner_headers, _ = _register(client, "share-owner")
    other_headers, _ = _register(client, "share-other")
    scenario_id = _saved_scenario(client, owner_headers)

    response = client.post(f"/api/scenarios/{scenario_id}/share", headers=other_headers)
    assert response.status_code == 404
    assert client.post(f"/api/scenarios/{scenario_id}/share").status_code == 401


def test_unknown_share_token_is_a_plain_404(client):
    assert client.get(f"/api/shared/{uuid.uuid4().hex}").status_code == 404
    assert client.get("/api/shared/short").status_code == 404


# ---------------------------------------------------------------------------
# Readiness payload
# ---------------------------------------------------------------------------

def test_readiness_surfaces_storage_and_email_state(client):
    ready = client.get("/api/ready")
    assert ready.status_code == 200
    body = ready.json()
    assert body["storage"]["durable"] in (True, False)
    assert "remedy" in body["storage"]
    assert body["emailDelivery"] in ("smtp", "outbox", "unconfigured")
    assert body["shareLinks"] is True
    assert body["rateLimitIdentity"] in ("socket", "forwarded")


def test_sqlite_under_tmp_is_reported_as_non_durable(monkeypatch):
    monkeypatch.setattr(settings, "database_url", "sqlite:////tmp/spaceagrisim-ephemeral.db")
    report = storage.storage_durability()
    assert report["durable"] is False
    assert "SPACEAGRISIM_DATABASE_URL" in report["remedy"]


def _all(table_name: str):
    table = getattr(storage, table_name)
    with storage.database().connect() as connection:
        return connection.execute(table.select()).all()
