"""Web/API regression coverage for upload routing and workspace settings."""

import os
from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook

from vouch_engine.api import create_app


def test_labels_lists_27():
    body = TestClient(create_app()).get("/labels").json()
    assert len(body["labels"]) == 27
    assert body["labels"][0]["name"] == "Purchase"


def test_settings_roundtrip_and_validation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    assert client.get("/settings").json()["scorer"] == "keyword"

    saved = client.post(
        "/settings",
        json={"scorer": "server", "workers": 4, "theme": "dark", "export_format": "csv"},
    ).json()
    assert saved["scorer"] == "server" and saved["workers"] == 4
    assert saved["theme"] == "dark"
    assert saved["export_format"] == "csv"
    assert os.path.exists(tmp_path / "settings.json")

    bad = client.post("/settings", json={"scorer": "nope"})
    assert bad.status_code == 422

    capped = client.post(
        "/settings", json={"workers": 99, "auto_approve_threshold": 5}
    ).json()
    assert capped["workers"] == 8 and capped["auto_approve_threshold"] == 60


def test_predict_accepts_csv_upload():
    client = TestClient(create_app())
    body = b"Invoice No,Narration,Total\nPI-001,Steel rods purchase,1180\n"
    response = client.post(
        "/predict?scorer=keyword",
        files={"file": ("transactions.csv", body, "text/csv")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["n_rows"] == 1
    assert payload["predictions"][0]["row_id"] == 1


def test_predict_uses_best_sheet_for_messy_workbook():
    wb = Workbook()
    cover = wb.active
    cover.title = "Cover"
    cover["A1"] = "FY 2026-27 — VouchPilot export"

    tx = wb.create_sheet("Transactions")
    tx.append(["Invoice No", "Narration", "Total"])
    tx.append(["PI-002", "Computer purchase", 59000])

    stream = BytesIO()
    wb.save(stream)
    wb.close()

    client = TestClient(create_app())
    response = client.post(
        "/predict?scorer=keyword",
        files={
            "file": (
                "messy.xlsx",
                stream.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["n_rows"] == 1
    assert payload["predictions"][0]["invoice_number"] == "PI-002"


def test_unknown_upload_type_is_rejected():
    response = TestClient(create_app()).post(
        "/predict",
        files={"file": ("transactions.txt", b"Invoice No\nPI-001\n", "text/plain")},
    )
    assert response.status_code == 415


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


def test_predict_rejects_server_side_oversize_upload(monkeypatch):
    from vouch_engine import api

    monkeypatch.setattr(api, "MAX_UPLOAD_BYTES", 10)
    response = TestClient(create_app()).post(
        "/predict",
        files={"file": ("transactions.csv", b"Invoice No,Total\nPI-001,1180\n", "text/csv")},
    )
    assert response.status_code == 413
    assert "10 bytes" in response.json()["detail"]
