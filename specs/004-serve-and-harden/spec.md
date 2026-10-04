# Feature Specification: Serving plus Robustness Proof (004)

Closes README gaps: no API service (research R5 deferral), no retro-audit mode (UC3), unmeasured objectives O4 (30pct field removal, drop within 10pts) and O5 (header-rename, within 5pts).

## Stories
- US1 P1: FastAPI service with POST /predict (xlsx upload or rows json, scorer/params as query), GET /health, POST /evaluate; OpenAPI docs free from FastAPI; offline; errors are RFC-style json with row-level invalid counting (never silent).
- US2 P1: retro-audit mode: input xlsx WITH a voucher-type column plus predictions; output disagreement report (recorded vs predicted, per-label agreement matrix, top confusion cells) via CLI audit command and API endpoint.
- US3 P1: perturbation harness CLI robust: --drop-rate/--rename-rate/--seed sweeps on gold; curves of macro-F1 vs rate; O4/O5 verdict lines printed and stored in report json.
- US4 P2: human-verified gold starter: hand-label checklist plus inter-annotator template (gold/verify.csv schema + kappa computed by evaluate); at least 60 hand-checked rows committed as fixtures for CI smoke (fast subset).

## Requirements
- api.py (FastAPI, lazy scorer build, reuse pipeline fns; no new heavy deps; fastapi/uvicorn already present).
- audit.py: audit_recorded_vs_predicted(records, predictions) -> {agreement, per_label[{label, n, agree, top_confusions}], disagreements[]}; CLI audit --input xlsx --pred jsonl --report.
- robust.py: perturb_copy(rows, drop_rate, rename_rate, seed) at RAW level (drop non-essential fields; rename headers from alias families); sweep command writing curves json.
- gold/verify.csv (60 rows, schema row_id,invoice_number,trumps... fields: invoice_number, voucher_type, note) plus kappa helper in evaluate (cohen_kappa(rater_a, rater_b)).
- Tests: api contract tests via fastapi.testclient (predict/evaluate/health shapes); audit unit (perfect agreement=1.0, known disagreement cells); robust unit (rate 0 reproduces baseline; determinism same seed); verify.csv loads and kappa sane.
- Constitution VI/VII apply: warn-and-count everywhere; workers default 1.

## Success Criteria
- SC-001: API predict on gold54 matches CLI labels exactly (same scorer, workers 1).
- SC-002: O4/O5 verdicts printed from one command on synthetic gold (targets likely missed on synthetic; honest numbers either way).
- SC-003: verify.csv kappa computable; CI smoke uses it under 60s.
- SC-004: full suite green.

