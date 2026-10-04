"""Bill reconciliation pipeline (Strategy + Factory patterns, plain callables)."""

from .factory import CSVIngestorFactory
from .pipeline import FEATURE_COLS, TARGET_COL, load_config, run_pipeline
from .strategies import (
    BillDataPipeline,
    CleaningStrategy,
    DropMissingStrategy,
    FillMedianStrategy,
    ZScoreOutlierStrategy,
)

__all__ = [
    "BillDataPipeline",
    "CSVIngestorFactory",
    "CleaningStrategy",
    "DropMissingStrategy",
    "FEATURE_COLS",
    "FillMedianStrategy",
    "TARGET_COL",
    "ZScoreOutlierStrategy",
    "load_config",
    "run_pipeline",
]
