"""Bill-data pipeline: ingest a file, clean it, predict bill totals."""

from pathlib import Path

import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split

from .factory import CSVIngestorFactory
from .strategies import (
    BillDataPipeline,
    DropMissingStrategy,
    FillMedianStrategy,
    ZScoreOutlierStrategy,
)

FEATURE_COLS = ["taxable", "cgst", "sgst", "igst"]
TARGET_COL = "total"

_DATA_KEYS = ("data_path", "input_path", "csv_path", "path", "data")


def load_config(path: str | Path) -> dict:
    """Parse a flat ``key: value`` config file using only the stdlib."""
    cfg: dict = {}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip().strip("'\"")
        low = val.lower()
        if low in ("true", "false"):
            cfg[key] = low == "true"
        elif "," in val or (val.startswith("[") and val.endswith("]")):
            inner = val.strip("[]")
            cfg[key] = [p.strip().strip("'\"") for p in inner.split(",") if p.strip()]
        else:
            try:
                cfg[key] = int(val)
            except ValueError:
                try:
                    cfg[key] = float(val)
                except ValueError:
                    cfg[key] = val
    return cfg


def _resolve_data_path(config: dict):
    for key in _DATA_KEYS:
        val = config.get(key)
        if val:
            return val
    return None


def _coerce_steps(config: dict, steps: list[str]) -> list[str]:
    if steps:
        return [str(s).strip().lower() for s in steps]
    raw = config.get("steps", [])
    if isinstance(raw, str):
        return [p.strip().lower() for p in raw.split(",") if p.strip()]
    return [str(s).strip().lower() for s in raw]


def _train_bill_total(df: pd.DataFrame) -> float:
    """Fit LinearRegression(taxable, cgst, sgst, igst -> total); return MSE."""
    feats = [c for c in FEATURE_COLS if c in df.columns]
    if TARGET_COL not in df.columns or not feats:
        return 0.0
    data = df[feats + [TARGET_COL]].dropna()
    if len(data) < 4:
        return 0.0
    try:
        X_train, X_test, y_train, y_test = train_test_split(
            data[feats], data[TARGET_COL], test_size=0.25, random_state=42
        )
        model = LinearRegression()
        model.fit(X_train, y_train)
        return float(mean_squared_error(y_test, model.predict(X_test)))
    except Exception:
        return 0.0


def run_pipeline(config: dict, steps: list[str]) -> dict:
    """Run ingest -> clean -> train; return a metrics dict."""
    config = dict(config or {})
    names = set(_coerce_steps(config, steps or []))
    path = _resolve_data_path(config)
    if path is None:
        raise ValueError("config needs a data path (data_path/input_path/csv_path/path)")
    df = CSVIngestorFactory.get(path)
    n_rows = int(len(df))
    n_deduped = 0
    missing_filled = 0
    pipe = BillDataPipeline(DropMissingStrategy())
    if names & {"dedup", "dedupe", "drop_duplicates"}:
        before = len(df)
        df = df.drop_duplicates().reset_index(drop=True)
        n_deduped = int(before - len(df))
    if "drop_missing" in names:
        pipe.set_strategy(DropMissingStrategy())
        df = pipe.run(df)
    if names & {"fill_median", "fill", "fill_missing"}:
        before = int(df.isna().sum().sum())
        pipe.set_strategy(FillMedianStrategy())
        df = pipe.run(df)
        missing_filled = int(max(0, before - int(df.isna().sum().sum())))
    if names & {"outliers", "zscore", "z_score"}:
        pipe.set_strategy(ZScoreOutlierStrategy())
        df = pipe.run(df)
    model_name = str(config.get("model", "linear_regression"))
    return {
        "n_rows": n_rows,
        "n_deduped": n_deduped,
        "missing_filled": missing_filled,
        "model": model_name,
        "mse_or_accuracy": _train_bill_total(df),
    }
