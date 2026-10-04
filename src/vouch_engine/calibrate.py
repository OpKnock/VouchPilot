"""Temperature calibration for 27-label confidence (002/US2).

Temperature approximation (documented): the scorer emits only the top-label
confidence ``conf`` (a 27-way max probability), not full logits. We model the
remaining ``1 - conf`` mass as uniform over the other 26 labels, i.e. each
other label has probability ``(1 - conf) / 26``. Under that model the
temperature-scaled confidence is::

    a = conf ** (1/T);  b = ((1 - conf) / 26) ** (1/T)
    apply_conf(conf, T) = a / (a + 26 * b)

which is exactly softmax with temperature T applied to logits
``log(conf)`` (predicted class) and ``log((1-conf)/26)`` (each other class).
T = 1 is the identity; T > 1 softens overconfident scores toward 1/27.

``fit_temperature`` minimises binary NLL over the same approximation:
for each item, ``p_true(T) = c(T)`` if correct else ``(1 - c(T)) / 26``
where ``c(T) = apply_conf(conf, T)``; NLL = ``-mean(log(p_true(T)))``.
The grid is 0.05..5.0 inclusive in steps of 0.05.

Stdlib only.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

_EPS = 1e-9
_GRID_MIN = 0.05
_GRID_MAX = 5.0
_GRID_STEP = 0.05


def _clip_conf(conf: float) -> float:
    try:
        c = float(conf)
    except (TypeError, ValueError):
        c = 0.5
    if math.isnan(c) or math.isinf(c):
        return 0.5
    return min(1.0 - _EPS, max(_EPS, c))


def apply_conf(conf: float, T: float) -> float:
    """Map a confidence through temperature T (T=1 is identity)."""
    try:
        t = float(T)
    except (TypeError, ValueError):
        t = 1.0
    if t <= 0 or math.isnan(t) or math.isinf(t):
        t = 1.0
    c = _clip_conf(conf)
    inv = 1.0 / t
    try:
        a = math.pow(c, inv)
        b = math.pow((1.0 - c) / 26.0, inv)
    except (ValueError, OverflowError):
        return c
    denom = a + 26.0 * b
    if denom <= 0:
        return c
    out = a / denom
    return min(1.0 - _EPS, max(_EPS, out))


def _nll(items: list[dict], T: float) -> float:
    total = 0.0
    n = 0
    for it in items or []:
        if not isinstance(it, dict):
            continue
        conf = it.get("conf", it.get("confidence", 0.5))
        correct = it.get("correct", False)
        ok = bool(correct) if not isinstance(correct, (int, float)) else bool(correct)
        c = apply_conf(conf, T)
        if ok:
            p = max(1e-12, c)
        else:
            p = max(1e-12, (1.0 - c) / 26.0)
        total += -math.log(p)
        n += 1
    return total / n if n else float("inf")


def fit_temperature(items: list[dict], grid=None) -> float:
    """Fit T over grid 0.05..5.0 minimising binary NLL (see module docstring)."""
    if grid is None:
        steps = int(round((_GRID_MAX - _GRID_MIN) / _GRID_STEP))
        grid = [round(_GRID_MIN + i * _GRID_STEP, 10) for i in range(steps + 1)]
    best_t = 1.0
    best_nll = float("inf")
    for t in grid:
        try:
            val = _nll(items or [], float(t))
        except (TypeError, ValueError):
            continue
        if val < best_nll - 1e-12:
            best_nll = val
            best_t = float(t)
        elif val == best_nll and float(t) < best_t:
            best_t = float(t)
    return float(best_t)


def ece(confs: list[float], corrects: list, bins: int = 10) -> float:
    """Expected calibration error with equally-spaced confidence bins."""
    confs = [float(c) for c in (confs or [])]
    corr = [
        1.0 if (bool(c) if not isinstance(c, (int, float)) else bool(c)) else 0.0
        for c in (corrects or [])
    ]
    n = min(len(confs), len(corr))
    if n == 0 or bins <= 0:
        return 0.0
    confs, corr = confs[:n], corr[:n]
    total = 0.0
    for b in range(int(bins)):
        lo = b / bins
        hi = (b + 1) / bins
        idx = [
            i for i, c in enumerate(confs) if (c >= lo and (c < hi or (b == bins - 1 and c <= 1.0)))
        ]
        if not idx:
            continue
        acc = sum(corr[i] for i in idx) / len(idx)
        avg_conf = sum(confs[i] for i in idx) / len(idx)
        total += (len(idx) / n) * abs(acc - avg_conf)
    return float(total)


def coverage_accuracy(confs: list[float], corrects: list, steps: int = 10) -> list[dict]:
    """Coverage-accuracy points by descending confidence.

    For i in 1..steps, take the top i/steps fraction (ceil) and report
    {coverage, accuracy}.
    """
    confs = [float(c) for c in (confs or [])]
    corr = [bool(c) if not isinstance(c, (int, float)) else bool(c) for c in (corrects or [])]
    n = min(len(confs), len(corr))
    if n == 0 or steps <= 0:
        return []
    order = sorted(range(n), key=lambda i: (-confs[i], i))
    ranked = [corr[i] for i in order]
    out: list[dict] = []
    for i in range(1, int(steps) + 1):
        k = max(1, int(math.ceil(n * i / steps)))
        k = min(n, k)
        acc = sum(1 for v in ranked[:k] if v) / k
        out.append({"coverage": k / n, "accuracy": float(acc)})
    return out


def save_calibrator(path: str, T: float, n: int, ece_before: float, ece_after: float) -> str:
    """Write calibrator JSON {T, n, ece_before, ece_after}; return path."""
    payload = {
        "T": float(T),
        "n": int(n),
        "ece_before": float(ece_before),
        "ece_after": float(ece_after),
    }
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        Path(parent).mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return str(path)


def load_calibrator(path: str) -> dict:
    """Load calibrator JSON; normalise keys to {T, n, ece_before, ece_after}."""
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        return {"T": 1.0, "n": 0, "ece_before": 0.0, "ece_after": 0.0}
    t = data.get("T", data.get("t", data.get("temperature", 1.0)))
    try:
        t = float(t)
    except (TypeError, ValueError):
        t = 1.0
    return {
        "T": t,
        "n": int(data.get("n", 0)),
        "ece_before": float(data.get("ece_before", data.get("ece", 0.0))),
        "ece_after": float(data.get("ece_after", data.get("ece", 0.0))),
    }


def save(path: str, calibrator: dict) -> str:
    """Alias: save a calibrator dict {T, n, ece_before, ece_after}."""
    cal = calibrator or {}
    return save_calibrator(
        path,
        cal.get("T", 1.0),
        cal.get("n", 0),
        cal.get("ece_before", 0.0),
        cal.get("ece_after", 0.0),
    )


def load(path: str) -> dict:
    """Alias for load_calibrator."""
    return load_calibrator(path)


__all__ = [
    "apply_conf",
    "coverage_accuracy",
    "ece",
    "fit_temperature",
    "load",
    "load_calibrator",
    "save",
    "save_calibrator",
]
