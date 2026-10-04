"""Unit tests for extensions.fraud_quish."""

from __future__ import annotations

from extensions.fraud_quish import LEGIT, is_lookalike, score_bill


def _row(narration: str, **extra) -> dict:
    row = {"narration": narration, "raw": {}, "refs": [], "pay": {}}
    row.update(extra)
    return row


def test_clean_bill_scores_zero() -> None:
    row = _row(
        "Payment received via UPI, thanks",
        raw={"voucher_no": "V-1024", "amount": "1500"},
        refs=["INV-88"],
        pay={"utr": "123456789012"},
    )
    assert score_bill(row) == (0, [])


def test_legit_url_scores_zero() -> None:
    row = _row("Paid via https://www.hdfcbank.com personal banking")
    score, flags = score_bill(row)
    assert score == 0
    assert flags == []


def test_typosquat_http_login_url_scores_high() -> None:
    row = _row("Verify at http://hdfcbaank-login.top/verify-account urgently")
    score, flags = score_bill(row)
    assert score >= 50
    assert flags and all(f.startswith("quish:") for f in flags)
    assert "quish:non-https-scheme" in flags
    assert any(f.startswith("quish:lookalike:") for f in flags)


def test_punycode_url_flagged() -> None:
    row = _row("Login http://xn--hdfcbaank-login.top/verify to confirm")
    score, flags = score_bill(row)
    assert score >= 50
    assert "quish:punycode" in flags


def test_is_lookalike_exact_legit_is_false() -> None:
    assert is_lookalike(LEGIT[0], LEGIT[0]) is False
    assert is_lookalike("hdfcbaank.com", "hdfcbank.com") is True
