"""Unit tests for scorer prompts, llama-server mapping, and stub determinism."""

import json
from unittest.mock import patch

from vouch_engine import scorer
from vouch_engine.labels import LABEL_NAMES, LABELS
from vouch_engine.scorer import (
    LlamaServerScorer,
    StubScorer,
    build_group_prompt,
    build_member_prompt,
)


class _FakeResp:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode("utf-8")
        self.status = 200

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _completion_payload(entries: list[dict]) -> dict:
    return {"completion_probabilities": [{"probs": entries}]}


def _template_resp() -> _FakeResp:
    """Fake /apply-template reply; scorer appends the think-close suffix."""
    return _FakeResp({"prompt": "TEMPLATED Group:"})


def _row() -> dict:
    return {
        "row_id": 1,
        "narration": "sales invoice",
        "items": [{"desc": "chairs"}],
        "raw": {},
    }


def test_prompts_contain_tables_and_evidence():
    row = _row()
    g = build_group_prompt(row, ["PERSPECTIVE: seller"])
    assert "A = Trade invoices" in g
    assert "narration: sales invoice" in g
    assert "PERSPECTIVE: seller" in g
    assert "single code token" in g.lower()
    m = build_member_prompt(row, ["CUE: sales"], "A")
    assert "A1 = Purchase" in m
    assert "A2 = Sales" in m
    assert "CUE: sales" in m
    assert "single code token" in m.lower()


def test_complete_normalises_to_sum_one():
    payload = _completion_payload(
        [{"tok_str": " A", "prob": 2.0}, {"tok_str": " B", "prob": 1.0}]
    )
    with patch.object(
        scorer.urllib.request, "urlopen", return_value=_FakeResp(payload)
    ):
        out = LlamaServerScorer()._complete("prompt", ["A", "B"])
    assert abs(sum(out.values()) - 1.0) < 1e-6
    assert abs(out["A"] - 2.0 / 3.0) < 1e-6


def test_complete_substring_fallback():
    payload = _completion_payload([{"tok_str": " A1,", "prob": 1.0}])
    with patch.object(
        scorer.urllib.request, "urlopen", return_value=_FakeResp(payload)
    ):
        out = LlamaServerScorer()._complete("prompt", ["A1", "A2"])
    assert out["A1"] == 1.0


def test_complete_server_top_logprobs_shape():
    """Real llama.cpp shape: top_logprobs/token/logprob (prob = exp)."""
    import math

    payload = {
        "completion_probabilities": [
            {
                "top_logprobs": [
                    {"token": "A", "logprob": math.log(0.8)},
                    {"token": "C", "logprob": math.log(0.2)},
                ]
            }
        ]
    }
    with patch.object(
        scorer.urllib.request, "urlopen", return_value=_FakeResp(payload)
    ):
        out = LlamaServerScorer()._complete("prompt", ["A", "C"])
    assert abs(out["A"] - 0.8) < 1e-6
    assert abs(out["C"] - 0.2) < 1e-6


def test_predict_applies_mask_and_renormalises():
    group = _completion_payload(
        [{"tok_str": " A", "prob": 0.6}, {"tok_str": " C", "prob": 0.3}]
    )
    member_a = _completion_payload(
        [
            {"tok_str": " A2", "prob": 0.8},
            {"tok_str": " A1", "prob": 0.1},
            {"tok_str": " A3", "prob": 0.05},
            {"tok_str": " A4", "prob": 0.05},
        ]
    )
    member_c = _completion_payload(
        [{"tok_str": " C1", "prob": 0.9}, {"tok_str": " C2", "prob": 0.1}]
    )
    mask = {name: 1.0 for name in LABEL_NAMES}
    mask["Sales"] = 0.1  # penalise the unmasked winner to flip the verdict.
    responses = [
        _template_resp(),
        _FakeResp(group),
        _template_resp(),
        _FakeResp(member_a),
        _template_resp(),
        _FakeResp(member_c),
    ]
    with patch.object(
        scorer.urllib.request, "urlopen", side_effect=responses
    ):
        label, conf, top_k = LlamaServerScorer().predict(_row(), [], mask)
    assert label == "Payment"  # C1 wins once Sales is masked down.
    assert label in LABEL_NAMES
    assert 0.0 <= conf <= 1.0
    assert len(top_k) == 3
    assert top_k[0][0] == label
    assert abs(top_k[0][1] - conf) < 1e-9
    probs = [p for _, p in top_k]
    assert probs == sorted(probs, reverse=True)
    assert abs(sum(p for _, p in top_k) - sum(p for _, p in top_k)) < 1e-9
    # Renormalised full distribution implies top prob is a valid share.
    assert 0.0 < conf <= 1.0


def test_predict_without_mask_prefers_sales():
    group = _completion_payload(
        [{"tok_str": " A", "prob": 0.6}, {"tok_str": " C", "prob": 0.3}]
    )
    member_a = _completion_payload([{"tok_str": " A2", "prob": 0.8}])
    member_c = _completion_payload([{"tok_str": " C1", "prob": 0.9}])
    responses = [
        _template_resp(),
        _FakeResp(group),
        _template_resp(),
        _FakeResp(member_a),
        _template_resp(),
        _FakeResp(member_c),
    ]
    mask = {name: 1.0 for name in LABEL_NAMES}
    with patch.object(
        scorer.urllib.request, "urlopen", side_effect=responses
    ):
        label, _, _ = LlamaServerScorer().predict(_row(), [], mask)
    assert label == "Sales"


def test_stub_determinism_and_tie_break():
    mask = {name: 1.0 for name in LABEL_NAMES}
    mask["Export"] = 5.0
    mask["Sales"] = 5.0  # tie with Export; LABELS order (Sales earlier) wins.
    first = StubScorer().predict({}, [], mask)
    second = StubScorer().predict({}, [], mask)
    assert first == second
    label, conf, top_k = first
    assert label == "Sales"
    assert conf == 0.5
    assert abs(sum(p for _, p in top_k) - 1.0) < 1e-6
    assert top_k[0][0] == "Sales"
    # Empty mask falls back to LABELS order.
    label2, _, _ = StubScorer().predict({}, [], {})
    assert label2 == LABELS[0]["name"]
