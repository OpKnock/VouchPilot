"""Unit tests for header mapping and canonicalisation."""

from __future__ import annotations

from vouch_engine.normalise import ALIASES, map_columns, to_canonical


def test_aliases_cover_required_families() -> None:
    blob = " | ".join(a.lower() for v in ALIASES.values() for a in v)
    for token in [
        "supplier", "vendor", "customer", "client", "bill no", "particulars",
        "qty", "rate", "taxable value", "cgst", "sgst", "igst", "discount",
        "freight", "payment mode", "utr", "cheque", "currency", "gstin",
        "hsn", "sac", "employee", "basic", "hra", "pf", "esi", "order no",
        "challan", "lr", "vehicle", "debit", "credit", "narration", "remarks",
    ]:
        assert token in blob, f"missing alias token: {token}"


def test_map_columns_exact_alias() -> None:
    headers = ["Supplier", "Customer", "Bill No", "Taxable Value", "CGST", "SGST"]
    mapping = map_columns(headers, [])
    assert mapping["Supplier"] == "seller.name"
    assert mapping["Customer"] == "buyer.name"
    assert mapping["Bill No"] == "doc.invoice_number"
    assert mapping["Taxable Value"] == "money.taxable"


def test_map_columns_fuzzy() -> None:
    # Misspelled header still maps with RapidFuzz >= 85.
    headers = ["Suppliar Name"]
    mapping = map_columns(headers, [])
    assert mapping["Suppliar Name"] == "seller.name"


def test_map_columns_value_pattern_gstin() -> None:
    headers = ["Party Code"]
    sample = [
        {"Party Code": "27ABCDE1234F1Z5"},
        {"Party Code": "29ABCDE1234F1Z1"},
    ]
    mapping = map_columns(headers, sample)
    assert mapping["Party Code"] in ("seller.gstin", "buyer.gstin")


def test_map_columns_value_pattern_currency_and_hsn() -> None:
    mapping = map_columns(
        ["Curr", "HSNCode"],
        [{"Curr": "USD", "HSNCode": "8471"}, {"Curr": "USD", "HSNCode": "8471"}],
    )
    assert mapping["Curr"] == "money.currency"
    assert mapping["HSNCode"] == "items.hsn"


def test_to_canonical_indian_grouping_dayfirst_and_defaults() -> None:
    rows = [{
        "Supplier": "Sharma Traders",
        "Customer": "Nagpur Agro",
        "Bill No": "SI/001",
        "Bill Date": "31/03/2026",
        "Taxable Value": "1,23,456.00",
        "Grand Total": "1,45,678.50",
    }]
    mapping = map_columns(
        ["Supplier", "Customer", "Bill No", "Bill Date", "Taxable Value", "Grand Total"], rows
    )
    canon = to_canonical(rows, mapping)
    assert len(canon) == 1
    r = canon[0]
    assert r["row_id"] == 1
    assert r["seller"] == {"name": "Sharma Traders", "gstin": None}
    assert r["buyer"] == {"name": "Nagpur Agro", "gstin": None}
    assert r["doc"] == {"invoice_number": "SI/001", "date": "2026-03-31"}
    assert r["money"]["taxable"] == 123456.0
    assert r["money"]["total"] == 145678.5
    assert r["money"]["currency"] == "INR"  # default
    assert r["money"]["cgst"] is None
    assert r["perspective"] is None
    assert r["self_entity"] is None
    assert r["presence"]["seller"] is True
    assert r["presence"]["tax"] is False
    assert isinstance(r["raw"], dict)
    assert isinstance(r["narration"], str)
