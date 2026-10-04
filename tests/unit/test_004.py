"""Feature 004: API service, retro-audit, robustness, kappa."""

import io
import json

from fastapi.testclient import TestClient
from openpyxl import Workbook

from vouch_engine import audit as audit_mod
from vouch_engine import robust as robust_mod
from vouch_engine.api import create_app


def _raw_rows():
    return [
        {"Seller": "Sharma Traders", "Customer": "X",
         "Invoice No": "SI/1", "Taxable Value": 50000,
         "CGST": 4500, "SGST": 4500, "Narration": "sold chairs"},
        {"Supplier": "Y", "Buyer": "Sharma Traders",
         "Bill No": "PI/2", "Taxable Value": 10000,
         "CGST": 900, "SGST": 900, "Narration": "bought rods"},
    ]


def test_health():
    client = TestClient(create_app())
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["modules"]["ingest"] == "OK"


def test_predict_rows_keyword():
    client = TestClient(create_app())
    body = client.post("/predict-rows", json={"rows": _raw_rows(), "scorer": "keyword"}).json()
    assert body["n_rows"] == 2 and body["invalid"] == 0
    assert all("voucher_type" in p for p in body["predictions"])


def test_predict_xlsx_upload(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.append(["Seller", "Customer", "Invoice No", "Taxable Value"])
    ws.append(["Sharma Traders", "X", "SI/9", 1000])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    client = TestClient(create_app())
    resp = client.post("/predict", files={"file": ("t.xlsx", buf.read())},
                       params={"scorer": "keyword"})
    assert resp.status_code == 200
    assert resp.json()["n_rows"] == 1


def test_predict_bad_scorer_rejected():
    client = TestClient(create_app())
    resp = client.post("/predict-rows", json={"rows": _raw_rows(), "scorer": "nope"})
    assert resp.status_code == 422


def test_api_predict_deterministic():
    client = TestClient(create_app())
    first = client.post("/predict-rows", json={"rows": _raw_rows(), "scorer": "keyword"}).json()
    second = client.post("/predict-rows", json={"rows": _raw_rows(), "scorer": "keyword"}).json()
    assert first == second


def test_evaluate_endpoint():
    client = TestClient(create_app())
    gold = [{"row_id": 1, "voucher_type": "Sales"}, {"row_id": 2, "voucher_type": "Purchase"}]
    pred = [{"row_id": 1, "voucher_type": "Sales"}, {"row_id": 2, "voucher_type": "Sales"}]
    body = client.post("/evaluate", json={"gold": gold, "pred": pred}).json()
    assert body["accuracy"] == 0.5
    assert body["n_rows"] == 2


def test_audit_perfect_and_disagreement():
    records = [{"row_id": 1, "invoice_number": "A", "voucher_type": "Sales"},
               {"row_id": 2, "invoice_number": "B", "voucher_type": "Purchase"}]
    preds = [{"row_id": 1, "voucher_type": "Sales", "confidence": 0.9},
             {"row_id": 2, "voucher_type": "Sales", "confidence": 0.8}]
    rep = audit_mod.audit_recorded_vs_predicted(records, preds)
    assert rep["agreement"] == 0.5
    assert len(rep["disagreements"]) == 1
    assert rep["disagreements"][0]["row_id"] == 2
    by_label = {p["label"]: p for p in rep["per_label"]}
    assert by_label["Purchase"]["top_confusions"][0]["predicted"] == "Sales"


def test_kappa_known_values():
    assert audit_mod.cohen_kappa(["a", "a", "b", "b"], ["a", "a", "b", "b"])["kappa"] == 1.0
    out = audit_mod.cohen_kappa(["a", "a", "b", "b"], ["a", "a", "b", "a"])
    assert abs(out["kappa"] - 0.5) < 1e-9


def test_robust_rate_zero_is_identity(tmp_path):
    from vouch_engine import gold

    prefix = str(tmp_path / "r")
    gold.build_dataset(27, 4, prefix)
    labels = json.load(open(prefix + "_labels.json", encoding="utf-8"))
    rep = robust_mod.sweep(prefix + ".xlsx", labels, [0.0], [], "keyword", seed=7)
    rep2 = robust_mod.sweep(prefix + ".xlsx", labels, [0.0], [], "keyword", seed=7)
    assert rep["drop_curve"][0]["macro_f1"] == rep2["drop_curve"][0]["macro_f1"]
    assert "verdict_o4_drop_within_10pts" in rep and "verdict_o5_rename_within_5pts" in rep


def test_robust_drop_hurts_monotonically_or_reports(tmp_path):
    from vouch_engine import gold

    prefix = str(tmp_path / "m")
    gold.build_dataset(54, 6, prefix)
    labels = json.load(open(prefix + "_labels.json", encoding="utf-8"))
    rep = robust_mod.sweep(prefix + ".xlsx", labels, [0.0, 0.5], [0.0], "keyword", seed=7)
    f0 = rep["drop_curve"][0]["macro_f1"]
    f5 = rep["drop_curve"][1]["macro_f1"]
    assert f5 <= f0 + 1e-9
