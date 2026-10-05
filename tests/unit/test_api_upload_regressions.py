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
