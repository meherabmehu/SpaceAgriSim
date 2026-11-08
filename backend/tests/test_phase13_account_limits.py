"""Phase 13: persistent auth-secret handling and per-account saved-analysis limits.

Two failure modes are covered here, and both are quiet in production if they are wrong:

* the secret. A per-process random fallback means a second worker rejects the first worker's
  tokens, and every restart logs the whole estate out. That is survivable in development and
  unacceptable in a deployment, so production refuses to start without a real secret.
* the quotas. A count-then-insert implemented outside a transaction lets two concurrent saves
  both pass the same check, which is exactly how a per-account limit stops being a limit.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from threading import Thread

import jwt
import pytest
from fastapi.testclient import TestClient

from app import storage
from app.auth import hash_password
from app.config.settings import Settings, settings
from app.main import app

PASSWORD = "CorrectHorseBattery1!"
GOOD_SECRET = "Zx9" + "q7Lm2Pv8Rt4Wn6Bc1Fg5Hj3Kd0SaYuEoI"  # 40 chars, high entropy


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def _account(client: TestClient, label: str = "acct") -> tuple[dict, str]:
    email = f"limits-{label}-{uuid.uuid4().hex[:10]}@example.test"
    response = client.post("/api/auth/register", json={"email": email, "password": PASSWORD})
    assert response.status_code in (200, 201), response.text
    body = response.json()
    return {"Authorization": f"Bearer {body['accessToken']}"}, email


# ---------------------------------------------------------------------------
# The secret
# ---------------------------------------------------------------------------

def test_production_requires_an_explicit_secret():
    with pytest.raises(ValueError) as caught:
        Settings(environment="production")
    assert "SPACEAGRISIM_AUTH_SECRET" in str(caught.value)


def test_production_accepts_a_strong_secret():
    configured = Settings(environment="production", auth_secret=GOOD_SECRET)
    assert configured.auth_secret_is_persistent
    assert configured.resolved_auth_secret == GOOD_SECRET


@pytest.mark.parametrize("secret", ["short", "x" * 40, "changeme" * 6])
def test_weak_or_placeholder_secrets_are_rejected(secret):
    with pytest.raises(ValueError):
        Settings(environment="production", auth_secret=secret)


def test_previous_secret_must_differ():
    with pytest.raises(ValueError):
        Settings(environment="production", auth_secret=GOOD_SECRET, auth_secret_previous=GOOD_SECRET)


def test_development_falls_back_to_one_ephemeral_secret_per_process():
    first = Settings(environment="development")
    second = Settings(environment="development")
    assert not first.auth_secret_is_persistent
    # Same process, same fallback: a worker does not invalidate its own tokens between Settings
    # instances. Different processes get different values, which is why production forbids it.
    assert first.resolved_auth_secret == second.resolved_auth_secret


def test_the_environment_secret_is_shared_across_restarts(monkeypatch):
    monkeypatch.setenv("SPACEAGRISIM_ENVIRONMENT", "production")
    monkeypatch.setenv("SPACEAGRISIM_AUTH_SECRET", GOOD_SECRET)
    restarted_once = Settings()
    restarted_twice = Settings()
    assert restarted_once.auth_secret_is_persistent
    assert restarted_once.resolved_auth_secret == restarted_twice.resolved_auth_secret == GOOD_SECRET


def test_tokens_survive_a_restart_when_the_secret_is_configured(monkeypatch, client: TestClient):
    """The concrete consequence: a token issued before a restart still authenticates after it."""
    monkeypatch.setattr(settings, "auth_secret", GOOD_SECRET, raising=False)
    headers, _ = _account(client, "restart")
    before = client.get("/api/auth/me", headers=headers)
    assert before.status_code == 200
    # Simulate the restart by rebuilding the settings the way a new process would.
    restarted = Settings(environment="production", auth_secret=GOOD_SECRET)
    token = headers["Authorization"].split(" ", 1)[1]
    claims = jwt.decode(token, restarted.resolved_auth_secret, algorithms=["HS256"])
    assert claims["sub"] == before.json()["user"]["id"]


def test_a_token_signed_with_another_secret_is_rejected(monkeypatch, client: TestClient):
    monkeypatch.setattr(settings, "auth_secret", GOOD_SECRET, raising=False)
    headers, _ = _account(client, "foreign")
    token = headers["Authorization"].split(" ", 1)[1]
    claims = jwt.decode(token, GOOD_SECRET, algorithms=["HS256"])
    foreign = jwt.encode(claims, "B" * 40, algorithm="HS256")
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {foreign}"})
    assert response.status_code == 401


def test_rotation_window_accepts_the_previous_secret(monkeypatch, client: TestClient):
    previous = "Previous" + "Ab3Cd5Ef7Gh9Ij1Kl3Mn5Op7Qr9St"
    monkeypatch.setattr(settings, "auth_secret", GOOD_SECRET, raising=False)
    monkeypatch.setattr(settings, "auth_secret_previous", previous, raising=False)
    headers, _ = _account(client, "rotate")
    token = headers["Authorization"].split(" ", 1)[1]
    claims = jwt.decode(token, GOOD_SECRET, algorithms=["HS256"])
    old_token = jwt.encode(claims, previous, algorithm="HS256")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_token}"}).status_code == 200
    # Outside the rotation window the same token is refused.
    monkeypatch.setattr(settings, "auth_secret_previous", None, raising=False)
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_token}"}).status_code == 401


def test_expired_token_is_refused_with_an_expiry_message(monkeypatch, client: TestClient):
    monkeypatch.setattr(settings, "auth_secret", GOOD_SECRET, raising=False)
    headers, email = _account(client, "expiry")
    claims = jwt.decode(headers["Authorization"].split(" ", 1)[1], GOOD_SECRET, algorithms=["HS256"])
    expired = jwt.encode({**claims, "exp": datetime.now(timezone.utc) - timedelta(minutes=5)},
                         GOOD_SECRET, algorithm="HS256")
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


def test_secret_is_absent_from_health_and_docs(client: TestClient):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert GOOD_SECRET not in health.text
    schema = client.get("/api/openapi.json").text
    assert GOOD_SECRET not in schema
    assert "auth_secret" not in schema.lower()


# ---------------------------------------------------------------------------
# Saved-analysis quotas
# ---------------------------------------------------------------------------

def _save(client: TestClient, headers: dict, title: str = "analysis"):
    return client.post("/api/workflow/run-and-save",
                       json={"modelId": "lettuce-earth-growth-v1", "title": title,
                             "inputs": {"daysAfterTransplant": 20, "airTemperature": 24,
                                        "rootTemperature": 22, "ppfd": 400}},
                       headers=headers)


def test_count_quota_is_enforced_inside_the_transaction(monkeypatch, client: TestClient):
    monkeypatch.setattr(settings, "max_analyses_per_user", 1, raising=False)
    headers, _ = _account(client, "quota")
    assert _save(client, headers, "first").status_code == 200
    second = _save(client, headers, "second")
    assert second.status_code == 409
    assert second.json()["detail"]["error"] == "quota-count"
    listed = client.get("/api/analyses", headers=headers).json()
    assert listed["pagination"]["total"] == 1


def test_byte_quota_is_enforced(monkeypatch, client: TestClient):
    monkeypatch.setattr(settings, "max_analysis_bytes_per_user", 1024, raising=False)
    headers, _ = _account(client, "bytes")
    response = _save(client, headers)
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "quota-bytes"


def test_single_payload_ceiling_is_separate_from_the_account_quota(monkeypatch, client: TestClient):
    monkeypatch.setattr(settings, "max_analysis_bytes", 10, raising=False)
    headers, _ = _account(client, "payload")
    response = _save(client, headers)
    assert response.status_code == 413


def test_concurrent_saves_never_exceed_the_limit(monkeypatch, client: TestClient):
    monkeypatch.setattr(settings, "max_analyses_per_user", 3, raising=False)
    headers, _ = _account(client, "concurrent")

    results: list[int] = []

    def worker():
        results.append(_save(client, headers).status_code)

    threads = [Thread(target=worker) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    stored = client.get("/api/analyses", headers=headers).json()["pagination"]["total"]
    assert stored <= 3
    assert results.count(200) == stored
    assert set(results) <= {200, 409}


def test_quota_usage_is_reported(monkeypatch, client: TestClient):
    monkeypatch.setattr(settings, "max_analyses_per_user", 5, raising=False)
    headers, _ = _account(client, "usage")
    _save(client, headers)
    usage = client.get("/api/analyses", headers=headers).json()["usage"]
    assert usage["count"] >= 1 and usage["maxCount"] == 5
    assert set(usage) == {"count", "bytes", "maxCount", "maxBytes"}


def test_pagination_walks_the_whole_set_without_overlap(monkeypatch, client: TestClient):
    headers, _ = _account(client, "pages")
    for index in range(5):
        assert _save(client, headers, f"page-{index}").status_code == 200
    first = client.get("/api/analyses?limit=2&offset=0", headers=headers).json()
    second = client.get("/api/analyses?limit=2&offset=2", headers=headers).json()
    assert first["pagination"] == {"limit": 2, "offset": 0, "total": 5, "hasMore": True}
    assert second["pagination"]["hasMore"] is True
    ids_first = {row["id"] for row in first["analyses"]}
    ids_second = {row["id"] for row in second["analyses"]}
    assert not ids_first & ids_second
    assert len(ids_first | ids_second) == 4


def test_page_size_is_capped_by_the_server(monkeypatch, client: TestClient):
    monkeypatch.setattr(settings, "max_analyses_page_size", 3, raising=False)
    headers, _ = _account(client, "cap")
    for index in range(4):
        _save(client, headers, f"cap-{index}")
    page = client.get("/api/analyses?limit=500", headers=headers).json()
    assert page["pagination"]["limit"] == 3
    assert len(page["analyses"]) == 3


def test_retention_sweep_is_off_by_default_and_removes_old_rows_when_enabled(monkeypatch, client: TestClient):
    headers, email = _account(client, "retention")
    _save(client, headers, "old")
    assert client.get("/api/analyses", headers=headers).json()["pagination"]["total"] == 1

    assert storage.purge_expired_analyses() == 0  # retention disabled

    monkeypatch.setattr(settings, "analysis_retention_days", 30, raising=False)
    assert storage.purge_expired_analyses() == 0  # nothing is old yet
    later = datetime.now(timezone.utc) + timedelta(days=31)
    # The sweep is account-agnostic by design: retention is an operator policy, not a per-user
    # preference. The test therefore asserts this account is emptied, not that exactly one row
    # vanished from a database other tests also write to.
    removed = storage.purge_expired_analyses(now=later)
    assert removed >= 1
    assert client.get("/api/analyses", headers=headers).json()["pagination"]["total"] == 0


def test_account_deletion_is_scoped_to_the_caller(client: TestClient):
    owner_headers, _ = _account(client, "owner")
    other_headers, _ = _account(client, "other")
    _save(client, owner_headers, "mine")
    _save(client, other_headers, "theirs")
    removed = client.delete("/api/analyses", headers=owner_headers)
    assert removed.status_code == 200 and removed.json()["deleted"] == 1
    assert client.get("/api/analyses", headers=owner_headers).json()["pagination"]["total"] == 0
    assert client.get("/api/analyses", headers=other_headers).json()["pagination"]["total"] == 1


def test_quotas_and_pagination_require_authentication(client: TestClient):
    assert client.get("/api/analyses").status_code == 401
    assert client.delete("/api/analyses").status_code == 401


def test_existing_analyses_survive_schema_initialisation(client: TestClient):
    """Creating the schema again - what a restart or a migration run does - must not drop rows."""
    headers, _ = _account(client, "migrate")
    _save(client, headers, "survivor")
    engine = storage.database()
    before = storage.list_analyses(headers and storage.find_user_by_email(
        jwt.decode(headers["Authorization"].split(" ", 1)[1],
                   settings.resolved_auth_secret, algorithms=["HS256"])["email"])["id"])[1]
    storage.metadata.create_all(engine)
    after = storage.list_analyses(storage.find_user_by_email(
        jwt.decode(headers["Authorization"].split(" ", 1)[1],
                   settings.resolved_auth_secret, algorithms=["HS256"])["email"])["id"])[1]
    assert before == after == 1
