"""Tests for extensions/report_vendor.py (in-memory sqlite only)."""

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from extensions.report_vendor import vendor_summary  # noqa: E402


def _bills_conn():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE bills (seller TEXT, total REAL, voucher_type TEXT, "
        "needs_review INTEGER, fraud_score REAL)"
    )
    conn.executemany(
        "INSERT INTO bills VALUES (?, ?, ?, ?, ?)",
        [
            ("Acme Traders", 100.0, "Purchase", 0, 0.1),
            ("Acme Traders", 200.0, "Purchase", 1, 0.9),
            ("Beta Stores", 50.0, "Sales", 0, 0.2),
        ],
    )
    conn.commit()
    return conn


def test_bills_per_vendor_stats():
    out = vendor_summary(_bills_conn())
    assert out["n_vendors"] == 2
    assert "generated_at" in out
    by_vendor = {v["vendor"]: v for v in out["vendors"]}
    acme = by_vendor["Acme Traders"]
    assert acme["rows"] == 2
    assert acme["total"] == pytest.approx(300.0)
    assert acme["needs_review_rate"] == pytest.approx(0.5)
    assert acme["fraud_rate"] == pytest.approx(0.5)
    beta = by_vendor["Beta Stores"]
    assert beta["rows"] == 1
    assert beta["fraud_rate"] == pytest.approx(0.0)


def test_bills_missing_optional_cols():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE bills (vendor TEXT, amount REAL)")
    conn.executemany("INSERT INTO bills VALUES (?, ?)", [("Solo", 10.0), ("Solo", 20.0)])
    conn.commit()
    out = vendor_summary(conn)
    assert out["n_vendors"] == 1
    vendor = out["vendors"][0]
    assert vendor["rows"] == 2
    assert vendor["total"] == pytest.approx(30.0)
    assert vendor["needs_review_rate"] == 0.0
    assert vendor["fraud_rate"] == 0.0


def test_empty_db_returns_warning():
    out = vendor_summary(sqlite3.connect(":memory:"))
    assert out["vendors"] == []
    assert out["n_vendors"] == 0
    assert out["warning"] == "no-compatible-tables"
    assert "generated_at" in out
