"""Evidence-tag retrieval grounding (002/US1).

Class-balanced k-NN over evidence-tag Jaccard similarity. Stdlib only.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def _label_order() -> dict[str, int]:
    from .labels import LABELS

    return {lb["name"]: i for i, lb in enumerate(LABELS)}


def _tags_set(tags) -> set[str]:
    if not tags:
        return set()
    return {str(t) for t in tags}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def build_index(exemplars: list[dict]) -> dict:
    """Build a retrieval index from exemplars.

    Args:
        exemplars: list of {tags, label, row_id} (extra keys preserved).

    Returns:
        Index dict {"exemplars": [...]} with normalised entries.
    """
    normed: list[dict] = []
    for ex in exemplars or []:
        if not isinstance(ex, dict):
            continue
        normed.append(
            {
                "tags": [str(t) for t in (ex.get("tags") or [])],
                "label": str(ex.get("label", "")),
                "row_id": ex.get("row_id"),
                **{k: v for k, v in ex.items() if k not in ("tags", "label", "row_id")},
            }
        )
    return {"exemplars": normed}


def retrieve(
    index: dict,
    tags: list[str],
    k: int = 5,
    per_class_cap: int = 2,
    exclude_row_id=None,
) -> list[dict]:
    """Retrieve up to k exemplars by evidence-tag Jaccard (desc).

    Deterministic tiebreak: label order (LABELS order) then row_id.
    At most per_class_cap exemplars per label. Leave-one-out is done via
    exclude_row_id (the query row's own exemplar is skipped).
    """
    order = _label_order()
    query = _tags_set(tags)
    cands = (index or {}).get("exemplars", []) if isinstance(index, dict) else []
    scored: list[tuple[float, int, object, dict]] = []
    for ex in cands:
        if not isinstance(ex, dict):
            continue
        if exclude_row_id is not None and ex.get("row_id") == exclude_row_id:
            continue
        score = _jaccard(query, _tags_set(ex.get("tags") or []))
        label = str(ex.get("label", ""))
        rank = order.get(label, 9999)
        rid = ex.get("row_id")
        try:
            rid_key: object = int(rid)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            rid_key = str(rid)
        scored.append((-score, rank, rid_key, ex))
    scored.sort(key=lambda t: (t[0], t[1], str(t[2])))
    out: list[dict] = []
    per_label: dict[str, int] = {}
    for neg, _rank, _rid, ex in scored:
        if len(out) >= max(0, int(k)):
            break
        label = str(ex.get("label", ""))
        if per_label.get(label, 0) >= max(0, int(per_class_cap)):
            continue
        per_label[label] = per_label.get(label, 0) + 1
        out.append(ex)
    return out


def exemplars_from_gold(gold_xlsx: str, labels_json: str, out_prefix: str) -> dict:
    """Run the real pipeline over a gold sheet and write exemplars.

    Runs ingest -> normalise -> perspective -> evidence (imports are inside
    this function so module import stays light). Writes
    ``{out_prefix}_exemplars.json`` holding the index dict and returns it.
    """
    from . import evidence as _evidence
    from . import ingest as _ingest
    from . import normalise as _normalise
    from . import perspective as _perspective

    data = _ingest.read_excel(gold_xlsx)
    headers = list(data.get("headers", []))
    raw_rows = list(data.get("rows", []))
    mapping = _normalise.map_columns(headers, raw_rows)
    canonical = _normalise.to_canonical(raw_rows, mapping)
    _perspective.resolve(canonical)

    with open(labels_json, encoding="utf-8") as handle:
        gold = json.load(handle)
    if isinstance(gold, dict):
        gold = gold.get("labels", gold.get("rows", []))
    by_id: dict[int, str] = {}
    for entry in gold or []:
        if not isinstance(entry, dict):
            continue
        rid = entry.get("row_id")
        label = entry.get("voucher_type", entry.get("label"))
        if rid is not None and label:
            try:
                by_id[int(rid)] = str(label)
            except (TypeError, ValueError):
                continue

    exemplars: list[dict] = []
    for pos, crow in enumerate(canonical, start=1):
        rid = crow.get("row_id", pos)
        try:
            rid_int = int(rid)
        except (TypeError, ValueError):
            rid_int = pos
        tags, _mask = _evidence.extract(crow)
        label = by_id.get(rid_int)
        if label is None and pos - 1 < len(gold or []):
            g = (gold or [])[pos - 1]
            if isinstance(g, dict):
                label = g.get("voucher_type", g.get("label"))
        if not label:
            continue
        exemplars.append({"tags": tags, "label": str(label), "row_id": rid_int})

    index = build_index(exemplars)
    out_path = f"{out_prefix}_exemplars.json"
    parent = os.path.dirname(os.path.abspath(out_path))
    if parent:
        Path(parent).mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(index, handle, indent=2)
    return index


__all__ = ["build_index", "retrieve", "exemplars_from_gold"]
