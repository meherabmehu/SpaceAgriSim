"""Phase 19: the request budget has to follow the client, not the gateway.

Behind a managed gateway every request arrives from the proxy's address. Counting those together
turns a per-user budget into a global one — one caller can exhaust it for everybody, and an
attacker gets a fresh allowance for every request if the service instead trusts whatever
X-Forwarded-For it is handed. Both directions are asserted here.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config.settings import settings
from app.middleware import RequestGuard


def _app(limit: int = 2) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestGuard, max_per_minute=limit, optimize_per_minute=limit)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    return app


def _call(client: TestClient, forwarded: str | None = None):
    headers = {"X-Forwarded-For": forwarded} if forwarded else {}
    return client.get("/ping", headers=headers).status_code


def test_forwarded_header_is_ignored_when_no_proxy_is_configured(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_hops", 0)
    client = TestClient(_app(limit=2))
    # A caller rotating the header must not be handed a fresh budget each time.
    assert _call(client, "203.0.113.1") == 200
    assert _call(client, "203.0.113.2") == 200
    assert _call(client, "203.0.113.3") == 429


def test_one_trusted_hop_separates_clients_behind_a_gateway(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)
    client = TestClient(_app(limit=2))
    assert _call(client, "198.51.100.7") == 200
    assert _call(client, "198.51.100.7") == 200
    assert _call(client, "198.51.100.7") == 429
    # a different client arriving through the same gateway still has its own budget
    assert _call(client, "198.51.100.8") == 200


def test_only_the_trusted_hop_from_the_right_is_used(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)
    client = TestClient(_app(limit=1))
    # The left-most entry is caller-controlled; the gateway appends the real peer on the right.
    assert _call(client, "1.2.3.4, 198.51.100.9") == 200
    assert _call(client, "9.9.9.9, 198.51.100.9") == 429


def test_missing_or_short_forwarding_chain_falls_back_to_the_peer(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_hops", 2)
    client = TestClient(_app(limit=1))
    assert _call(client) == 200
    assert _call(client, "198.51.100.10") == 429  # one entry cannot satisfy two hops


def test_rate_limited_response_states_when_to_retry():
    client = TestClient(_app(limit=1))
    client.get("/ping")
    blocked = client.get("/ping")
    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"] == "60"
    assert blocked.json()["error"] == "rate_limit"


def test_shipped_defaults_are_unchanged_and_local_only():
    from app.config.settings import Settings

    shipped = Settings()
    assert shipped.auth_rate_limit_per_minute == 30
    assert shipped.general_rate_limit_per_minute == 180
    # Trusting forwarded headers by default would let a direct client forge its own address.
    assert shipped.trusted_proxy_hops == 0
    with pytest.raises(ValueError):
        Settings(trusted_proxy_hops=6)
