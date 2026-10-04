"""Hindi/Marathi header pre-pass for VouchIQ.

This module lives HERE (not in normalise.py/baseline.py, which are frozen).
It translates Hindi/Marathi Excel headers to the English aliases that
``vouch_engine.normalise`` already understands, and folds non-ASCII digits.

Usage: run ``translate_header`` + ``fold_digits`` on raw headers BEFORE
calling ``normalise.map_columns``.
"""

from __future__ import annotations

from typing import Any

# Hindi/Marathi header -> English alias already understood by normalise.ALIASES.
# Every value below is an exact (case-insensitive) alias in normalise.ALIASES,
# so normalise.map_columns maps the translated header to the canonical field.
HI_ALIASES: dict[str, str] = {
    # Seller side.
    "विक्रेता": "seller",
    "आपूर्तिकर्ता": "supplier",
    "विक्रेता जीएसटी": "seller gstin",
    # Buyer side.
    "खरीदार": "buyer",
    "ग्राहक": "customer",
    "खरेदीदार": "buyer",
    "ग्राहक जीएसटी": "customer gstin",
    # Invoice number.
    "बीजक": "invoice no",
    "चालान संख्या": "invoice no",
    "बिल नंबर": "bill no",
    # Date.
    "तारीख": "date",
    "दिनांक": "date",
    # Line-item description.
    "विवरण": "description",
    "वर्णन": "description",
    # Quantity.
    "मात्रा": "qty",
    "संख्या": "qty",
    # Rate.
    "दर": "rate",
    "भाव": "rate",
    # Taxable value.
    "कर योग्य मूल्य": "taxable value",
    # Amount / total. "total" is chosen (over "amount") so that normalise maps
    # राशि/रक्कम to money.total, matching the downstream total expectation.
    "राशि": "total",
    "रक्कम": "total",
    # Tax break-up. Generic "कर" maps to money.taxable via the "taxable" alias.
    "कर": "taxable",
    "सीजीएसटी": "cgst",
    "एसजीएसटी": "sgst",
    "आईजीएसटी": "igst",
    # Payment.
    "भुगतान": "payment mode",
    "UTR": "utr",
    "utr": "utr",
    # Currency.
    "मुद्रा": "currency",
    # Narration.
    "टिप्पणी": "narration",
    "टिपण": "narration",
    # GSTIN (generic -> seller gstin; buyer variant is covered above).
    "जीएसटी नंबर": "seller gstin",
    "जीएसटी": "seller gstin",
    # Grand total.
    "कुल": "total",
    "एकूण": "total",
    # Employee.
    "कर्मचारी": "employee",
    # Order reference.
    "आदेश": "order no",
    # Generic reference.
    "संदर्भ": "ref invoice",
}


def translate_header(h: str) -> str:
    """Translate one raw header to its English alias.

    Strips surrounding whitespace, returns the exact ``HI_ALIASES`` match,
    else returns the stripped original unchanged.
    """
    if not isinstance(h, str):
        return h  # type: ignore[return-value]
    stripped = h.strip()
    return HI_ALIASES.get(stripped, stripped)


# Devanagari ०-९ (U+0966-U+096F) + Arabic-Indic ٠-٩ (U+0660-U+0669) -> 0-9.
_DIGIT_MAP: dict[int, str] = {
    **{ord("०") + i: str(i) for i in range(10)},
    **{ord("٠") + i: str(i) for i in range(10)},
}


def fold_digits(s: str) -> str:
    """Fold Devanagari and Arabic-Indic digits to ASCII 0-9.

    Leaves every other character untouched. Non-string input is returned as-is.
    """
    if not isinstance(s, str):
        return s  # type: ignore[return-value]
    return s.translate(_DIGIT_MAP)


# DISPLAY / EXPLANATION ONLY. This table is NEVER used for scoring and MUST
# NOT feed keyword_predict, map_columns, or any classifier. It exists solely
# so UI / explanation layers can show a Hindi/Marathi cue word next to an
# already-decided English label.
HINDI_CUES: dict[str, list[str]] = {
    "Purchase": ["खरीद"],
    "Sales": ["बिक्री", "विक्री"],
    "Payment": ["भुगतान"],
    "Receipt": ["प्राप्ति"],
    "Salary": ["वेतन", "पगार"],
    "Order": ["आदेश"],
    "Return": ["वापसी", "परतावा"],
}


def _is_empty_cell(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


__all__ = ["HI_ALIASES", "HINDI_CUES", "translate_header", "fold_digits"]
