"""Tests for the enterprise validation gate."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.validate_enterprise import validate


def _write_gold(path: Path) -> None:
    rows = [
        {
            "Seller": "A",
            "Buyer": "Self",
            "Invoice No": "1",
            "Narration": "purchase",
            "voucher_type": "Purchase",
        },
        {
            "Seller": "Self",
            "Buyer": "B",
            "Invoice No": "2",
            "Narration": "sales",
            "voucher_type": "Sales",
        },
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_validation_reports_hand_verified_as_not_enterprise_ready(tmp_path):
    gold = tmp_path / "gold.csv"
    _write_gold(gold)
    report = validate(
        gold,
        dataset_type="hand-verified",
        min_accuracy=0.0,
        min_macro_f1=0.0,
        max_review_rate=1.0,
        max_high_confidence_error_rate=1.0,
        min_support_per_class=0,
    )
    assert report["gate"]["pass"] is True
    assert report["gate"]["enterprise_ready"] is False


def test_validation_rejects_prediction_count_mismatch(tmp_path):
    gold = tmp_path / "gold.csv"
    _write_gold(gold)
    predictions = tmp_path / "pred.jsonl"
    predictions.write_text(
        json.dumps(
            {
                "row_id": 1,
                "invoice_number": "1",
                "voucher_type": "Purchase",
                "confidence": 0.9,
                "needs_review": False,
                "top_k": [["Purchase", 0.9]],
                "evidence": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="does not match"):
        validate(
            gold,
            predictions_path=predictions,
            min_support_per_class=0,
        )
