"""Unit tests for extensions.triage_sms."""

from __future__ import annotations

from extensions.triage_sms import normalize_text


def test_bengali_suffix_strip() -> None:
    out = normalize_text("\u09ac\u09bf\u09b2\u0997\u09c1\u09b2\u09bf \u09aa\u09b0\u09bf\u09b6\u09cb\u09a7")
    assert "\u0997\u09c1\u09b2\u09bf" not in out
    assert "\u09ac\u09bf\u09b2" in out


def test_english_stopword_removal() -> None:
    assert normalize_text("Please pay the bill, sir") == "pay bill"


def test_empty_and_non_string() -> None:
    assert normalize_text("") == ""
    assert normalize_text(None) == ""
    assert normalize_text(123) == ""


def test_long_digits_dropped_short_kept() -> None:
    assert "1234567" not in normalize_text("utr 1234567 ref 5000")
    assert "5000" in normalize_text("utr 1234567 ref 5000")


def test_idempotent() -> None:
    x = "Please \u09ac\u09bf\u09b2\u0997\u09c1\u09b2\u09bf pay Rs 5000 only, sir"
    once = normalize_text(x)
    assert normalize_text(once) == once
