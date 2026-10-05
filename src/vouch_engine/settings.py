"""Workspace settings store with validated defaults."""

from __future__ import annotations

import json
import os

DEFAULTS = {
    "scorer": "keyword",
    "endpoint": "http://127.0.0.1:8080",
    "workers": 1,
    "challenger": True,
    "fraud": True,
    "auto_approve_threshold": 85,
    "export_format": "jsonl",
    "include_evidence": True,
    "theme": "light",
}

FILENAME = "settings.json"
_ALLOWED_SCORERS = {"stub", "keyword", "server", "vouchpilot"}
_ALLOWED_EXPORTS = {"xlsx", "jsonl", "csv"}
_ALLOWED_THEMES = {"light", "dark"}


def _path(root: str | None = None) -> str:
    return os.path.join(root or os.getcwd(), FILENAME)


def load(root: str | None = None) -> dict:
    merged = dict(DEFAULTS)
    try:
        with open(_path(root), encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            for key in DEFAULTS:
                if key in data:
                    merged[key] = data[key]
    except (OSError, ValueError, TypeError):
        pass
    if merged.get("scorer") not in _ALLOWED_SCORERS:
        merged["scorer"] = DEFAULTS["scorer"]
    return _validate(merged)


def _validate(values: dict) -> dict:
    result = dict(DEFAULTS)
    result.update({key: values[key] for key in DEFAULTS if key in values})

    if result["scorer"] not in _ALLOWED_SCORERS:
        raise ValueError("unknown scorer")

    try:
        result["workers"] = max(1, min(8, int(result["workers"])))
    except (TypeError, ValueError):
        result["workers"] = DEFAULTS["workers"]

    try:
        result["auto_approve_threshold"] = max(
            60, min(99, int(result["auto_approve_threshold"]))
        )
    except (TypeError, ValueError):
        result["auto_approve_threshold"] = DEFAULTS["auto_approve_threshold"]

    result["challenger"] = bool(result["challenger"])
    result["fraud"] = bool(result["fraud"])
    result["include_evidence"] = bool(result["include_evidence"])

    if result["theme"] not in _ALLOWED_THEMES:
        result["theme"] = DEFAULTS["theme"]
    if result["export_format"] not in _ALLOWED_EXPORTS:
        result["export_format"] = DEFAULTS["export_format"]
    return result


def save(patch: dict, root: str | None = None) -> dict:
    if not isinstance(patch, dict):
        raise TypeError("settings patch must be an object")
    merged = load(root)
    merged.update({key: patch[key] for key in DEFAULTS if key in patch})
    merged = _validate(merged)

    target = _path(root)
    os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(merged, handle, indent=1)
    return merged


__all__ = ["DEFAULTS", "FILENAME", "load", "save"]
