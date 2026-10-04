# Implementation Plan: Vertical Slice — End-to-End Predictions File

**Branch**: `001-vertical-slice` | **Date**: 2026-10-03 | **Spec**: `spec.md`

**Input**: Feature specification from `/specs/001-vertical-slice/spec.md`

## Summary

Ship the first measurable VouchIQ increment: `.xlsx` in, `predictions.jsonl/.xlsx` plus A0/A1 baseline metrics out, entirely offline. Deterministic pipeline (ingest → normalise → perspective → evidence → validate) in pure Python; keyword baseline A0; zero-shot SLM scorer A1 behind a stdlib HTTP client to a local llama.cpp server with a stub fallback; synthetic gold factory v1 plus scikit-learn eval harness; CLI plus minimal Streamlit UI; Docker Compose for the offline two-service runtime.

## Technical Context

**Language/Version**: Python 3.11+ (dev machine 3.14.6)

**Primary Dependencies**: pandas, openpyxl, pydantic>=2, rapidfuzz, scikit-learn, streamlit, huggingface_hub (setup only). No torch/faiss/embeddings in this slice (see research.md R1).

**Storage**: Files only — `.xlsx` in, `.jsonl`/`.xlsx`/eval JSON out. No database.

**Testing**: pytest (unit + integration), ruff for lint. Deterministic seeds; stub scorer for model-free CI.

**Target Platform**: Windows 10/11 laptop (minimum 8 GB RAM CPU-only; recommended 16 GB RAM + 6 GB VRAM GPU); Docker Compose for the offline `app` + `llm` runtime.

**Project Type**: CLI + library + minimal web UI.

**Performance Goals**: 500-row sheet end-to-end on the recommended machine without manual intervention; ≥85% single-pass resolution design point (measured from 002).

**Constraints**: Fully offline decision path; no proprietary model; exactly one valid label per row; reproducible metrics.

**Scale/Scope**: Single-file sheets of hundreds to low-thousands of rows; 27-label taxonomy fixed.

## Constitution Check

GATE before build — all five principles satisfied, no violations:
- I (LLM decides): `scorer.py` is the only label source; `baseline.py` A0 is measurement-only and never overrides the pipeline verdict path. PASS.
- II (Perspective first): `perspective.py` runs before evidence/scoring on every row. PASS.
- III (Probabilities): group→member two-step reads with top-2 groups; confidence + review flag in output contract. Calibration proper deferred to 003, raw probs reported honestly. PASS.
- IV (Uncertainty compute): slice is single-pass only; challenger/escalation explicitly out of scope. PASS.
- V (Honest eval): A0 vs A1 reported separately with seeds; misses allowed. PASS.

Re-check after design: no new components added beyond spec — PASS, no Complexity Tracking entries.

## Project Structure

### Documentation (this feature)

```text
specs/001-vertical-slice/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── prediction.schema.json
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
src/vouch_engine/
├── __init__.py
├── labels.py          # 27-label taxonomy + hierarchy + precedence v1
├── schemas.py         # Prediction Pydantic model
├── ingest.py          # Excel read, header detection, profiling
├── normalise.py       # alias + fuzzy + value-pattern mapping
├── perspective.py     # reporting entity + per-row perspective
├── evidence.py        # evidence tags + feasibility mask
├── baseline.py        # A0 keyword classifier (measurement only)
├── scorer.py          # A1 SLM adapter (llama.cpp HTTP + stub)
├── validate.py        # output validation + file writers
├── evaluate.py        # sklearn metrics + report
├── gold.py            # synthetic gold factory v1
└── __main__.py        # CLI: run, evaluate, gold, doctor

tests/unit/           # per-module tests
tests/integration/    # end-to-end pipeline tests
app.py                # Streamlit UI (US3)
scripts/fetch_model.py# GGUF download + llama-server check
docker-compose.yml    # app + llm offline runtime
pyproject.toml
```

**Structure Decision**: Single-project `src/` layout (spec-kit Option 1) with Streamlit app at root; FastAPI deferred to 002 per research R5.

## Complexity Tracking

None — no constitution violations to justify.
