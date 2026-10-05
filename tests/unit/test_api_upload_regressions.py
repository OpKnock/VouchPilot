from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook

from vouch_engine.api import create_app


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


def test_vouchpilot_fraud_setting_is_forwarded(monkeypatch):
    from vouch_engine import api

    seen = {}

    class FakeScorer:
        def predict(self, row, tags, mask, exemplars=None):
            return "Purchase", 0.91, [["Purchase", 0.91], ["Sales", 0.09]]

    def fake_make_scorer(name, endpoint, fraud=True):
        seen["name"] = name
        seen["endpoint"] = endpoint
        seen["fraud"] = fraud
        return FakeScorer()

    monkeypatch.setattr(api, "_make_scorer", fake_make_scorer)
    predictions, invalid = api.classify_raw_rows(
        [{"Invoice No": "PI-003", "Narration": "Steel rods"}],
        "vouchpilot",
        "http://127.0.0.1:8080",
        1,
        fraud=False,
    )

    assert invalid == 0
    assert len(predictions) == 1
    assert seen == {
        "name": "vouchpilot",
        "endpoint": "http://127.0.0.1:8080",
        "fraud": False,
    }
