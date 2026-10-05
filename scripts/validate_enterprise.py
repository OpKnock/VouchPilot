"""Enterprise validation gate for VouchPilot voucher classification.

This command measures quality on a hand-labelled or production dataset without
pretending a small benchmark is proof of production readiness.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from statistics import mean
from typing import Any

from vouch_engine.api import classify_raw_rows
from vouch_engine.labels import LABEL_NAMES


def _normalise_name(value: str) -> str:
    return "".join(ch for ch in str(value).strip().lower() if ch.isalnum())


def _find_label_column(fieldnames: list[str]) -> str:
    candidates = {"vouchertype", "label", "target", "groundtruth"}
    for field in fieldnames:
        if _normalise_name(field) in candidates:
            return field
    raise ValueError("gold dataset must contain a voucher_type/label column")


def _read_gold(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        if not fields:
            raise ValueError("gold dataset has no header")
        label_col = _find_label_column(fields)
        rows: list[dict[str, str]] = []
        labels: list[str] = []
        for row in reader:
            label = str(row.get(label_col, "") or "").strip()
            if not label:
                continue
            rows.append(dict(row))
            labels.append(label)
    return rows, labels


def _ece(confidence: list[float], correct: list[bool], bins: int = 10) -> float:
    if not confidence:
        return 0.0
    total = len(confidence)
    error = 0.0
    for index in range(bins):
        lo = index / bins
        hi = (index + 1) / bins
        members = [
            i
            for i, value in enumerate(confidence)
            if (lo <= value < hi) or (index == bins - 1 and value == hi)
        ]
        if not members:
            continue
        accuracy = sum(bool(correct[i]) for i in members) / len(members)
        avg_confidence = sum(confidence[i] for i in members) / len(members)
        error += (len(members) / total) * abs(avg_confidence - accuracy)
    return float(error)


def _safe_float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def validate(
    gold_path: str | Path,
    *,
    predictions_path: str | Path | None = None,
    dataset_type: str = "hand-verified",
    scorer: str = "keyword",
    endpoint: str = "http://127.0.0.1:8080",
    workers: int = 1,
    min_accuracy: float = 0.80,
    min_macro_f1: float = 0.70,
    max_review_rate: float = 0.60,
    max_high_confidence_error_rate: float = 0.05,
    min_support_per_class: int = 1,
) -> dict[str, Any]:
    gold_rows, labels = _read_gold(Path(gold_path))
    if not gold_rows:
        raise ValueError("gold dataset contains no labelled rows")

    if predictions_path:
        predictions = []
        with Path(predictions_path).open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    predictions.append(json.loads(line))
    else:
        predictions, invalid = classify_raw_rows(
            gold_rows,
            scorer,
            endpoint,
            workers,
        )
        if invalid:
            raise ValueError(f"classifier returned {invalid} invalid rows")

    if len(predictions) != len(labels):
        raise ValueError(
            f"prediction count {len(predictions)} does not match labelled row count {len(labels)}"
        )

    y_pred = [str(row.get("voucher_type", "")) for row in predictions]
    support = {label: labels.count(label) for label in LABEL_NAMES}
    predicted_counts = {label: y_pred.count(label) for label in LABEL_NAMES}
    correct = [actual == predicted for actual, predicted in zip(labels, y_pred)]
    confidence = [_safe_float(row.get("confidence")) for row in predictions]
    review = [bool(row.get("needs_review")) for row in predictions]
    high_confidence_errors = [
        not is_correct and conf >= 0.85
        for is_correct, conf in zip(correct, confidence)
    ]

    from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support

    precision, recall, f1, class_support = precision_recall_fscore_support(
        labels,
        y_pred,
        labels=list(LABEL_NAMES),
        zero_division=0,
    )
    accuracy = float(accuracy_score(labels, y_pred))
    macro_f1 = float(
        f1_score(labels, y_pred, labels=list(LABEL_NAMES), average="macro", zero_division=0)
    )
    per_class = []
    for label, p, r, f, s in zip(LABEL_NAMES, precision, recall, f1, class_support):
        per_class.append(
            {
                "label": label,
                "precision": float(p),
                "recall": float(r),
                "f1": float(f),
                "support": int(s),
            }
        )

    review_rate = mean(review)
    high_conf_error_rate = mean(high_confidence_errors)
    label_coverage = sum(value > 0 for value in support.values()) / len(LABEL_NAMES)
    unknown_predictions = sum(label not in LABEL_NAMES for label in y_pred)
    unknown_ground_truth = sorted(set(labels) - set(LABEL_NAMES))
    min_support = min(support.values()) if support else 0

    failures = []
    if accuracy < min_accuracy:
        failures.append(f"accuracy {accuracy:.4f} < {min_accuracy:.4f}")
    if macro_f1 < min_macro_f1:
        failures.append(f"macro_f1 {macro_f1:.4f} < {min_macro_f1:.4f}")
    if review_rate > max_review_rate:
        failures.append(f"review_rate {review_rate:.4f} > {max_review_rate:.4f}")
    if high_conf_error_rate > max_high_confidence_error_rate:
        failures.append(
            f"high_confidence_error_rate {high_conf_error_rate:.4f} > "
            f"{max_high_confidence_error_rate:.4f}"
        )
    if unknown_predictions:
        failures.append(f"{unknown_predictions} predictions use unknown labels")
    if unknown_ground_truth:
        failures.append(f"gold data contains unknown labels: {unknown_ground_truth}")
    if min_support < min_support_per_class:
        failures.append(
            f"minimum class support {min_support} < required {min_support_per_class}"
        )

    enterprise_ready = (
        dataset_type == "production"
        and label_coverage == 1.0
        and not failures
    )

    return {
        "dataset": {
            "path": str(gold_path),
            "type": dataset_type,
            "rows": len(labels),
            "label_coverage": label_coverage,
            "minimum_class_support": min_support,
            "class_support": support,
        },
        "metrics": {
            "accuracy": accuracy,
            "macro_f1": macro_f1,
            "review_rate": float(review_rate),
            "high_confidence_error_rate": float(high_conf_error_rate),
            "expected_calibration_error": _ece(confidence, correct),
            "mean_confidence": float(mean(confidence)),
            "correct_rows": int(sum(correct)),
            "incorrect_rows": int(len(correct) - sum(correct)),
            "unknown_predictions": unknown_predictions,
            "unknown_ground_truth": unknown_ground_truth,
        },
        "per_class": per_class,
        "predicted_counts": predicted_counts,
        "gate": {
            "pass": not failures,
            "enterprise_ready": enterprise_ready,
            "failures": failures,
            "thresholds": {
                "min_accuracy": min_accuracy,
                "min_macro_f1": min_macro_f1,
                "max_review_rate": max_review_rate,
                "max_high_confidence_error_rate": max_high_confidence_error_rate,
                "min_support_per_class": min_support_per_class,
            },
        },
        "interpretation": (
            "This report is pre-production evidence until the dataset is independently "
            "labelled from representative enterprise data. Synthetic or hand-verified "
            "benchmarks do not establish audit, tax, or regulatory compliance."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run VouchPilot enterprise classification validation."
    )
    parser.add_argument("--gold", required=True, help="CSV with voucher_type/label ground truth")
    parser.add_argument("--predictions", help="Optional JSONL predictions")
    parser.add_argument("--output", default="artifacts/enterprise_validation.json")
    parser.add_argument(
        "--dataset-type",
        choices=("synthetic", "hand-verified", "production"),
        default="hand-verified",
    )
    parser.add_argument(
        "--scorer",
        choices=("keyword", "vouchpilot", "server", "stub"),
        default="keyword",
    )
    parser.add_argument("--endpoint", default="http://127.0.0.1:8080")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--min-accuracy", type=float, default=0.80)
    parser.add_argument("--min-macro-f1", type=float, default=0.70)
    parser.add_argument("--max-review-rate", type=float, default=0.60)
    parser.add_argument("--max-high-confidence-error-rate", type=float, default=0.05)
    parser.add_argument("--min-support-per-class", type=int, default=1)
    parser.add_argument("--allow-gate-failure", action="store_true")
    args = parser.parse_args()

    report = validate(
        args.gold,
        predictions_path=args.predictions,
        dataset_type=args.dataset_type,
        scorer=args.scorer,
        endpoint=args.endpoint,
        workers=args.workers,
        min_accuracy=args.min_accuracy,
        min_macro_f1=args.min_macro_f1,
        max_review_rate=args.max_review_rate,
        max_high_confidence_error_rate=args.max_high_confidence_error_rate,
        min_support_per_class=args.min_support_per_class,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\\n", encoding="utf-8")

    metrics = report["metrics"]
    gate = report["gate"]
    print(f"Rows: {report['dataset']['rows']}")
    print(f"Accuracy: {metrics['accuracy']:.4f}")
    print(f"Macro-F1: {metrics['macro_f1']:.4f}")
    print(f"Review rate: {metrics['review_rate']:.4f}")
    print(f"High-confidence error rate: {metrics['high_confidence_error_rate']:.4f}")
    print(f"ECE: {metrics['expected_calibration_error']:.4f}")
    print(f"Gate: {'PASS' if gate['pass'] else 'FAIL'}")
    print(f"Enterprise-ready: {'YES' if gate['enterprise_ready'] else 'NO'}")
    for failure in gate["failures"]:
        print(f"FAIL: {failure}")
    return 0 if gate["pass"] or args.allow_gate_failure else 1


if __name__ == "__main__":
    raise SystemExit(main())
