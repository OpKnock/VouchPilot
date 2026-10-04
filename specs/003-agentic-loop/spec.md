# Feature Specification: Agentic Loop with Human Approval (003)

Implements README section 13 as runnable code: bounded deterministic multi-role workflow, not a free-roaming agent. Each role has typed I/O and a step budget; all tool calls are local.

## Roles and order
1. Inspector: profiles sheet (header detection, fill rates, schema mapping coverage, perspective summary) and emits inspection report with red flags.
2. Reasoner/Classifier: per row builds evidence plus retrieved exemplars, calls scorer tool, records verdict with margin.
3. Challenger: re-checks low-margin rows within --max-challenge-rate budget (existing challenger.py).
4. Gatekeeper: collects needs_review rows into a review queue and REQUESTS HUMAN APPROVAL (cli interactive, file-based, or auto).
5. Exporter: writes predictions plus approvals.json plus trace.jsonl audit; invalid outputs rejected and counted.

## Stories
- US1 P1: agent run --gate auto reproduces run command output plus inspection report and audit trace.
- US2 P1: agent run --gate file:decisions.json merges human overrides; overridden rows carry HUMAN evidence tag; approvals recorded.
- US3 P1: review-template emits pending.json; Streamlit Review tab approves/overrides and saves decisions.json.
- US4 P2: step budget enforced (max tool calls per row); trace shows every tool call with inputs/outputs hashes.

## Requirements
- agent.py: ToolRegistry (inspect_sheet, map_schema, resolve_perspective, extract_evidence, retrieve_exemplars, score_row, challenge_row, apply_calibration, validate_export) each with name/cost/budget; AgentRunner runs roles in fixed order; per-row step cap (default 12 tool calls).
- Gates: auto (no pause, flags stay), cli (interactive approve/override/escalate per queued row, batch commands: all/quit), file:PATH (decisions json {row_id: {verdict: approve/override/escalate, label?, note?}}).
- Export contract unchanged (Prediction schema); human verdicts in evidence HUMAN tags plus approvals.json {row_id, model_label, final_label, verdict, note, by}.
- No network, no new deps, deterministic given same inputs plus decisions file.

## Success Criteria
- SC-001: auto gate output identical labels to run command on same input/scorer.
- SC-002: override in decisions file changes exported label and appears in approvals.json with HUMAN tag.
- SC-003: trace.jsonl contains one entry per tool call with row scope.
- SC-004: full suite green.

