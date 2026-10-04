"""Cleaning strategies for bill data (Strategy pattern, plain callables)."""

from abc import ABC, abstractmethod

import pandas as pd


class CleaningStrategy(ABC):
    """Interface for dataframe cleaning strategies."""

    @abstractmethod
    def handle(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return a cleaned copy of df."""
        raise NotImplementedError


class DropMissingStrategy(CleaningStrategy):
    """Drop rows (axis=0) or columns (axis=1) containing missing values."""

    def __init__(self, axis: int = 0, thresh: int | None = None) -> None:
        self.axis = axis
        self.thresh = thresh

    def handle(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.thresh is None:
            return df.dropna(axis=self.axis).reset_index(drop=True)
        return df.dropna(axis=self.axis, thresh=self.thresh).reset_index(drop=True)


class FillMedianStrategy(CleaningStrategy):
    """Fill numeric NaNs with the column median, others with the mode."""

    def handle(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        num_cols = out.select_dtypes(include="number").columns
        if len(num_cols):
            out[num_cols] = out[num_cols].fillna(out[num_cols].median())
        for col in out.columns:
            if out[col].isna().any():
                mode = out[col].mode(dropna=True)
                if len(mode):
                    out[col] = out[col].fillna(mode.iloc[0])
        return out


class ZScoreOutlierStrategy(CleaningStrategy):
    """Drop rows whose numeric z-score exceeds the threshold on any column."""

    def __init__(self, threshold: float = 3.0, columns: list[str] | None = None) -> None:
        self.threshold = threshold
        self.columns = columns

    def handle(self, df: pd.DataFrame) -> pd.DataFrame:
        num = df.select_dtypes(include="number")
        if self.columns:
            keep = [c for c in self.columns if c in num.columns]
            num = num[keep]
        if num.empty or len(df) < 2:
            return df.copy()
        std = num.std(ddof=0).replace(0, float("nan"))
        z = ((num - num.mean()) / std).abs().fillna(0.0)
        mask = (z > self.threshold).any(axis=1)
        return df.loc[~mask].reset_index(drop=True)


class BillDataPipeline:
    """Context class that applies a swappable cleaning strategy."""

    def __init__(self, strategy: CleaningStrategy) -> None:
        self._strategy = strategy

    def set_strategy(self, strategy: CleaningStrategy) -> None:
        """Swap the active cleaning strategy."""
        self._strategy = strategy

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean df with the current strategy."""
        return self._strategy.handle(df)

    def handle(self, df: pd.DataFrame) -> pd.DataFrame:
        """Alias for run, mirroring the strategy interface."""
        return self.run(df)
