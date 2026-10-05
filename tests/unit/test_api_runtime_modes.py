from fastapi.testclient import TestClient


def test_cors_is_opt_in(monkeypatch):
    monkeypatch.delenv("VOUCH_CORS_ORIGINS", raising=False)
    client = TestClient(__import__("vouch_engine.api", fromlist=["create_app"]).create_app())
    response = client.options(
        "/health",
        headers={
            "Origin": "https://app.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in response.headers


def test_cors_allows_configured_origin(monkeypatch):
    from vouch_engine.api import create_app

    monkeypatch.setenv("VOUCH_CORS_ORIGINS", "https://app.example.com")
    client = TestClient(create_app())
    response = client.options(
        "/health",
        headers={
            "Origin": "https://app.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers["access-control-allow-origin"] == "https://app.example.com"


def test_saas_settings_do_not_write_server_file(monkeypatch, tmp_path):
    from vouch_engine import api, settings

    monkeypatch.setenv("VOUCH_SAAS_MODE", "1")
    monkeypatch.chdir(tmp_path)
    client = TestClient(api.create_app())

    response = client.post("/settings", json={"theme": "dark", "workers": 8})
    assert response.status_code == 200
    assert response.json()["theme"] == "dark"
    assert response.json()["workers"] == 8
    assert not (tmp_path / settings.FILENAME).exists()
