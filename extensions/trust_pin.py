"""Integrity pins for offline drift checks (stdlib only)."""

import hashlib
import hmac
from datetime import datetime, timezone
from pathlib import Path


def pin_sha256(data: bytes) -> str:
    """Return the hex SHA-256 digest of data."""
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("data must be bytes")
    return hashlib.sha256(bytes(data)).hexdigest()


def pin_file(path) -> str:
    """Return the hex SHA-256 digest of a file's bytes."""
    return pin_sha256(Path(path).read_bytes())


def save_pin(pin_hex: str, path) -> None:
    """Persist a hex pin to path (normalised, trailing newline)."""
    Path(path).write_text(pin_hex.strip().lower() + "\n", encoding="utf-8")


def load_pin(path) -> str:
    """Load a hex pin previously stored with save_pin."""
    return Path(path).read_text(encoding="utf-8").strip().lower()


def verify_live_vs_pinned(live: bytes, pinned_hex: str) -> dict:
    """Compare live bytes against a pinned hex digest (constant-time)."""
    expected = pinned_hex.strip().lower()
    actual = pin_sha256(live)
    return {
        "match": bool(hmac.compare_digest(actual, expected)),
        "expected": expected,
        "actual": actual,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
