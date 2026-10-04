# Workspace settings store: JSON file with validated defaults. New file (web wiring).
# No new dependencies. Lives next to the backend so the exe build carries it along.

from __future__ import annotations

import json
import os

DEFAULTS = {
    'scorer': 'keyword',
    'endpoint': 'http://127.0.0.1:8080',
    'workers': 1,
    'challenger': True,
    'fraud': True,
    'auto_approve_threshold': 85,
    'export_format': 'xlsx',
    'include_evidence': True,
    'theme': 'light',
}

FILENAME = 'settings.json'


def _path(root: str | None = None) -> str:
    base = root or os.getcwd()
    return os.path.join(base, FILENAME)


def load(root: str | None = None) -> dict:
    merged = dict(DEFAULTS)
    try:
        with open(_path(root), encoding='utf-8') as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            for key in DEFAULTS:
                if key in data:
                    merged[key] = data[key]
    except (OSError, ValueError):
        pass
    return merged


def save(patch: dict, root: str | None = None) -> dict:
    merged = load(root)
    for key in DEFAULTS:
        if key in patch:
            merged[key] = patch[key]
    if merged['scorer'] not in ('stub', 'keyword', 'server', 'vouchpilot'):
        raise ValueError('unknown scorer')
    merged['workers'] = max(1, min(8, int(merged['workers'])))
    merged['auto_approve_threshold'] = max(60, min(99, int(merged['auto_approve_threshold'])))
    for key in ('challenger', 'fraud', 'include_evidence',):
        merged[key] = bool(merged[key])
    if merged['theme'] not in ('light', 'dark'):
        merged['theme'] = 'light'
    if merged['export_format'] not in ('xlsx', 'jsonl'):
        merged['export_format'] = 'xlsx'
    with open(_path(root), 'w', encoding='utf-8') as handle:
        json.dump(merged, handle, indent=1)
    return merged


__all__ = ['DEFAULTS', 'FILENAME', 'load', 'save']

