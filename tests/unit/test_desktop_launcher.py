"""Desktop launcher startup-contract tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path


_MODULE_PATH = Path(__file__).resolve().parents[2] / "desktop" / "launcher.py"
_SPEC = importlib.util.spec_from_file_location("vouchpilot_desktop_launcher", _MODULE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"cannot load desktop launcher from {_MODULE_PATH}")
launcher = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(launcher)


def test_wait_for_healthy_returns_false_after_all_attempts(monkeypatch):
    monkeypatch.setattr(launcher.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(launcher, "healthy", lambda _url, timeout=3: False)
    assert launcher.wait_for_healthy("http://127.0.0.1:8000/health", attempts=3, delay=0) is False


def test_wait_for_healthy_returns_true_when_service_recovers(monkeypatch):
    outcomes = iter([False, True])
    monkeypatch.setattr(launcher.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(launcher, "healthy", lambda _url, timeout=3: next(outcomes))
    assert launcher.wait_for_healthy("http://127.0.0.1:8000/health", attempts=3, delay=0) is True
