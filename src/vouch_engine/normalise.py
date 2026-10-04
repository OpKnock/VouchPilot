"""Map arbitrary Excel headers onto the canonical voucher schema."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

GSTIN_RE = re.compile(r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]")

# Canonical flat keys used by map_columns / to_canonical.
CANONICAL_FIELDS = [
    "seller.name",
    "seller.gstin",
    "buyer.name",
    "buyer.gstin",
    "doc.invoice_number",
    "doc.date",
    "items.desc",
    "items.qty",
    "items.rate",
    "items.amount",
    "items.hsn",
    "money.taxable",
    "money.cgst",
    "money.sgst",
    "money.igst",
    "money.total",
    "money.currency",
    "money.discount",
    "money.freight",
    "pay.mode",
    "pay.utr",
    "pay.debit",
    "pay.credit",
    "people.employee",
    "people.period",
    "people.earnings",
    "people.deductions",
    "people.attendance",
    "refs.invoice",
    "refs.order",
    "refs.receipt_note",
    "refs.delivery",
    "narration",
]

ALIASES: dict[str, list[str]] = {
    "seller.name": [
        "seller", "seller name", "supplier", "supplier name", "vendor", "vendor name",
        "seller party", "supplier party", "from party", "sold by",
    ],
    "seller.gstin": [
        "seller gstin", "supplier gstin", "vendor gstin", "seller gst", "supplier gst",
        "seller gst no", "supplier gst no",
    ],
    "buyer.name": [
        "buyer", "buyer name", "customer", "customer name", "client", "client name",
        "buyer party", "customer party", "sold to", "bill to", "ship to",
    ],
    "buyer.gstin": [
        "buyer gstin", "customer gstin", "client gstin", "buyer gst", "customer gst",
        "buyer gst no", "customer gst no",
    ],
    "doc.invoice_number": [
        "invoice no", "invoice number", "invoice no.", "inv no", "inv number",
        "bill no", "bill number", "bill no.", "voucher no", "voucher number",
        "doc no", "document no", "credit note no", "debit note no",
    ],
    "doc.date": [
        "date", "invoice date", "bill date", "voucher date", "doc date", "transaction date",
    ],
    "items.desc": [
        "item", "items", "description", "item description", "product", "particulars",
        "particular", "goods description", "service description", "narration of goods",
    ],
    "items.qty": ["qty", "quantity", "qnty", "nos", "units"],
    "items.rate": ["rate", "price", "unit price", "mrp"],
    "items.amount": ["amount", "item amount", "line amount", "value", "gross amount", "net amount"],
    "items.hsn": ["hsn", "hsn code", "sac", "sac code", "hsn/sac", "hsn sac"],
    "money.taxable": [
        "taxable value", "taxable amount", "taxable", "assessable value", "subtotal",
    ],
    "money.cgst": ["cgst", "cgst amount", "central gst"],
    "money.sgst": ["sgst", "sgst amount", "state gst", "utgst", "utgst amount"],
    "money.igst": ["igst", "igst amount", "integrated gst"],
    "money.total": [
        "total", "grand total", "invoice total", "bill total", "invoice value",
        "invoice amount", "net total", "total amount",
    ],
    "money.currency": ["currency", "curr", "ccy"],
    "money.discount": ["discount", "disc", "discount amount", "trade discount", "cash discount"],
    "money.freight": ["freight", "transport", "transport charges", "shipping charges", "freight charges"],
    "pay.mode": [
        "payment mode", "pay mode", "mode of payment", "mode", "payment method",
        "transaction mode",
    ],
    "pay.utr": [
        "utr", "utr no", "cheque", "cheque no", "cheque number", "check no",
        "transaction id", "txn id", "ref no", "reference no", "neft", "rtgs", "upi ref",
    ],
    "pay.debit": ["debit", "debit ledger", "debit account", "dr ledger", "dr account", "paid from"],
    "pay.credit": ["credit", "credit ledger", "credit account", "cr ledger", "cr account", "paid to"],
    "people.employee": ["employee", "employee name", "emp name", "staff", "worker", "emp code", "employee id"],
    "people.period": ["period", "pay period", "month", "salary month", "pay month", "attendance month"],
    "people.earnings": ["earnings", "basic", "basic pay", "hra", "da", "gross pay", "gross salary", "allowances"],
    "people.deductions": ["deductions", "deduction", "pf", "provident fund", "esi", "esic", "tds", "pt", "professional tax"],
    "people.attendance": ["attendance", "present days", "absent days", "leave", "attendance days"],
    "refs.invoice": ["ref invoice", "invoice ref", "against invoice", "ref inv", "linked invoice"],
    "refs.order": ["order no", "order number", "po no", "po number", "purchase order", "sales order", "so no"],
    "refs.receipt_note": ["receipt note", "grn", "grn no", "receipt note no", "challan", "challan no"],
    "refs.delivery": ["delivery", "delivery note", "delivery challan", "lr", "lr no", "vehicle", "vehicle no", "eway bill", "e-way bill"],
    "narration": ["narration", "remarks", "remark", "comments", "note", "description note", "reason"],
}

CURRENCY_TOKENS: dict[str, str] = {
    "₹": "INR", "rs": "INR", "rs.": "INR", "inr": "INR", "rupee": "INR", "rupees": "INR",
    "indian rupee": "INR", "indian rupees": "INR",
    "$": "USD", "usd": "USD", "us dollar": "USD", "us dollars": "USD", "dollar": "USD", "dollars": "USD",
    "€": "EUR", "eur": "EUR", "euro": "EUR", "euros": "EUR",
    "£": "GBP", "gbp": "GBP", "pound": "GBP", "pounds": "GBP",
    "aed": "AED", "dirham": "AED", "dirhams": "AED",
    "sar": "SAR", "riyal": "SAR", "sgd": "SGD", "cad": "CAD", "aud": "AUD",
    "jpy": "JPY", "yen": "JPY", "cny": "CNY", "yuan": "CNY",
}


def _norm_header(h: str) -> str:
    return re.sub(r"\s+", " ", h.strip().lower())


def _build_alias_lookup() -> tuple[dict[str, str], list[str]]:
    lookup: dict[str, str] = {}
    alias_list: list[str] = []
    for canon, aliases in ALIASES.items():
        for a in aliases:
            key = _norm_header(a)
            if key not in lookup:
                lookup[key] = canon
            alias_list.append(a)
    return lookup, alias_list


_ALIAS_LOOKUP, _ALIAS_LIST = _build_alias_lookup()
_ALIAS_NORM_TO_CANON = {_norm_header(a): _ALIAS_LOOKUP[_norm_header(a)] for a in _ALIAS_LIST}


def _looks_like_gstin(value: Any) -> bool:
    if value is None:
        return False
    s = str(value).strip().upper().replace(" ", "")
    return bool(GSTIN_RE.fullmatch(s))


def _looks_like_currency(value: Any) -> bool:
    if value is None:
        return False
    s = str(value).strip().lower()
    if s in CURRENCY_TOKENS:
        return True
    if s.upper() in {"INR", "USD", "EUR", "GBP", "AED", "SAR", "SGD", "CAD", "AUD", "JPY", "CNY"}:
        return True
    return s in {"₹", "$", "€", "£"}


def _looks_like_hsn(value: Any) -> bool:
    if value is None:
        return False
    s = str(value).strip().replace(" ", "")
    return bool(re.fullmatch(r"\d{4,8}", s))


def _looks_like_date(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (datetime, date)):
        return True
    s = str(value).strip()
    if not s:
        return False
    return _parse_date_to_iso(s) is not None


def map_columns(headers: list[str], sample_rows: list[dict[str, Any]]) -> dict[str, str | None]:
    """Map raw headers to canonical flat keys (or None if unmapped).

    Strategy: (1) alias exact match, (2) RapidFuzz >= 85, (3) value-pattern
    inference for GSTIN / currency / HSN / dates.
    """
    from rapidfuzz import fuzz, process

    mapping: dict[str, str | None] = {}
    taken: set[str] = set()

    # 1. exact alias match.
    unresolved: list[str] = []
    for h in headers:
        canon = _ALIAS_LOOKUP.get(_norm_header(h))
        if canon is not None:
            mapping[h] = canon
            taken.add(canon)
        else:
            unresolved.append(h)

    # 2. fuzzy match >= 85.
    alias_norms = list(_ALIAS_NORM_TO_CANON.keys())
    for h in unresolved:
        if not h.strip():
            mapping[h] = None
            continue
        hit = process.extractOne(_norm_header(h), alias_norms, scorer=fuzz.WRatio, score_cutoff=85)
        if hit is not None:
            mapping[h] = _ALIAS_NORM_TO_CANON[hit[0]]
            taken.add(mapping[h])  # type: ignore[arg-type]
        else:
            mapping[h] = None

    # 3. value-pattern inference for still-unmapped headers.
    for h in headers:
        if mapping[h] is not None:
            continue
        values = [r.get(h) for r in sample_rows if r.get(h) not in (None, "")]
        if not values:
            continue
        n = len(values)
        n_gstin = sum(1 for v in values if _looks_like_gstin(v))
        n_curr = sum(1 for v in values if _looks_like_currency(v))
        n_hsn = sum(1 for v in values if _looks_like_hsn(v))
        n_date = sum(1 for v in values if _looks_like_date(v))
        hl = h.lower()
        is_sellerish = any(k in hl for k in ("sell", "suppl", "vend"))
        is_buyerish = any(k in hl for k in ("buy", "cust", "client"))
        if n_gstin >= max(1, n / 2):
            if is_sellerish:
                mapping[h] = "seller.gstin"
            elif is_buyerish:
                mapping[h] = "buyer.gstin"
            elif "seller.gstin" not in taken:
                mapping[h] = "seller.gstin"
            else:
                mapping[h] = "buyer.gstin"
            taken.add(mapping[h])  # type: ignore[arg-type]
        elif n_curr >= max(1, n / 2):
            mapping[h] = "money.currency"
            taken.add("money.currency")
        elif n_hsn >= max(1, n / 2):
            mapping[h] = "items.hsn"
            taken.add("items.hsn")
        elif n_date >= max(1, n / 2) and "doc.date" not in taken:
            mapping[h] = "doc.date"
            taken.add("doc.date")

    return mapping


def _parse_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if s == "":
        return None
    # Handle (1,000) negatives.
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    s = s.replace(",", "").replace("₹", "").replace("$", "").replace("€", "").replace("£", "")
    s = s.replace("Rs.", "").replace("Rs", "").strip()
    try:
        num = float(s)
    except ValueError:
        return None
    return -num if neg else num


def _parse_date_to_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    s = str(value).strip()
    if not s:
        return None
    # Fast paths for common Indian formats (dayfirst).
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y",
                "%Y-%m-%d", "%Y/%m/%d", "%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%d-%b-%y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    try:
        from dateutil import parser as _parser

        return _parser.parse(s, dayfirst=True).date().isoformat()
    except Exception:
        return None


def _parse_currency(value: Any) -> str:
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return "INR"
    s = str(value).strip()
    key = s.lower()
    if key in CURRENCY_TOKENS:
        return CURRENCY_TOKENS[key]
    up = s.upper()
    if up in {"INR", "USD", "EUR", "GBP", "AED", "SAR", "SGD", "CAD", "AUD", "JPY", "CNY"}:
        return up
    if s in {"₹", "$", "€", "£"}:
        return CURRENCY_TOKENS[s]
    return up


def _first_non_empty(values: list[Any]) -> Any | None:
    for v in values:
        if v is None:
            continue
        if isinstance(v, str) and v.strip() == "":
            continue
        return v
    return None


def to_canonical(rows: list[dict[str, Any]], mapping: dict[str, str | None]) -> list[dict[str, Any]]:
    """Convert raw rows + mapping into CanonicalRow dicts."""
    out: list[dict[str, Any]] = []
    for idx, raw_row in enumerate(rows):
        # Group raw values by canonical key.
        grouped: dict[str, list[Any]] = {}
        unmapped: dict[str, Any] = {}
        for raw_col, val in raw_row.items():
            canon = mapping.get(raw_col)
            if canon is None:
                unmapped[raw_col] = val
            else:
                grouped.setdefault(canon, []).append(val)

        def pick(canon: str) -> Any | None:
            return _first_non_empty(grouped.get(canon, []))

        seller_name = pick("seller.name")
        seller_gstin = pick("seller.gstin")
        buyer_name = pick("buyer.name")
        buyer_gstin = pick("buyer.gstin")
        inv_no = pick("doc.invoice_number")
        doc_date_raw = pick("doc.date")
        item_desc = pick("items.desc")
        item_hsn = pick("items.hsn")
        pay_mode = pick("pay.mode")
        pay_utr = pick("pay.utr")
        pay_debit = pick("pay.debit")
        pay_credit = pick("pay.credit")
        employee = pick("people.employee")
        period = pick("people.period")
        attendance = pick("people.attendance")
        ref_invoice = pick("refs.invoice")
        ref_order = pick("refs.order")
        ref_rn = pick("refs.receipt_note")
        ref_del = pick("refs.delivery")
        narration_raw = pick("narration")

        qty = _parse_number(pick("items.qty"))
        rate = _parse_number(pick("items.rate"))
        amount = _parse_number(pick("items.amount"))
        taxable = _parse_number(pick("money.taxable"))
        cgst = _parse_number(pick("money.cgst"))
        sgst = _parse_number(pick("money.sgst"))
        igst = _parse_number(pick("money.igst"))
        total = _parse_number(pick("money.total"))
        discount = _parse_number(pick("money.discount"))
        freight = _parse_number(pick("money.freight"))

        # Earnings/deductions may aggregate several columns (basic+HRA, PF+ESI).
        earnings_vals = [_parse_number(v) for v in grouped.get("people.earnings", [])]
        earnings_vals = [v for v in earnings_vals if v is not None]
        earnings: float | None = sum(earnings_vals) if earnings_vals else None
        # Keep raw text too if nothing numeric but text present.
        if earnings is None:
            txt = _first_non_empty(grouped.get("people.earnings", []))
            earnings = txt if txt is not None else None  # type: ignore[assignment]
        ded_vals = [_parse_number(v) for v in grouped.get("people.deductions", [])]
        ded_vals = [v for v in ded_vals if v is not None]
        deductions: float | str | None = sum(ded_vals) if ded_vals else None
        if deductions is None:
            txt2 = _first_non_empty(grouped.get("people.deductions", []))
            deductions = txt2 if txt2 is not None else None

        currency = _parse_currency(pick("money.currency"))
        doc_date = _parse_date_to_iso(doc_date_raw)

        def _str_or_none(v: Any | None) -> str | None:
            if v is None:
                return None
            s = str(v).strip()
            return s if s else None

        items: list[dict[str, Any]] = []
        if any(x is not None for x in (item_desc, qty, rate, amount, item_hsn)):
            items.append({
                "desc": _str_or_none(item_desc),
                "qty": qty,
                "rate": rate,
                "amount": amount,
                **({"hsn": _str_or_none(item_hsn)} if item_hsn is not None else {}),
            })

        money: dict[str, Any] = {
            "taxable": taxable,
            "cgst": cgst,
            "sgst": sgst,
            "igst": igst,
            "total": total,
            "currency": currency,
        }
        if discount is not None:
            money["discount"] = discount
        if freight is not None:
            money["freight"] = freight

        has_tax = any(x is not None for x in (cgst, sgst, igst))
        has_items = len(items) > 0
        has_seller = _str_or_none(seller_name) is not None
        has_buyer = _str_or_none(buyer_name) is not None
        has_ledger = _str_or_none(pay_debit) is not None or _str_or_none(pay_credit) is not None
        has_employee = _str_or_none(employee) is not None or earnings is not None
        has_period = _str_or_none(period) is not None
        has_refs = any(
            _str_or_none(x) is not None for x in (ref_invoice, ref_order, ref_rn, ref_del)
        )

        presence: dict[str, bool] = {
            "seller": has_seller,
            "buyer": has_buyer,
            "invoice_no": _str_or_none(inv_no) is not None,
            "doc_date": doc_date is not None,
            "items": has_items,
            "qty": any((it.get("qty") is not None) for it in items),
            "tax": has_tax,
            "total": total is not None,
            "pay_mode": _str_or_none(pay_mode) is not None,
            "utr": _str_or_none(pay_utr) is not None,
            "ledger": has_ledger,
            "employee": has_employee,
            "period": has_period,
            "refs": has_refs,
            "narration": _str_or_none(narration_raw) is not None,
            "currency_foreign": currency != "INR",
        }

        row: dict[str, Any] = {
            "row_id": idx + 1,
            "seller": {"name": _str_or_none(seller_name), "gstin": _str_or_none(seller_gstin)},
            "buyer": {"name": _str_or_none(buyer_name), "gstin": _str_or_none(buyer_gstin)},
            "doc": {"invoice_number": _str_or_none(inv_no), "date": doc_date},
            "items": items,
            "money": money,
            "pay": {
                "mode": _str_or_none(pay_mode),
                "utr": _str_or_none(pay_utr),
                "debit": _str_or_none(pay_debit),
                "credit": _str_or_none(pay_credit),
            },
            "people": {
                "employee": _str_or_none(employee),
                "period": _str_or_none(period),
                "earnings": earnings,
                "deductions": deductions,
                **({"attendance": _str_or_none(attendance)} if attendance is not None else {}),
            },
            "refs": {
                "invoice": _str_or_none(ref_invoice),
                "order": _str_or_none(ref_order),
                "receipt_note": _str_or_none(ref_rn),
                "delivery": _str_or_none(ref_del),
            },
            "narration": _str_or_none(narration_raw) or "",
            "raw": unmapped,
            "presence": presence,
            "perspective": None,
            "self_entity": None,
        }
        out.append(row)
    return out
