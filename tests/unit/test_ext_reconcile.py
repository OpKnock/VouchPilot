"""Tests for extensions/reconcile_zenml (relative paths only, no absolute paths)."""

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from extensions.reconcile_zenml.factory import CSVIngestorFactory  # noqa: E402
from extensions.reconcile_zenml.pipeline import load_config, run_pipeline  # noqa: E402
from extensions.reconcile_zenml.strategies import (  # noqa: E402
    BillDataPipeline,
    FillMedianStrategy,
)


def test_factory_csv(tmp_path):
    df = pd.DataFrame({"taxable": [100.0, 200.0], "total": [118.0, 236.0]})
    p = tmp_path / "bills.csv"
    df.to_csv(p, index=False)
    got = CSVIngestorFactory.get(p)
    assert len(got) == 2
    assert list(got.columns) == ["taxable", "total"]


def test_factory_xlsx(tmp_path):
    pytest.importorskip("openpyxl")
    df = pd.DataFrame({"taxable": [100.0, 200.0], "total": [118.0, 236.0]})
    p = tmp_path / "bills.xlsx"
    df.to_excel(p, index=False)
    got = CSVIngestorFactory.get(str(p))
    assert len(got) == 2
    assert list(got.columns) == ["taxable", "total"]


def test_factory_unsupported_suffix(tmp_path):
    with pytest.raises(ValueError):
        CSVIngestorFactory.get(tmp_path / "bills.txt")


def test_fill_median_strategy():
    df = pd.DataFrame({"taxable": [100.0, None, 300.0], "cgst": [9.0, 18.0, None]})
    out = BillDataPipeline(FillMedianStrategy()).run(df)
    assert not out.isna().any().any()
    assert out.loc[1, "taxable"] == pytest.approx(200.0)
    assert out.loc[2, "cgst"] == pytest.approx(13.5)


def test_pipeline_on_synthetic_csv(tmp_path):
    df = pd.DataFrame(
        {
            "taxable": [100.0, 200.0, 150.0, 300.0, 250.0, 120.0,
                        180.0, 220.0, 90.0, 260.0, 140.0, 210.0],
            "cgst": [9.0, 18.0, None, 27.0, 22.5, 10.8,
                     16.2, 19.8, 8.1, 23.4, 12.6, 18.9],
            "sgst": [9.0, 18.0, 13.5, 27.0, 22.5, 10.8,
                     16.2, 19.8, 8.1, 23.4, 12.6, 18.9],
            "igst": [0.0] * 12,
        }
    )
    df["total"] = df["taxable"] + df["cgst"].fillna(df["cgst"].median()) + df["sgst"]
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    csv_path = tmp_path / "synthetic_bills.csv"
    df.to_csv(csv_path, index=False)
    config = {"model": "linear_regression", "data_path": str(csv_path)}
    metrics = run_pipeline(config, ["dedup", "fill_median", "outliers", "train"])
    assert metrics["n_rows"] == len(df)
    assert metrics["n_deduped"] == 1
    assert metrics["missing_filled"] == 1
    assert metrics["model"] == "linear_regression"
    assert metrics["mse_or_accuracy"] >= 0.0


def test_load_config_from_package():
    cfg = load_config(ROOT / "extensions" / "reconcile_zenml" / "config.yaml")
    assert cfg["model"] == "linear_regression"
    assert cfg["enable_cache"] is False
    assert isinstance(cfg["steps"], list) and len(cfg["steps"]) >= 1
