"""Unit tests for temperature calibration (002/US2). No network."""

import json

from vouch_engine.calibrate import (
    apply_conf,
    coverage_accuracy,
    ece,
    fit_temperature,
    load_calibrator,
    save_calibrator,
)


def _overconfident_items():
    # 20 rows at conf 0.9 but only half correct -> overconfident.
    items = []
    for i in range(20):
        items.append({"conf": 0.9, "correct": (i % 2 == 0)})
    return items


def test_ece_decreases_after_calibration():
    items = _overconfident_items()
    confs = [it["conf"] for it in items]
    corrects = [it["correct"] for it in items]
    before = ece(confs, corrects)
    assert before > 0.2  # 0.9 mean conf vs 0.5 accuracy.
    t = fit_temperature(items)
    assert 0.05 <= t <= 5.0
    assert t > 1.0  # overconfidence needs softening.
    after = ece([apply_conf(c, t) for c in confs], corrects)
    assert after < before


def test_apply_conf_identity_at_one():
    assert abs(apply_conf(0.83, 1.0) - 0.83) < 1e-9
    assert 0.0 < apply_conf(0.9, 2.0) < 0.9
    assert 0.9 < apply_conf(0.9, 0.5) <= 1.0


def test_coverage_accuracy_shape_sorted():
    confs = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.05]
    corrects = [True, True, True, False, True, False, False, False, True, False]
    pts = coverage_accuracy(confs, corrects, steps=5)
    assert len(pts) == 5
    assert pts[-1]["coverage"] == 1.0
    covs = [p["coverage"] for p in pts]
    assert covs == sorted(covs)
    for p in pts:
        assert 0.0 <= p["accuracy"] <= 1.0
        assert set(p) == {"coverage", "accuracy"}


def test_save_load_roundtrip(tmp_path):
    path = str(tmp_path / "cal.json")
    save_calibrator(path, 2.5, 20, 0.4, 0.1)
    loaded = load_calibrator(path)
    assert loaded["T"] == 2.5
    assert loaded["n"] == 20
    assert loaded["ece_before"] == 0.4
    assert loaded["ece_after"] == 0.1
    raw = json.loads(open(path, encoding="utf-8").read())
    assert set(raw) == {"T", "n", "ece_before", "ece_after"}
