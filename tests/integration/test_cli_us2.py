"""CLI integration test (Team-C, US2): gold -> run(stub) -> evaluate.

The stub scorer is not expected to match gold labels, so this asserts report
shape (all keys, n_rows), metric reproducibility (evaluate twice identical),
and gold seed reproducibility (labels json + parsed xlsx rows identical).
"""

import json
import os
import subprocess
import sys

from openpyxl import load_workbook

from vouch_engine.evaluate import REPORT_KEYS
from vouch_engine.gold import build_dataset

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "src")


def _run_cli(*cli_args):
    env = dict(os.environ)
    env["PYTHONPATH"] = SRC + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "vouch_engine", *cli_args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )


def _read_sheet_rows(xlsx_path):
    workbook = load_workbook(xlsx_path, read_only=True, data_only=True)
    sheet = workbook.active
    return [[c.value for c in row] for row in sheet.iter_rows()]


def test_cli_gold_run_evaluate_reproducible(tmp_path):
    prefix = str(tmp_path / "gold")
    build_dataset(60, 1, prefix)
    xlsx = prefix + ".xlsx"
    labels_json = prefix + "_labels.json"
    pred = str(tmp_path / "predictions.jsonl")

    run = _run_cli("run", "--input", xlsx, "--out", pred, "--scorer", "stub")
    assert run.returncode == 0, run.stderr
    assert "n_rows=60" in run.stdout
    with open(pred, encoding="utf-8") as handle:
        lines = [line for line in handle if line.strip()]
    assert len(lines) == 60

    rep1 = str(tmp_path / "eval1.json")
    rep2 = str(tmp_path / "eval2.json")
    eval1 = _run_cli("evaluate", "--gold", labels_json, "--pred", pred,
                     "--report", rep1)
    assert eval1.returncode == 0, eval1.stderr
    eval2 = _run_cli("evaluate", "--gold", labels_json, "--pred", pred,
                     "--report", rep2)
    assert eval2.returncode == 0, eval2.stderr

    report1 = json.loads(open(rep1, encoding="utf-8").read())
    report2 = json.loads(open(rep2, encoding="utf-8").read())
    assert set(report1) == set(REPORT_KEYS)
    assert report1["n_rows"] == 60
    assert report1 == report2, "metrics must reproduce exactly"


def test_gold_seed_reproducibility_files(tmp_path):
    first = str(tmp_path / "a" / "gold")
    second = str(tmp_path / "b" / "gold")
    build_dataset(60, 1, first)
    build_dataset(60, 1, second)
    labels1 = json.loads(open(first + "_labels.json", encoding="utf-8").read())
    labels2 = json.loads(open(second + "_labels.json", encoding="utf-8").read())
    assert labels1 == labels2
    # xlsx bytes may differ by embedded timestamp: compare parsed rows instead.
    assert _read_sheet_rows(first + ".xlsx") == _read_sheet_rows(second + ".xlsx")
