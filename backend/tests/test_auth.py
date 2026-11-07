from app import storage
from app.config.settings import settings


def register(client, email: str, password: str = "CorrectHorseBattery1!"):
    response = client.post("/api/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    return response.json()


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_registration_login_logout_and_password_protection(client, tmp_path, monkeypatch):
    storage.database.cache_clear()
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{(tmp_path/'auth.db').as_posix()}")
    try:
        account = register(client, "astronaut@example.test")
        assert "CorrectHorse" not in str(account)
        assert client.post("/api/auth/register", json={"email":"astronaut@example.test", "password":"CorrectHorseBattery1!"}).status_code == 409
        assert client.post("/api/auth/login", json={"email":"astronaut@example.test", "password":"not-the-password"}).status_code == 401
        login = client.post("/api/auth/login", json={"email":"astronaut@example.test", "password":"CorrectHorseBattery1!"})
        assert login.status_code == 200
        token = login.json()["accessToken"]
        assert client.get("/api/auth/me", headers=bearer(token)).json()["user"]["email"] == "astronaut@example.test"
        assert client.post("/api/auth/logout", headers=bearer(token)).status_code == 204
        assert client.get("/api/auth/me", headers=bearer(token)).status_code == 401
    finally:
        storage.database().dispose()
        storage.database.cache_clear()


def test_scenarios_are_private_to_the_authenticated_owner(client, tmp_path, monkeypatch):
    storage.database.cache_clear()
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{(tmp_path/'owners.db').as_posix()}")
    try:
        first = register(client, "first@example.test")["accessToken"]
        second = register(client, "second@example.test")["accessToken"]
        payload = {"name":"first mission", "configuration":{"crop":"lettuce"}}
        assert client.post("/api/scenarios", json=payload).status_code == 401
        created = client.post("/api/scenarios", json=payload, headers=bearer(first))
        assert created.status_code == 201
        assert client.get("/api/scenarios", headers=bearer(second)).json()["scenarios"] == []
        own = client.get("/api/scenarios", headers=bearer(first)).json()["scenarios"]
        assert len(own) == 1 and own[0]["owner_id"] != second
    finally:
        storage.database().dispose()
        storage.database.cache_clear()


def test_auth_validation_and_sensitive_endpoint_headers(client):
    response = client.post("/api/auth/login", json={"email":"bad", "password":"short"})
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
