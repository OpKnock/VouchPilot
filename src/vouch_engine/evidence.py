"""Evidence tags + soft feasibility mask over the 27 labels."""

from __future__ import annotations

import re
from typing import Any

from .labels import LABEL_NAMES

_CUE_KEYWORDS = ["return", "returned", "damaged", "defective", "advance", "depreciation",
                 "on account", "deposit", "token", "prepaid", "discount", "written off"]

_CUSTOMS_HINTS = ["bill of entry", "port", "customs", "custom duty", "customs duty",
                  "iec", "cif", "fob", "boedry", "boe"]
_SHIPPING_HINTS = ["shipping bill", "lut", "bond", "port", "incoterm", "fob", "cif", "export"]


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _has_party(row: dict[str, Any]) -> bool:
    s = (row.get("seller") or {}).get("name")
    b = (row.get("buyer") or {}).get("name")
    return bool(s and str(s).strip()) or bool(b and str(b).strip())


def _text_blob(row: dict[str, Any]) -> str:
    parts: list[str] = []
    for v in (row.get("narration"),):
        if v:
            parts.append(str(v))
    for it in row.get("items") or []:
        if isinstance(it, dict) and it.get("desc"):
            parts.append(str(it["desc"]))
    raw = row.get("raw") or {}
    if isinstance(raw, dict):
        for v in raw.values():
            if isinstance(v, str) and v.strip():
                parts.append(v)
    return " ".join(parts).lower()


def _has_hint(blob: str, hints: list[str]) -> bool:
    return any(h in blob for h in hints)


def extract(row: dict[str, Any]) -> tuple[list[str], dict[str, float]]:
    """Return (tags, mask) for one canonical row. Mask values in (0, 1]."""
    tags: list[str] = []
    money = row.get("money") or {}
    pay = row.get("pay") or {}
    people = row.get("people") or {}
    refs = row.get("refs") or {}
    doc = row.get("doc") or {}
    items = row.get("items") or []
    presence = row.get("presence") or {}

    # --- Perspective ---
    persp = row.get("perspective") or "unknown"
    tags.append(f"PERSPECTIVE: {persp}")

    # --- Document sign ---
    totals = [_num(money.get(k)) for k in ("total", "taxable")]
    totals = [t for t in totals if t is not None]
    negative = any(t is not None and t < 0 for t in totals)
    tags.append("DOC_SIGN: negative" if negative else "DOC_SIGN: positive")

    # --- Items ---
    has_items = len(items) > 0
    tags.append(f"HAS_ITEMS: {'yes' if has_items else 'no'}")
    if not has_items:
        tags.append("NO_ITEMS")
    qty_present = any(isinstance(it, dict) and it.get("qty") is not None for it in items)
    price_present = any(
        isinstance(it, dict) and (it.get("rate") is not None or it.get("amount") is not None)
        for it in items
    )
    if has_items and qty_present and not price_present:
        tags.append("QTY_ONLY: yes")
    else:
        tags.append("QTY_ONLY: no")

    inv_no = doc.get("invoice_number")
    if not inv_no or (isinstance(inv_no, str) and not inv_no.strip()):
        tags.append("NO_INVOICE_NO")

    # --- Tax ---
    cgst, sgst, igst = money.get("cgst"), money.get("sgst"), money.get("igst")
    has_cgst = _num(cgst) is not None
    has_sgst = _num(sgst) is not None
    has_igst = _num(igst) is not None
    if has_cgst and has_sgst:
        tags.append("TAX: CGST+SGST")
    elif has_igst:
        tags.append("TAX: IGST")
    else:
        tags.append("TAX: none")
    taxable = _num(money.get("taxable"))
    total = _num(money.get("total"))
    if taxable is not None and total is not None:
        rate_sum = sum(_num(x) or 0.0 for x in (cgst, sgst, igst))
        if abs(taxable + rate_sum - total) < 1.0:
            tags.append("TAX_ARITHMETIC: consistent")
        else:
            tags.append("TAX_ARITHMETIC: inconsistent")
    else:
        tags.append("TAX_ARITHMETIC: unknown")

    # --- Money movement ---
    mode = (pay.get("mode") or "")
    if isinstance(mode, str) and mode.strip():
        tags.append(f"PAY_MODE: {mode.strip().lower()}")
    else:
        tags.append("PAY_MODE: none")
    debit, credit = pay.get("debit"), pay.get("credit")
    if debit and credit:
        tags.append(f"LEDGER_PAIR: {str(debit).strip()}-to-{str(credit).strip()}")
    elif debit or credit:
        tags.append("LEDGER_PAIR: single")
    else:
        tags.append("LEDGER_PAIR: none")
    utr = pay.get("utr")
    tags.append(
        "HAS_UTR_OR_CHEQUE: yes" if utr and str(utr).strip() else "HAS_UTR_OR_CHEQUE: no"
    )

    # --- Cross-border ---
    currency = (money.get("currency") or "INR")
    cur_up = str(currency).upper()
    if cur_up != "INR":
        tags.append(f"CURRENCY: {cur_up} (foreign)")
    else:
        tags.append("CURRENCY: INR")
    blob = _text_blob(row)
    customs = _has_hint(blob, _CUSTOMS_HINTS)
    shipping = _has_hint(blob, _SHIPPING_HINTS)
    tags.append(f"HAS_CUSTOMS_FIELDS: {'yes' if customs else 'no'}")
    tags.append(f"HAS_SHIPPING_BILL: {'yes' if shipping else 'no'}")

    # --- People ---
    emp = people.get("employee")
    per = people.get("period")
    earn = people.get("earnings")
    ded = people.get("deductions")
    att = people.get("attendance")
    tags.append(f"EMPLOYEE_FIELDS: {'yes' if emp or earn is not None else 'no'}")
    tags.append(f"PAY_PERIOD: {'yes' if per else 'no'}")
    tags.append(f"DEDUCTIONS: {'yes' if ded is not None else 'no'}")
    tags.append(f"ATTENDANCE_FIELDS: {'yes' if att else 'no'}")

    # --- References ---
    if refs.get("invoice"):
        tags.append(f"REFS_INVOICE: {refs['invoice']}")
    else:
        tags.append("REFS_INVOICE: none")
    if refs.get("order"):
        tags.append("REFS_ORDER: yes")
    else:
        tags.append("REFS_ORDER: no")
    if refs.get("receipt_note"):
        tags.append("REFS_RECEIPT_NOTE: yes")
    else:
        tags.append("REFS_RECEIPT_NOTE: no")
    if refs.get("delivery"):
        tags.append("REFS_DELIVERY: yes")
    else:
        tags.append("REFS_DELIVERY: no")

    # --- Narration cues ---
    for kw in _CUE_KEYWORDS:
        if kw in blob:
            tags.append(f'CUE: "{kw}"')

    # --- Absence signals ---
    if not _has_party(row):
        tags.append("NO_PARTY")

    # --- Mask ---
    mask: dict[str, float] = {name: 1.0 for name in LABEL_NAMES}

    def penalise(label: str, factor: float) -> None:
        mask[label] = min(mask[label], factor)

    has_people = bool(emp or per or earn is not None or ded is not None)
    has_employee_fields = bool(emp or earn is not None or per)
    has_attendance = bool(att)
    party_present = _has_party(row)
    two_ledgers = bool(debit and credit and str(debit).strip() and str(credit).strip())
    foreign = cur_up != "INR"
    has_refs = bool(refs.get("invoice") or refs.get("order") or refs.get("receipt_note") or refs.get("delivery"))

    # Logically impossible -> 0.05.
    if not has_people:
        penalise("Salary / Payroll", 0.05)
    if not (has_employee_fields or has_attendance):
        penalise("Attendance", 0.05)
    if party_present:
        penalise("Stock Journal", 0.05)
        penalise("Physical Stock", 0.05)
    if not two_ledgers:
        penalise("Contra", 0.05)
    if not has_items and not party_present:
        # Pure money movement cannot be a trade invoice.
        for lab in ("Purchase", "Sales", "Import", "Export"):
            penalise(lab, 0.05)
    if has_items and two_ledgers and not party_present:
        pass  # ambiguous; leave to unlikely tier below.

    # Unlikely -> 0.5.
    if not foreign and not customs:
        penalise("Import", 0.5)
        penalise("Export", 0.5)
    if has_items:
        penalise("Expense", 0.5)  # expense wins only when no stock items
        penalise("Payment", 0.5)
        penalise("Receipt", 0.5)
        penalise("Contra", 0.5)
        penalise("Journal", 0.5)
    if not has_items:
        penalise("Purchase", 0.5)
        penalise("Sales", 0.5)
        penalise("Purchase Return / Debit Note", 0.5)
        penalise("Sales Return / Credit Note", 0.5)
    if not negative:
        penalise("Purchase Return / Debit Note", 0.5)
        penalise("Sales Return / Credit Note", 0.5)
    if inv_no and str(inv_no).strip():
        penalise("Advance / Prepayment", 0.5)  # advance moves money without settling invoice
    if not has_refs:
        penalise("Rejection Out", 0.5)
        penalise("Rejection In", 0.5)
    if party_present or has_items or two_ledgers:
        penalise("Other / Miscellaneous", 0.5)  # last resort only
    if _has_party(row) or has_items:
        penalise("Attendance", 0.5)

    # Clamp into (0, 1].
    for k, v in mask.items():
        mask[k] = max(0.01, min(1.0, float(v)))

    # Re-assert impossibles that the clamp must not lift above 0.05.
    if not has_people:
        mask["Salary / Payroll"] = 0.05
    if party_present:
        mask["Stock Journal"] = 0.05
        mask["Physical Stock"] = 0.05
    if not two_ledgers:
        mask["Contra"] = 0.05

    _ = re.compile  # keep import used for future cue regexes
    _ = presence
    return tags, mask
