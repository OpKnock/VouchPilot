"""Unit tests for the bounded agentic loop (inspect, gate, audit)."""

import json

import pytest

from vouch_engine import agent
from vouch_engine.__main__ import main
from vouch_engine.labels import LABEL_NAMES


def _tiny_states():
    return [
        {"ok": True, "crow": {"narration": "x"}, "row_id": 1, "invoice": "A1",
         "tags": ["T1"], "label": "Purchase", "conf": 0.9, "top_k": [["Purchase", 0.9]]},
        {"ok": True, "crow": {"narration": "y"}, "row_id": 2, "invoice": "A2",
         "tags": ["T2"], "label": "Sales", "conf": 0.2, "top_k": [["Sales", 0.2]]},
        {"ok": False, "row_id": 3, "invoice": "A3"},
    ]


def test_review_queue_thresholds():
    queue = agent.build_review_queue(_tiny_states())
    assert [q["row_id"] for q in queue] == [2]
    assert queue[0]["reason"] == "low-confidence"


def test_apply_gate_override_approve_escalate():
    states = _tiny_states()
    decisions = [
        {"row_id": 1, "verdict": "approve"},
        {"row_id": 2, "verdict": "override", "label": "Expense", "note": "human"},
    ]
    approvals = agent.apply_gate(states, decisions, "file", agent.AgentState("."))
    assert states[0]["label"] == "Purchase"
    assert any(t == "HUMAN:approved" for t in states[0]["tags"])
    assert states[1]["label"] == "Expense"
    assert any(t.startswith("HUMAN:override") for t in states[1]["tags"])
    by_id = {a["row_id"]: a for a in approvals}
    assert by_id[1]["verdict"] == "approve"
    assert by_id[2]["final_label"] == "Expense"
    assert by_id[2]["model_label"] == "Sales"


def test_apply_gate_escalate_forces_review():
    states = _tiny_states()
    agent.apply_gate(states, [{"row_id": 2, "verdict": "escalate"}], "cli", agent.AgentState("."))
    assert states[1]["force_review"] is True
    assert "HUMAN:escalated" in states[1]["tags"]


def test_approved_rows_cleared_not_forced():
    states = _tiny_states()
    agent.apply_gate(
        states,
        [{"row_id": 1, "verdict": "approve"},
         {"row_id": 2, "verdict": "override", "label": "Expense"}],
        "file",
        agent.AgentState("."),
    )
    assert states[0].get("cleared") is True
    assert states[1].get("cleared") is True
    assert not states[0].get("force_review", False)


def test_gate_file_validation(tmp_path):
    good = tmp_path / "d.json"
    good.write_text(json.dumps({"decisions": [{"row_id": 1, "verdict": "override",
                                               "label": "Sales"}]}), encoding="utf-8")
    out = agent.gate_file(str(good))
    assert out[0]["label"] == "Sales"
    bad = tmp_path / "b.json"
    bad.write_text(json.dumps({"decisions": [{"row_id": 1, "verdict": "nope"}]}), encoding="utf-8")
    with pytest.raises(ValueError):
        agent.gate_file(str(bad))
    bad2 = tmp_path / "b2.json"
    bad2.write_text(json.dumps({"decisions": [{"row_id": 1, "verdict": "override",
                                               "label": "Nope"}]}), encoding="utf-8")
    with pytest.raises(ValueError):
        agent.gate_file(str(bad2))


def test_trace_records_tool_calls(tmp_path):
    state = agent.AgentState(str(tmp_path))
    state.log("inspect", "inspect_sheet", None, "x")
    state.log("classify", "score_row", 1, "ok=True")
    out = tmp_path / "t.jsonl"
    state.write_trace(str(out))
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["seq"] == 1


def test_labels_all_valid_for_override():
    assert "Sales" in LABEL_NAMES and "Expense" in LABEL_NAMES


def _run_gold_sheet(tmp_path, n=24, seed=3):
    from vouch_engine import gold

    prefix = str(tmp_path / "g")
    gold.build_dataset(n, seed, prefix)
    return prefix + ".xlsx", prefix + "_labels.json"


def test_agent_auto_matches_run(tmp_path):
    xlsx, labels = _run_gold_sheet(tmp_path)
    pred_run = str(tmp_path / "run.jsonl")
    pred_agent = str(tmp_path / "agent.jsonl")
    assert main(["run", "--input", xlsx, "--out", pred_run, "--scorer", "stub"]) == 0
    assert main(["agent", "run", "--input", xlsx, "--out", pred_agent,
                 "--scorer", "stub", "--gate", "auto"]) == 0
    run_rows = [json.loads(line) for line in open(pred_run, encoding="utf-8")]
    agent_rows = [json.loads(line) for line in open(pred_agent, encoding="utf-8")]
    assert [r["voucher_type"] for r in run_rows] == [r["voucher_type"] for r in agent_rows]
    stem = str(tmp_path / "agent")
    for suffix in (".approvals.json", ".trace.jsonl", ".inspection.json"):
        assert (tmp_path / ("agent" + suffix)).exists()
    trace_lines = open(stem + ".trace.jsonl", encoding="utf-8").read().strip().splitlines()
    assert len(trace_lines) > 24
    insp = json.load(open(stem + ".inspection.json", encoding="utf-8"))
    assert insp["n_rows"] == 24


def test_agent_file_gate_override_changes_export(tmp_path):
    xlsx, _ = _run_gold_sheet(tmp_path)
    dec = tmp_path / "dec.json"
    dec.write_text(json.dumps({"decisions": [{"row_id": 1, "verdict": "override",
                                              "label": "Sales", "note": "t"}]}), encoding="utf-8")
    out = str(tmp_path / "o.jsonl")
    assert main(["agent", "run", "--input", xlsx, "--out", out,
                 "--scorer", "stub", "--gate", "file:" + str(dec)]) == 0
    rows = [json.loads(line) for line in open(out, encoding="utf-8")]
    first = [r for r in rows if r["row_id"] == 1][0]
    assert first["voucher_type"] == "Sales"
    assert any(e.startswith("HUMAN:override") for e in first["evidence"])
    approvals = json.load(open(str(tmp_path / "o.approvals.json"), encoding="utf-8"))
    entry = [a for a in approvals["approvals"] if a["row_id"] == 1][0]
    assert entry["final_label"] == "Sales" and entry["verdict"] == "override"


def test_agent_review_template_emits_queue(tmp_path):
    xlsx, _ = _run_gold_sheet(tmp_path)
    out = str(tmp_path / "pending.json")
    assert main(["agent", "review-template", "--input", xlsx, "--out", out,
                 "--scorer", "stub"]) == 0
    data = json.load(open(out, encoding="utf-8"))
    assert "queue" in data and isinstance(data["queue"], list)
