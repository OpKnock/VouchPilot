"""Tests for extensions/trust_pin.py (roundtrip + tamper detection)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from extensions import trust_pin  # noqa: E402


def test_pin_roundtrip(tmp_path):
    data = b"voucher-2026-0001|total=118.0"
    pin = trust_pin.pin_sha256(data)
    assert len(pin) == 64
    pin_path = tmp_path / "bill.pin"
    trust_pin.save_pin(pin, pin_path)
    assert trust_pin.load_pin(pin_path) == pin
    data_path = tmp_path / "bill.bin"
    data_path.write_bytes(data)
    assert trust_pin.pin_file(data_path) == pin


def test_verify_match():
    live = b"voucher-2026-0001|total=118.0"
    pinned = trust_pin.pin_sha256(live)
    event = trust_pin.verify_live_vs_pinned(live, pinned)
    assert event["match"] is True
    assert event["expected"] == pinned
    assert event["actual"] == pinned
    assert "checked_at" in event


def test_verify_tampered_mismatch():
    pinned = trust_pin.pin_sha256(b"voucher-2026-0001|total=118.0")
    event = trust_pin.verify_live_vs_pinned(b"voucher-2026-0001|total=999.0", pinned)
    assert event["match"] is False
    assert event["expected"] == pinned
    assert event["actual"] != pinned
    assert event["expected"] and event["actual"]
