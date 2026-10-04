"""Unit tests for perspective resolution."""

from __future__ import annotations

from vouch_engine.perspective import normalize_party, resolve


def _row(seller: str | None, buyer: str | None, inv: str | None = None) -> dict:
    return {
        "seller": {"name": seller, "gstin": None},
        "buyer": {"name": buyer, "gstin": None},
        "doc": {"invoice_number": inv, "date": None},
        "items": [],
        "money": {},
        "pay": {},
        "people": {},
        "refs": {},
        "narration": "",
        "raw": {},
        "presence": {},
        "perspective": None,
        "self_entity": None,
    }


def test_seller_self_sheet_is_sales_side() -> None:
    rows = [
        _row("Sharma Traders", "Nagpur Agro", "SI/26-27/0411"),
        _row("Sharma Traders", "Pune Foods", "SI/26-27/0412"),
        _row("Sharma Traders", "Delhi Mart", "SI/26-27/0413"),
        _row("Nagpur Agro", "Sharma Traders", "PUR/09"),
    ]
    self_entity, perspectives = resolve(rows)
    assert self_entity is not None and "Sharma" in self_entity
    assert perspectives[:3] == ["seller", "seller", "seller"]
    assert perspectives[3] == "buyer"
    assert all(r["self_entity"] == self_entity for r in rows)
    assert all(r["perspective"] in ("seller", "buyer", "neither", "unknown") for r in rows)


def test_buyer_self_sheet_is_purchase_side() -> None:
    rows = [
        _row("Supplier A", "Sharma Traders", "SUP-A/101"),
        _row("Supplier B", "Sharma Traders", "SUP-B/102"),
        _row("Supplier C", "Sharma Traders", "SUP-C/103"),
        _row("Sharma Traders", "Customer Z", "SI/26-27/0500"),
    ]
    self_entity, perspectives = resolve(rows)
    assert self_entity is not None and "Sharma" in self_entity
    assert perspectives[:3] == ["buyer", "buyer", "buyer"]
    assert perspectives[3] == "seller"


def test_unknown_when_no_repeat_entity() -> None:
    rows = [
        _row("Seller A", "Buyer A", "X-1"),
        _row("Seller B", "Buyer B", "Y-2"),
    ]
    self_entity, perspectives = resolve(rows)
    assert self_entity is None
    assert perspectives == ["unknown", "unknown"]
    assert all(r["perspective"] == "unknown" for r in rows)


def test_normalize_strips_pvt_ltd() -> None:
    assert normalize_party("Sharma Traders Pvt Ltd") == normalize_party("SHARMA TRADERS")
    assert normalize_party("ABC Private Limited") == normalize_party("abc")


def test_gstin_tiebreak() -> None:
    rows = [
        _row("Alpha", "Beta", "A-1"),
        _row("Beta", "Alpha", "B-2"),
    ]
    for r in rows:
        pass
    rows[0]["seller"]["gstin"] = "27ABCDE1234F1Z5"
    rows[0]["buyer"]["gstin"] = "29XYZAB1234C1Z1"
    rows[1]["seller"]["gstin"] = "29XYZAB1234C1Z1"
    rows[1]["buyer"]["gstin"] = "27ABCDE1234F1Z5"
    # Both entities appear on both sides once -> tie; GSTIN shared on both sides exists.
    self_entity, perspectives = resolve(rows)
    assert self_entity is not None
    assert len(perspectives) == 2
