"""Unit tests for extensions.rag_evidence. No network."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from extensions.rag_evidence import (  # noqa: E402
    chunk_text,
    retrieve_exemplars,
    row_text,
)


def _words(n: int, prefix: str = "w") -> str:
    return " ".join(f"{prefix}{i}" for i in range(n))


def _base_row(**over: object) -> dict:
    row: dict = {
        "seller": {"name": "Sharma Traders", "gstin": None},
        "buyer": {"name": "Nagpur Agro", "gstin": None},
        "doc": {"invoice_number": "SI/001", "date": "2026-03-31"},
        "items": [{"desc": "Office chairs", "qty": 10.0, "rate": 5000.0,
                   "amount": 50000.0}],
        "money": {"taxable": 50000.0, "total": 59000.0, "currency": "INR"},
        "pay": {"mode": None, "utr": None},
        "people": {},
        "refs": {},
        "narration": "",
        "raw": {},
    }
    row.update(over)
    return row


def test_chunk_overlap_math() -> None:
    chunks = chunk_text(_words(600), size=100, overlap_pct=20)
    assert len(chunks) == 8
    first = chunks[0].split()
    second = chunks[1].split()
    assert len(first) == 100
    assert len(second) == 100
    assert first[-20:] == second[:20]
    assert chunks[-1].split() == _words(600).split()[560:]


def test_chunk_empty() -> None:
    assert chunk_text("") == []
    assert chunk_text("   ") == []
    assert chunk_text("", size=10, overlap_pct=50) == []


def test_row_text_joins_fields() -> None:
    text = row_text(_base_row(narration="goods received in good condition"))
    assert "goods received in good condition" in text
    assert "Office chairs" in text
    assert "Sharma Traders" in text
    assert "Nagpur Agro" in text
    assert "SI/001" in text
    assert row_text({}) == ""


def test_ranking_prefers_nearer_text() -> None:
    query = _base_row(narration="office chairs purchase for nagpur branch")
    exemplars = [
        {"label": "Far", "text": "salary payroll employee wages deductions"},
        {"label": "Near", "text": "office chairs purchase nagpur branch furniture"},
    ]
    out = retrieve_exemplars(query, k=5, exemplars=exemplars)
    assert [hit["label"] for hit in out] == ["Near", "Far"]
    assert out[0]["score"] >= out[1]["score"]


def test_tags_exemplars_supported() -> None:
    query = _base_row(narration="office chairs purchase")
    exemplars = [{"label": "Purchase", "tags": ["office", "chairs", "furniture"],
                  "row_id": 1}]
    out = retrieve_exemplars(query, k=5, exemplars=exemplars)
    assert len(out) == 1
    assert out[0]["label"] == "Purchase"
    assert set(out[0]) == {"label", "score", "text"}


def test_empty_query_returns_empty() -> None:
    exemplars = [{"label": "X", "text": "office chairs purchase"}]
    assert retrieve_exemplars({}, k=5, exemplars=exemplars) == []
    assert retrieve_exemplars({"narration": "   "}, k=5, exemplars=exemplars) == []
    assert retrieve_exemplars({"narration": "chairs"}, k=5, exemplars=[]) == []
    assert retrieve_exemplars({"narration": "chairs"}, k=5, exemplars=None) == []


def test_k_respected() -> None:
    query = _base_row(narration="office chairs purchase")
    exemplars = [{"label": f"L{i}", "text": f"office chairs item {i}"} for i in range(5)]
    out = retrieve_exemplars(query, k=2, exemplars=exemplars)
    assert len(out) == 2
    out_all = retrieve_exemplars(query, k=10, exemplars=exemplars)
    assert len(out_all) == 5
    scores = [hit["score"] for hit in out_all]
    assert scores == sorted(scores, reverse=True)
