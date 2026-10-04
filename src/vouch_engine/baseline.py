"""Keyword baseline A0: versioned 27-label keyword table + pure scoring.

Rules (Team-B contract):
- Score = keyword hits across narration + item descriptions + raw values.
- Case-insensitive substring match, one hit per distinct keyword present.
- Winner = max hits; ties broken by fixed LABELS order.
- Confidence 0.9 if hits >= 2 and strictly unique, 0.6 if hits == 1 unique,
  0.35 on tie or zero.
"""

from __future__ import annotations

from typing import Any

from .labels import LABELS

# Versioned keyword table covering all 27 labels (Indian accounting vocabulary).
# Keys are canonical label names from LABEL_NAMES.
KEYWORDS: dict[str, list[str]] = {
    "Purchase": [
        "purchase",
        "supplier",
        "input gst",
        "purchase invoice",
        "bought",
        "procurement",
    ],
    "Sales": [
        "sales",
        "customer",
        "output gst",
        "sales invoice",
        "sold",
        "selling",
    ],
    "Import": [
        "import",
        "bill of entry",
        "customs",
        "custom duty",
        "customs duty",
        "iec",
        "foreign supplier",
        "overseas supplier",
        "cif",
        "fob",
        "port of loading",
        "clearing agent",
    ],
    "Export": [
        "export",
        "shipping bill",
        "lut",
        "bond",
        "incoterms",
        "foreign customer",
        "overseas buyer",
        "export invoice",
        "port of discharge",
        "cif",
        "fob",
    ],
    "Purchase Return / Debit Note": [
        "purchase return",
        "debit note",
        "return to supplier",
        "supplier return",
        "purchase rejection",
        "return",
    ],
    "Sales Return / Credit Note": [
        "sales return",
        "credit note",
        "customer return",
        "return from customer",
        "sales rejection",
        "returned goods",
        "return",
    ],
    "Rejection Out": [
        "rejection out",
        "rejected outward",
        "rejection outward",
        "outward rejection",
        "goods rejected outward",
        "quantity rejected",
        "rejection memo",
    ],
    "Rejection In": [
        "rejection in",
        "rejected inward",
        "rejection inward",
        "inward rejection",
        "goods rejected inward",
        "rejected by customer",
        "quantity rejected",
        "rejection memo",
    ],
    "Payment": [
        "payment",
        "paid",
        "neft",
        "rtgs",
        "imps",
        "utr",
        "cheque payment",
        "cash paid",
        "vendor payment",
        "outgoing payment",
        "upi payment",
        "bank transfer paid",
    ],
    "Receipt": [
        "receipt",
        "received",
        "collection",
        "incoming payment",
        "cheque received",
        "cash received",
        "customer payment",
        "money receipt",
        "upi receipt",
        "neft",
        "rtgs",
        "imps",
        "utr",
    ],
    "Contra": [
        "contra",
        "cash deposit",
        "cash withdrawal",
        "bank to cash",
        "cash to bank",
        "fund transfer between",
        "cash bank transfer",
        "bank to bank transfer",
        "cash in hand to bank",
    ],
    "Advance / Prepayment": [
        "advance",
        "prepayment",
        "pre-payment",
        "token advance",
        "advance payment",
        "advance receipt",
        "mobilisation advance",
        "mobilization advance",
        "booking advance",
        "on account",
        "security deposit advance",
    ],
    "Journal": [
        "journal",
        "adjustment",
        "depreciation",
        "provision",
        "accrual",
        "rectification",
        "write off",
        "write-off",
        "deferred",
        "amortisation",
        "amortization",
        "round off",
        "round-off",
    ],
    "Expense": [
        "expense",
        "expenses",
        "petty cash",
        "conveyance",
        "travelling",
        "travel",
        "telephone",
        "electricity",
        "rent",
        "stationery",
        "repairs",
        "maintenance",
        "professional fees",
        "audit fees",
        "consultancy",
        "overhead",
        "service charge",
        "diesel",
        "fuel",
    ],
    "Other / Miscellaneous": [
        "miscellaneous",
        "misc",
        "other charges",
        "general",
        "unclassified",
        "suspense",
        "sundry",
    ],
    "Salary / Payroll": [
        "salary",
        "payroll",
        "wages",
        "pf contribution",
        "esi",
        "bonus",
        "payslip",
        "employee salary",
        "staff salary",
        "provident fund",
        "gratuity",
    ],
    "Attendance": [
        "attendance",
        "present days",
        "absent",
        "leave",
        "muster",
        "shift",
        "overtime",
        "half day",
        "attendance register",
        "loss of pay",
        "lop days",
    ],
    "Purchase Order": [
        "purchase order",
        "purchase indent",
        "po no",
        "po number",
        "purchase requisition",
        "indent",
        "order",
    ],
    "Sales Order": [
        "sales order",
        "so no",
        "so number",
        "order booked",
        "sales indent",
        "customer order",
        "order",
    ],
    "Receipt Note": [
        "receipt note",
        "grn",
        "goods receipt",
        "material receipt",
        "goods inward note",
        "receipt challan",
        "purchase receipt",
        "receipt",
    ],
    "Delivery Note": [
        "delivery note",
        "delivery challan",
        "dispatch",
        "despatch",
        "lr number",
        "lorry receipt",
        "eway bill",
        "e-way bill",
        "goods dispatched",
        "delivery",
        "challan",
    ],
    "Material In": [
        "material in",
        "goods inward",
        "stock inward",
        "inward entry",
        "store receipt",
        "material receipt",
        "material inward",
        "goods received",
        "material",
    ],
    "Material Out": [
        "material out",
        "goods outward",
        "stock outward",
        "outward entry",
        "store issue",
        "material issue",
        "material outward",
        "goods issued",
        "material",
    ],
    "Job Work In Order": [
        "job work in",
        "jobwork in",
        "job work received",
        "job work inward",
        "challan for job work",
        "job worker receipt",
        "jobwork challan inward",
        "job work",
        "jobwork",
    ],
    "Job Work Out Order": [
        "job work out",
        "jobwork out",
        "job work sent",
        "job work outward",
        "challan for job work",
        "job worker issue",
        "jobwork challan outward",
        "job work",
        "jobwork",
    ],
    "Stock Journal": [
        "stock journal",
        "stock transfer",
        "godown transfer",
        "branch transfer",
        "material transfer",
        "stock adjustment",
        "godown",
        "stock",
    ],
    "Physical Stock": [
        "physical stock",
        "stock verification",
        "stock counting",
        "inventory count",
        "stock audit",
        "physical inventory",
        "inventory",
        "stock",
    ],
}

_KEYWORD_SETS: dict[str, list[str]] = {
    name: [k.lower() for k in kws] for name, kws in KEYWORDS.items()
}


def _flatten_raw(value: Any, out: list[str]) -> None:
    """Recursively collect string values from nested raw structures."""
    if value is None:
        return
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, (int, float)):
        out.append(str(value))
    elif isinstance(value, dict):
        for v in value.values():
            _flatten_raw(v, out)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _flatten_raw(v, out)
    else:
        out.append(str(value))


def _row_text(row: dict[str, Any]) -> str:
    """Build the searchable blob: narration + item descs + raw values."""
    parts: list[str] = []
    narration = row.get("narration", "")
    if isinstance(narration, str):
        parts.append(narration)
    elif narration is not None:
        parts.append(str(narration))
    items = row.get("items", [])
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                for key in ("desc", "description", "name", "item", "particulars"):
                    if key in item and item[key] is not None:
                        parts.append(str(item[key]))
                # Fallback: include any other string values in the item dict.
                if not any(k in item for k in ("desc", "description", "name")):
                    buf: list[str] = []
                    _flatten_raw(item, buf)
                    parts.extend(buf)
            elif item is not None:
                parts.append(str(item))
    elif isinstance(items, dict):
        buf2: list[str] = []
        _flatten_raw(items, buf2)
        parts.extend(buf2)
    raw = row.get("raw", None)
    if raw is not None:
        buf3: list[str] = []
        _flatten_raw(raw, buf3)
        parts.extend(buf3)
    return "\n".join(parts).lower()


def keyword_predict(row: dict[str, Any], tags: list[str]) -> tuple[str, float]:
    """Score a canonical row with keyword hits.

    Args:
        row: CanonicalRow as plain dict.
        tags: Evidence tags (accepted for signature parity; not scored).

    Returns:
        (label, confidence) with label in LABEL_NAMES.
    """
    _ = tags  # tags intentionally not scored; contract scores text fields only.
    blob = _row_text(row if isinstance(row, dict) else {})
    scores: dict[str, int] = {}
    for label in LABELS:
        name = label["name"]
        kws = _KEYWORD_SETS.get(name, [])
        scores[name] = sum(1 for kw in kws if kw and kw in blob)
    best_label = LABELS[0]["name"]
    best_score = -1
    for label in LABELS:  # fixed LABELS order breaks ties deterministically.
        name = label["name"]
        if scores[name] > best_score:
            best_score = scores[name]
            best_label = name
    top_count = sum(1 for v in scores.values() if v == best_score)
    if top_count > 1 or best_score <= 0:
        return best_label, 0.35
    if best_score >= 2:
        return best_label, 0.9
    return best_label, 0.6
