"""New web-wiring endpoints: labels, settings, system, launcher."""

import os

from fastapi.testclient import TestClient

from vouch_engine.api import create_app


def test_labels_lists_27():
    body = TestClient(create_app()).get("/labels").json()
    assert len(body["labels"]) == 27
    assert body["labels"][0]["name"] == "Purchase"


def test_settings_roundtrip_and_validation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    assert client.get("/settings").json()["scorer"] == "keyword"
    saved = client.post("/settings", json={"scorer": "server", "workers": 4,
                                           "theme": "dark"}).json()
    assert saved["scorer"] == "server" and saved["workers"] == 4
    assert saved["theme"] == "dark"
    assert os.path.exists(tmp_path / "settings.json")
    bad = client.post("/settings", json={"scorer": "nope"})
    assert bad.status_code == 422
    capped = client.post("/settings", json={"workers": 99, "auto_approve_threshold": 5}).json()
    assert capped["workers"] == 8 and capped["auto_approve_threshold"] == 60


def test_system_shape():
    body = TestClient(create_app()).get("/system").json()
    assert body["modules"]["ingest"] == "OK"
    assert "weights" in body and "server" in body


def test_launcher_serves_bat_or_404():
    resp = TestClient(create_app()).get("/launcher")
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        assert "start-vouchpilot" in resp.text.lower() or len(resp.content) > 100


def test_desktop_package_zip_or_404(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    resp = TestClient(create_app()).get("/desktop-package")
    assert resp.status_code == 404
    assert "exe" in resp.json()["detail"].lower()
