"""Unified web-app helpers: review apply, queue, distribution, stats."""

from vouch_engine import pilot_logic


def _preds():
    return [
        {"row_id": 1, "invoice_number": "A1", "voucher_type": "Purchase",
         "confidence": 0.9, "needs_review": False, "top_k": [], "evidence": []},
        {"row_id": 2, "invoice_number": "A2", "voucher_type": "Sales",
         "confidence": 0.2, "needs_review": True, "top_k": [], "evidence": []},
    ]


def test_review_queue_only_flagged():
    assert [q["row_id"] for q in pilot_logic.review_queue(_preds())] == [2]


def test_apply_decisions_override_and_clear():
    final, approvals = pilot_logic.apply_decisions(
        _preds(), [{"row_id": 2, "verdict": "override", "label": "Expense", "note": "t"}])
    by_id = {r["row_id"]: r for r in final}
    assert by_id[2]["voucher_type"] == "Expense"
    assert by_id[2]["needs_review"] is False
    assert any(e.startswith("HUMAN:override") for e in by_id[2]["evidence"])
    assert by_id[1]["needs_review"] is False
    assert approvals[1]["model_label"] == "Sales"


def test_apply_decisions_escalate_keeps_flag():
    final, _ = pilot_logic.apply_decisions(
        _preds(), [{"row_id": 2, "verdict": "escalate"}])
    assert [r for r in final if r["row_id"] == 2][0]["needs_review"] is True


def test_distribution_and_stats():
    assert pilot_logic.label_distribution(_preds()) == {"Purchase": 1, "Sales": 1}
    stats = pilot_logic.review_stats(_preds(), [{"verdict": "approve"}])
    assert stats["n_rows"] == 2 and stats["needs_review"] == 1
    assert stats["by_verdict"] == {"approve": 1}
