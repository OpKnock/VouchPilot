"""Integration test for 002 grounding + reliability. No network."""

import json
import os
import subprocess
import sys

from openpyxl import Workbook

from vouch_engine.retriever import exemplars_from_gold

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "src")

LABELS_4 = ["Purchase", "Sales", "Payment", "Expense"]


def _run_cli(*cli_args):
    env = dict(os.environ)
    env["PYTHONPATH"] = SRC + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "vouch_engine", *cli_args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )


def _build_tiny_gold(xlsx_path, labels_path):
    headers = [
        "Supplier",
        "Customer",
        "Bill No",
        "Bill Date",
        "Item Desc",
        "Qty",
        "Rate",
        "Amount",
        "Taxable Value",
        "CGST",
        "SGST",
        "Grand Total",
        "Currency",
        "Payment Mode",
        "UTR / Cheque",
        "Debit Ledger",
        "Credit Ledger",
        "Narration",
    ]
    rows = []
    labels = []
    for i in range(12):
        label = LABELS_4[i % 4]
        inv = f"INV/{i + 1:04d}"
        if label == "Purchase":
            raw = {
                "Supplier": f"Vendor {i}",
                "Customer": "Sharma Traders",
                "Bill No": inv,
                "Bill Date": "01/02/2025",
                "Item Desc": "Steel rods",
                "Qty": 10,
                "Rate": 100,
                "Amount": 1000,
                "Taxable Value": 1000,
                "CGST": 90,
                "SGST": 90,
                "Grand Total": 1180,
                "Currency": "INR",
                "Narration": f"Purchase of goods {inv} input GST",
            }
        elif label == "Sales":
            raw = {
                "Supplier": "Sharma Traders",
                "Customer": f"Buyer {i}",
                "Bill No": inv,
                "Bill Date": "02/02/2025",
                "Item Desc": "Cotton fabric",
                "Qty": 5,
                "Rate": 200,
                "Amount": 1000,
                "Taxable Value": 1000,
                "CGST": 90,
                "SGST": 90,
                "Grand Total": 1180,
                "Currency": "INR",
                "Narration": f"Sales invoice {inv} output GST",
            }
        elif label == "Payment":
            raw = {
                "Supplier": f"Vendor {i}",
                "Customer": "Sharma Traders",
                "Bill No": inv,
                "Bill Date": "03/02/2025",
                "Taxable Value": 5000,
                "Grand Total": 5000,
                "Currency": "INR",
                "Payment Mode": "UPI",
                "UTR / Cheque": "123456789012",
                "Debit Ledger": "Supplier",
                "Credit Ledger": "HDFC Bank",
                "Narration": f"Payment made {inv} UTR recorded",
            }
        else:
            raw = {
                "Supplier": f"Vendor {i}",
                "Customer": "Sharma Traders",
                "Bill No": inv,
                "Bill Date": "04/02/2025",
                "Item Desc": "Godown rent",
                "Amount": 8000,
                "Taxable Value": 8000,
                "CGST": 720,
                "SGST": 720,
                "Grand Total": 9440,
                "Currency": "INR",
                "Narration": f"Office expense {inv} overhead rent",
            }
        rows.append([raw.get(h, "") for h in headers])
        labels.append({"row_id": i + 1, "invoice_number": inv, "voucher_type": label})
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for r in rows:
        ws.append(r)
    wb.save(xlsx_path)
    with open(labels_path, "w", encoding="utf-8") as handle:
        json.dump(labels, handle, indent=2)
    return xlsx_path, labels_path


def test_002_grounded_run_calibrate_evaluate(tmp_path):
    xlsx = str(tmp_path / "tiny.xlsx")
    labels_json = str(tmp_path / "tiny_labels.json")
    _build_tiny_gold(xlsx, labels_json)

    prefix = str(tmp_path / "ex")
    index = exemplars_from_gold(xlsx, labels_json, prefix)
    assert len(index["exemplars"]) == 12
    assert os.path.exists(prefix + "_exemplars.json")

    pred = str(tmp_path / "predictions.jsonl")
    run = _run_cli(
        "run", "--input", xlsx, "--out", pred, "--scorer", "stub", "--exemplars", prefix, "--k", "3"
    )
    assert run.returncode == 0, run.stderr
    assert "n_rows=12" in run.stdout
    with open(pred, encoding="utf-8") as handle:
        lines = [ln for ln in handle if ln.strip()]
    assert len(lines) == 12
    for ln in lines:
        rec = json.loads(ln)
        assert rec["voucher_type"] in LABELS_4 or rec["voucher_type"]

    cal = str(tmp_path / "calibrator.json")
    calib = _run_cli("calibrate", "--pred", pred, "--gold", labels_json, "--out", cal)
    assert calib.returncode == 0, calib.stderr
    cal_data = json.loads(open(cal, encoding="utf-8").read())
    assert set(cal_data) == {"T", "n", "ece_before", "ece_after"}
    assert cal_data["n"] == 12

    rep = str(tmp_path / "report.json")
    ev = _run_cli(
        "evaluate", "--gold", labels_json, "--pred", pred, "--report", rep, "--calibrator", cal
    )
    assert ev.returncode == 0, ev.stderr
    report = json.loads(open(rep, encoding="utf-8").read())
    assert "ece" in report and "pairwise_f1" in report
    assert "ece_before" in report and "ece_after" in report
    assert "coverage_accuracy" in report or "coverage" in report
    assert isinstance(report["pairwise_f1"], dict)
    assert len(report["pairwise_f1"]) == 11
    assert report["n_rows"] == 12
