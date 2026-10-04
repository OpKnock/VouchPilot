"""File ingestor factory for bill data (Factory pattern, no fixed paths)."""

from pathlib import Path

import pandas as pd


class CSVIngestorFactory:
    """Load a dataframe from a caller-supplied CSV or Excel file path."""

    SUPPORTED = {".csv", ".xlsx", ".xls"}

    @staticmethod
    def get(path: str | Path) -> pd.DataFrame:
        """Read path into a DataFrame; supports .csv / .xlsx / .xls."""
        suffix = Path(path).suffix.lower()
        if suffix == ".csv":
            return pd.read_csv(path)
        if suffix in (".xlsx", ".xls"):
            return pd.read_excel(path)
        raise ValueError(
            f"Unsupported file type '{suffix}'; expected {sorted(CSVIngestorFactory.SUPPORTED)}"
        )
