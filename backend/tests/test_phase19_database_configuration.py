"""Hosted database configuration: alias handling and honest, secret-free failure reporting.

The live deployment failed every account, history and share-link route while /health stayed 200.
Two separate gaps made that hard to read: a platform URL form was rejected outright, and the
rejection surfaced as an opaque 500 on one route and a bare "Database unavailable" on another.
"""

import pytest
from fastapi.testclient import TestClient

from app.config.settings import resolve_database_url, settings
from app.storage import DatabaseConfigurationError


DEFAULT = "sqlite:///.spaceagrisim/scenarios.db"


@pytest.fixture(autouse=True)
def _fresh_engine():
    """`storage.database()` is memoised, so a test that changes the URL must drop the cached engine.

    Without this the suite passes in isolation and fails after any test that opened the real
    database first, which is exactly the kind of ordering bug that hides for months.
    """
    from app import storage

    storage.database.cache_clear()
    yield
    storage.database.cache_clear()


@pytest.mark.parametrize(
    "raw",
    ["postgres://user:secret@db.example.com:5432/app",
     "postgresql://user:secret@db.example.com:5432/app"],
)
def test_platform_postgres_aliases_map_to_the_psycopg_driver(raw):
    resolved = resolve_database_url(raw, DEFAULT)
    assert resolved.startswith("postgresql+psycopg://")
    # the credentials survive untouched; only the driver is named
    assert "user:secret@db.example.com:5432/app" in resolved


@pytest.mark.parametrize("raw", ["", "   ", None])
def test_blank_url_falls_back_instead_of_disabling_every_route(raw):
    assert resolve_database_url(raw, DEFAULT) == DEFAULT


def test_unrecognised_scheme_is_left_for_the_storage_layer_to_reject():
    # not silently rewritten: an operator typo should fail loudly, with a reason
    assert resolve_database_url("mysql://host/db", DEFAULT) == "mysql://host/db"


def test_unsupported_scheme_raises_a_typed_error_with_a_reason(monkeypatch):
    from app import storage

    monkeypatch.setattr(storage.settings, "database_url", "mysql://host/db", raising=False)
    with pytest.raises(DatabaseConfigurationError) as excinfo:
        storage.database()
    assert excinfo.value.reason == "scheme-unsupported"
    assert "mysql" in excinfo.value.detail


def test_readiness_names_the_reason_and_never_leaks_the_url(client, monkeypatch):
    from app import storage

    monkeypatch.setattr(
        storage.settings, "database_url", "mysql://user:hunter2@db.internal/app", raising=False
    )
    response = client.get("/api/ready")
    assert response.status_code == 503
    body = response.json()
    detail = body["detail"]
    assert detail["reason"] == "scheme-unsupported"
    assert "SPACEAGRISIM_DATABASE_URL" in detail["remedy"]
    # neither the password nor the host may appear in the response
    assert "hunter2" not in response.text
    assert "db.internal" not in response.text


def test_account_route_reports_503_not_an_opaque_500(client, monkeypatch):
    from app import storage

    monkeypatch.setattr(storage.settings, "database_url", "mysql://host/db", raising=False)
    response = client.post(
        "/api/auth/login", json={"email": "someone@example.com", "password": "nottherightone"}
    )
    assert response.status_code == 503
    assert response.json()["error"] == "database_misconfigured"
    assert response.json()["reason"] == "scheme-unsupported"


def test_resolved_url_is_what_the_storage_layer_opens(monkeypatch):
    from app import storage

    monkeypatch.setattr(storage.settings, "database_url", "  ", raising=False)
    assert storage.settings.database_url_resolved == storage.settings.database_url_default


class _FakeOperationalError(Exception):
    """Stands in for psycopg's OperationalError, which carries a SQLSTATE."""

    def __init__(self, sqlstate):
        super().__init__("connection to server at db.internal (10.0.0.5) failed")
        self.sqlstate = sqlstate


@pytest.mark.parametrize("sqlstate", ["28P01", "3D000", "08006"])
def test_readiness_reports_sqlstate_but_not_the_driver_message(client, monkeypatch, sqlstate):
    from app import storage

    def boom():
        raise _FakeOperationalError(sqlstate)

    monkeypatch.setattr(storage, "database_health", boom)
    response = client.get("/api/ready")
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["reason"] == "connection-failed"
    assert detail["sqlstate"] == sqlstate
    assert detail["exceptionType"] == "_FakeOperationalError"
    # the driver's own message names the host and must not be forwarded
    assert "db.internal" not in response.text
    assert "10.0.0.5" not in response.text


def test_missing_sqlstate_is_read_as_never_reaching_the_server(client, monkeypatch):
    from app import storage

    def boom():
        raise _FakeOperationalError(None)

    monkeypatch.setattr(storage, "database_health", boom)
    detail = client.get("/api/ready").json()["detail"]
    assert "sqlstate" not in detail
    assert "never reached a database server" in detail["remedy"]


def test_driver_diagnosis_survives_a_wrapped_error():
    from app import storage

    class Wrapper(Exception):
        def __init__(self):
            super().__init__("wrapped")
            self.orig = _FakeOperationalError("28P01")

    assert storage._driver_diagnosis(Wrapper()) == {
        "exceptionType": "Wrapper",
        "sqlstate": "28P01",
    }
