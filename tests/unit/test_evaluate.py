"""Unit tests for the sklearn evaluation harness (Team-C, US2)."""

import json

from vouch_engine import evaluate
from vouch_engine.evaluate import compute_metrics, write_report
from vouch_engine.labels import LABEL_NAMES


def test_perfect_predictions():
    y = ["Purchase", "Sales", "Payment", "Receipt", "Expense", "Contra"]
    report = compute_metrics(y, list(y))
    assert report["accuracy"] == 1.0
    assert report["macro_f1"] == 1.0
    assert report["micro_f1"] == 1.0
    assert report["weighted_f1"] == 1.0
    assert report["n_rows"] == 6
    assert len(report["per_class"]) == len(LABEL_NAMES)
    for entry in report["per_class"]:
        if entry["support"] > 0:
            assert entry["precision"] == 1.0
            assert entry["recall"] == 1.0
            assert entry["f1"] == 1.0


def test_known_imperfect_case_sane():
    y_true = ["Purchase", "Sales", "Payment", "Receipt"]
    y_pred = ["Purchase", "Payment", "Payment", "Receipt"]
    report = compute_metrics(y_true, y_pred)
    assert report["accuracy"] == 0.75
    assert 0.0 < report["macro_f1"] < 1.0
    assert 0.0 < report["micro_f1"] <= 1.0
    assert 0.0 < report["weighted_f1"] <= 1.0
    assert report["n_rows"] == 4
    labels = report["confusion_matrix"]["labels"]
    matrix = report["confusion_matrix"]["matrix"]
    assert labels == LABEL_NAMES
    assert len(matrix) == len(LABEL_NAMES)
    assert all(len(row) == len(LABEL_NAMES) for row in matrix)
    assert sum(sum(row) for row in matrix) == 4
    assert set(report) == set(evaluate.REPORT_KEYS)
    assert report["latency"] == {"mean_s": 0.0, "p95_s": 0.0}


def test_write_report_round_trip(tmp_path):
    report = compute_metrics(["Purchase", "Sales"], ["Purchase", "Receipt"], seed=7,
                             latency_s=[0.1, 0.3])
    path = str(tmp_path / "eval.json")
    assert write_report(report, path) == path
    loaded = json.loads(open(path, encoding="utf-8").read())
    assert loaded == report
    assert loaded["seed"] == 7
    assert loaded["latency"]["mean_s"] > 0
