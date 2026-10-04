"""Unit tests for evidence tags and feasibility mask."""

from __future__ import annotations

from vouch_engine.evidence import extract
from vouch_engine.labels import LABEL_NAMES


def _base_row(**over: object) -> dict:
    row: dict = {
        "seller": {"name": "Sharma Traders", "gstin": None},
        "buyer": {"name": "Nagpur Agro", "gstin": None},
        "doc": {"invoice_number": "SI/001", "date": "2026-03-31"},
        "items": [{"desc": "Office chairs", "qty": 10.0, "rate": 5000.0, "amount": 50000.0}],
        "money": {"taxable": 50000.0, "cgst": 4500.0, "sgst": 4500.0, "igst": None,
                  "total": 59000.0, "currency": "INR"},
        "pay": {"mode": None, "utr": None, "debit": None, "credit": None},
        "people": {"employee": None, "period": None, "earnings": None, "deductions": None},
        "refs": {"invoice": None, "order": None, "receipt_note": None, "delivery": None},
        "narration": "",
        "raw": {},
        "presence": {},
        "perspective": "seller",
        "self_entity": "Sharma Traders",
    }
    row.update(over)
    return row


def test_trade_row_tags() -> None:
    tags, mask = extract(_base_row())
    assert "PERSPECTIVE: seller" in tags
    assert "HAS_ITEMS: yes" in tags
    assert "TAX: CGST+SGST" in tags
    assert "TAX_ARITHMETIC: consistent" in tags
    assert "CURRENCY: INR" in tags
    assert set(mask.keys()) == set(LABEL_NAMES)
    assert all(0.0 < v <= 1.0 for v in mask.values())


def test_salary_impossible_without_people() -> None:
    tags, mask = extract(_base_row())
    assert mask["Salary / Payroll"] == 0.05
    assert "EMPLOYEE_FIELDS: no" in tags


def test_stock_impossible_with_party() -> None:
    _, mask = extract(_base_row())
    assert mask["Stock Journal"] == 0.05
    assert mask["Physical Stock"] == 0.05


def test_contra_impossible_without_two_ledgers() -> None:
    _, mask = extract(_base_row())
    assert mask["Contra"] == 0.05
    row = _base_row()
    row["seller"] = {"name": None, "gstin": None}
    row["buyer"] = {"name": None, "gstin": None}
    row["items"] = []
    row["pay"] = {"mode": "bank", "utr": "UTR123", "debit": "HDFC Current", "credit": "Cash"}
    tags2, mask2 = extract(row)
    assert mask2["Contra"] == 1.0
    assert "LEDGER_PAIR: HDFC Current-to-Cash" in tags2
    assert "NO_PARTY" in tags2
    assert "NO_ITEMS" in tags2


def test_foreign_and_cues() -> None:
    row = _base_row()
    row["money"] = {"taxable": 1000.0, "cgst": None, "sgst": None, "igst": 180.0,
                    "total": 1180.0, "currency": "USD"}
    row["narration"] = "goods damaged, return against SI/0398, advance adjusted"
    tags, mask = extract(row)
    assert "CURRENCY: USD (foreign)" in tags
    assert "TAX: IGST" in tags
    assert any(t.startswith('CUE: "return"') for t in tags)
    assert any("damaged" in t for t in tags)
    assert mask["Import"] >= 0.5  # foreign currency keeps import feasible


def test_qty_only_and_no_invoice() -> None:
    row = _base_row()
    row["items"] = [{"desc": "Rejected qty", "qty": 5.0, "rate": None, "amount": None}]
    row["doc"] = {"invoice_number": None, "date": None}
    tags, _ = extract(row)
    assert "QTY_ONLY: yes" in tags
    assert "NO_INVOICE_NO" in tags
