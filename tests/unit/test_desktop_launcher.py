"""Desktop launcher startup-contract tests."""

from __future__ import annotations

from desktop import launcher


def test_wait_for_healthy_returns_false_after_all_attempts(monkeypatch):
    monkeypatch.setattr(launcher.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(launcher, "healthy", lambda _url, timeout=3: False)
    assert launcher.wait_for_healthy("http://127.0.0.1:8000/health", attempts=3, delay=0) is False


def test_wait_for_healthy_returns_true_when_service_recovers(monkeypatch):
    outcomes = iter([False, True])
    monkeypatch.setattr(launcher.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(launcher, "healthy", lambda _url, timeout=3: next(outcomes))
    assert launcher.wait_for_healthy("http://127.0.0.1:8000/health", attempts=3, delay=0) is True
