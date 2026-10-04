"""Prediction validation and output writers (JSONL / XLSX)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .schemas import Prediction

logger = logging.getLogger(__name__)


def validate_prediction(data: dict[str, Any] | Prediction) -> Prediction:
    """Validate one prediction record, raising on invalid input."""
    if isinstance(data, Prediction):
        return data
    return Prediction.model_validate(data)


def _coerce_record(item: Any) -> dict[str, Any]:
    if isinstance(item, Prediction):
        return item.model_dump()
    if isinstance(item, dict):
        return dict(item)
    raise TypeError(f"unsupported prediction record type: {type(item).__name__}")


def write_jsonl(records: list[Any], path: str | Path) -> dict[str, int]:
    """Write validated predictions as JSONL. Invalid rows are counted, logged, skipped."""
    p = Path(path)
    if p.parent and str(p.parent) not in ("", "."):
        p.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    invalid = 0
    with p.open("w", encoding="utf-8") as fh:
        for i, item in enumerate(records):
            try:
                pred = validate_prediction(_coerce_record(item))
            except Exception as exc:
                invalid += 1
                logger.warning("skipping invalid prediction at index %d: %s", i, exc)
                continue
            fh.write(pred.model_dump_json() + "\n")
            written += 1
    return {"written": written, "invalid": invalid}


def write_xlsx(records: list[Any], path: str | Path) -> dict[str, int]:
    """Write validated predictions as XLSX. Invalid rows are counted, logged, skipped."""
    from openpyxl import Workbook

    p = Path(path)
    if p.parent and str(p.parent) not in ("", "."):
        p.parent.mkdir(parents=True, exist_ok=True)
    valid: list[Prediction] = []
    invalid = 0
    for i, item in enumerate(records):
        try:
            valid.append(validate_prediction(_coerce_record(item)))
        except Exception as exc:
            invalid += 1
            logger.warning("skipping invalid prediction at index %d: %s", i, exc)
            continue
    wb = Workbook()
    ws = wb.active
    ws.title = "predictions"
    header = ["row_id", "invoice_number", "voucher_type", "confidence", "needs_review", "top_k", "evidence"]
    ws.append(header)
    for pred in valid:
        ws.append([
            pred.row_id,
            pred.invoice_number,
            pred.voucher_type,
            pred.confidence,
            pred.needs_review,
            json.dumps(pred.top_k),
            json.dumps(pred.evidence),
        ])
    wb.save(str(p))
    return {"written": len(valid), "invalid": invalid}
