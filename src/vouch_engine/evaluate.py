"""Evaluation harness (Team-C, US2): sklearn metrics + JSON report."""

from __future__ import annotations

import json
from pathlib import Path

from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)

from .labels import LABEL_NAMES

REPORT_KEYS = (
    "accuracy",
    "macro_f1",
    "micro_f1",
    "weighted_f1",
    "per_class",
    "confusion_matrix",
    "baseline_delta",
    "latency",
    "n_rows",
    "seed",
)


def _p95(values: list) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, int(-(-95 * len(ordered) // 100)) - 1))
    return float(ordered[rank])


def compute_metrics(
    y_true: list,
    y_pred: list,
    labels: list | None = None,
    seed: int | None = None,
    latency_s: list | None = None,
    baseline_delta: dict | None = None,
) -> dict:
    """Compute the EvalReport dict for one prediction set.

    ``labels`` defaults to LABEL_NAMES (all 27 labels) so per-class rows and
    the confusion matrix always cover the full taxonomy with zero_division=0.
    """
    label_list = list(labels) if labels is not None else list(LABEL_NAMES)
    y_true = list(y_true)
    y_pred = list(y_pred)
    report = classification_report(
        y_true, y_pred, labels=label_list, output_dict=True, zero_division=0
    )
    per_class = [
        {
            "label": lab,
            "precision": float(report[lab]["precision"]),
            "recall": float(report[lab]["recall"]),
            "f1": float(report[lab]["f1-score"]),
            "support": int(report[lab]["support"]),
        }
        for lab in label_list
    ]
    matrix = confusion_matrix(y_true, y_pred, labels=label_list).tolist()
    lat = list(latency_s) if latency_s else []
    mean_s = float(sum(lat) / len(lat)) if lat else 0.0
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "micro_f1": float(f1_score(y_true, y_pred, average="micro", zero_division=0)),
        "weighted_f1": float(
            f1_score(y_true, y_pred, average="weighted", zero_division=0)
        ),
        "per_class": per_class,
        "confusion_matrix": {"labels": label_list, "matrix": matrix},
        "baseline_delta": baseline_delta,
        "latency": {"mean_s": mean_s, "p95_s": _p95(lat)},
        "n_rows": len(y_true),
        "seed": seed,
    }


def write_report(report: dict, path: str) -> str:
    """Write the EvalReport as indented JSON; return the path."""
    out = Path(path)
    if str(out.parent) and str(out.parent) != ".":
        out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return str(out)
