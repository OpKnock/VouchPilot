"""Unit tests for the keyword baseline A0."""

from vouch_engine.baseline import KEYWORDS, keyword_predict
from vouch_engine.labels import LABEL_NAMES


def _sales_row() -> dict:
    return {
        "row_id": 1,
        "seller": {"name": "Sharma Traders", "gstin": ""},
        "buyer": {"name": "Nagpur Agro Pvt Ltd", "gstin": ""},
        "doc": {"invoice_number": "SI/26-27/0412", "date": "2026-08-01"},
        "items": [{"desc": "office chairs qty 10"}],
        "money": {"taxable": 50000, "cgst": 4500, "sgst": 4500},
        "pay": {},
        "narration": "Sales invoice for goods sold to customer, output gst",
        "raw": {"bill": "sales invoice SI/26-27/0412"},
        "presence": {},
        "perspective": "seller",
        "self_entity": "Sharma Traders",
    }


def test_keywords_cover_all_labels():
    assert set(KEYWORDS.keys()) == set(LABEL_NAMES)
    for name, kws in KEYWORDS.items():
        assert isinstance(kws, list) and len(kws) >= 1, name


def test_sales_like_row_wins_sales():
    label, conf = keyword_predict(_sales_row(), tags=[])
    assert label == "Sales"
    assert conf == 0.9


def test_empty_row_returns_valid_label_with_low_confidence():
    label, conf = keyword_predict({}, tags=[])
    assert label in LABEL_NAMES
    assert conf == 0.35
