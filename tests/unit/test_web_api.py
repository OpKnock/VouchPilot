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


def test_predict_handles_decorative_rows_and_semicolon_csv():
    client = TestClient(create_app())
    body = (
        "FY 2026-27;;\n"
        "Invoice No;Narration;Total\n"
        "PI-200;Office chairs purchase;59000\n"
    ).encode("utf-8")
    response = client.post(
        "/predict?scorer=keyword",
        files={"file": ("messy.csv", body, "text/csv")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["n_rows"] == 1
    assert payload["predictions"][0]["invoice_number"] == "PI-200"

def test_settings_recovers_from_stale_persisted_scorer(tmp_path, monkeypatch):
    (tmp_path / "settings.json").write_text(
        '{"scorer": "removed-model", "workers": 2}',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    response = client.get("/settings")
    assert response.status_code == 200
    assert response.json()["scorer"] == "keyword"
    bad = client.post("/settings", json={"scorer": "still-invalid"})
    assert bad.status_code == 422

def test_predict_reader_failure_is_a_server_error(monkeypatch):
    from vouch_engine import api

    def broken_input(_path, _suffix):
        raise RuntimeError("reader exploded")

    monkeypatch.setattr(api, "_read_input", broken_input)
    response = TestClient(create_app()).post(
        "/predict?scorer=keyword",
        files={"file": ("transactions.xlsx", b"fake", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 500
    assert "pipeline failed" in response.json()["detail"]
    
def test_audit_endpoint_returns_disagreement_report():
    client = TestClient(create_app())
    response = client.post(
        "/audit",
        json={
            "records": [
                {"row_id": 1, "invoice_number": "PI-1", "voucher_type": "Purchase"},
                {"row_id": 2, "invoice_number": "SI-1", "voucher_type": "Sales"},
            ],
            "predictions": [
                {"row_id": 1, "voucher_type": "Purchase", "confidence": 0.9},
                {"row_id": 2, "voucher_type": "Payment", "confidence": 0.7},
            ],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["n_rows"] == 2
    assert body["agreement"] == 0.5
    assert body["disagreements"][0]["row_id"] == 2


def test_predict_caps_worker_count(monkeypatch):
    from vouch_engine import api

    seen = {}

    class TinyExecutor:
        def __init__(self, max_workers):
            seen["max_workers"] = max_workers
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def map(self, fn, values):
            return [fn(value) for value in values]

    monkeypatch.setattr(api.concurrent.futures, "ThreadPoolExecutor", TinyExecutor)
    api.classify_raw_rows([{"Invoice No": "PI-1", "Narration": "purchase"}],
                          "keyword", "http://127.0.0.1:8080", 100_000)
    assert seen["max_workers"] == 8


def test_remote_llm_endpoint_is_rejected():
    response = TestClient(create_app()).post(
        "/predict?scorer=server&endpoint=http://169.254.169.254/latest/meta-data",
        files={"file": ("transactions.csv", b"Invoice No,Narration\nPI-1,purchase\n", "text/csv")},
    )
    assert response.status_code == 422
    assert "endpoint" in response.json()["detail"].lower()


def test_predict_n_rows_counts_input_rows_even_when_one_prediction_is_invalid(monkeypatch):
    from vouch_engine import api

    real_validate = api.validate.validate_prediction
    calls = {"n": 0}

    def invalid_second(record):
        calls["n"] += 1
        if calls["n"] == 2:
            raise ValueError("synthetic invalid row")
        return real_validate(record)

    monkeypatch.setattr(api.validate, "validate_prediction", invalid_second)
    response = TestClient(create_app()).post(
        "/predict?scorer=keyword",
        files={
            "file": (
                "transactions.csv",
                b"Invoice No,Narration\nPI-1,purchase\nPI-2,sales\n",
                "text/csv",
            )
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["n_rows"] == 2
    assert body["invalid"] == 1
    assert len(body["predictions"]) == 1




def test_predict_reports_model_server_unavailable(monkeypatch):
    from vouch_engine import api
    from vouch_engine.scorer import ScorerUnavailableError

    def unavailable(*_args, **_kwargs):
        raise ScorerUnavailableError("local model server unavailable at http://127.0.0.1:8080")

    monkeypatch.setattr(api, "classify_raw_rows", unavailable)
    response = TestClient(create_app()).post(
        "/predict?scorer=server",
        files={"file": ("transactions.csv", b"Invoice No,Narration\nPI-1,purchase\n", "text/csv")},
    )
    assert response.status_code == 503
    assert "local model server unavailable" in response.json()["detail"]


def test_audit_endpoint_tolerates_malformed_confidence():
    client = TestClient(create_app())
    response = client.post(
        "/audit",
        json={
            "records": [{"row_id": 1, "invoice_number": "PI-1", "voucher_type": "Purchase"}],
            "predictions": [{"row_id": 1, "voucher_type": "Sales", "confidence": "not-a-number"}],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["disagreements"][0]["confidence"] == 0.0
