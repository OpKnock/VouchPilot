# Tasks: Vertical Slice — End-to-End Predictions File

**Input**: `spec.md`, `plan.md`, `data-model.md`, `contracts/`

**Team split**: Team-A deterministic pipeline · Team-B ML scoring · Team-C data/eval/CLI · Integrator packaging/UI/verify.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup (Integrator)

**Purpose**: Skeleton every team codes against.

- [ ] T001 Create `src/vouch_engine/` package with `labels.py` (27 LABELS + GROUPS + PRECEDENCE_V1), `schemas.py` (Prediction model), `__init__.py`
- [ ] T002 Create `pyproject.toml` (pinned deps per plan, ruff config) + `tests/unit`, `tests/integration` dirs
- [ ] T003 [P] Write failing smoke test `tests/unit/test_labels.py` (27 labels, groups A–G) and make it pass

## Phase 2: Foundational — deterministic pipeline (Team-A, blocks US1)

- [ ] T010 [US1] `ingest.py::read_excel` — header-row detection, type inference, fill-rate profile + `tests/unit/test_ingest.py`
- [ ] T011 [US1] `normalise.py` — alias dict + RapidFuzz + value-pattern inference (GSTIN/date/currency/HSN), Indian digit grouping, `to_canonical` per data-model + `tests/unit/test_normalise.py`
- [ ] T012 [US1] `perspective.py::resolve` — normalised party keys, fuzzy near-dedup, frequency + invoice-series signals, perspective in {seller,buyer,neither,unknown} + `tests/unit/test_perspective.py`
- [ ] T013 [US1] `evidence.py::extract` — tag families + soft mask builder + `tests/unit/test_evidence.py`
- [ ] T014 [US1] `validate.py` — Pydantic validation, jsonl/xlsx writers, invalid-label accounting + `tests/unit/test_validate.py`

**Checkpoint**: `CanonicalRow → tags/mask → Prediction` round-trips on synthetic rows without any scorer.

## Phase 3: US1 scoring — baselines + SLM (Team-B, needs Phase 2 contracts)

- [ ] T020 [P] [US1] `baseline.py::keyword_predict` — versioned 27-label keyword table + confidence + `tests/unit/test_baseline.py`
- [ ] T021 [US1] `scorer.py::LlamaServerScorer` — stdlib HTTP client to llama.cpp `/completion`, group→member two-step reads over top-2 groups, mask multiply + renormalise + `tests/unit/test_scorer.py` (mocked HTTP)
- [ ] T022 [US1] `scorer.py::StubScorer` — deterministic mask-respecting fallback + `scripts/fetch_model.py` (GGUF download, server check)
- [ ] T023 [US1] Integration `tests/integration/test_pipeline_us1.py` — 10-row synthetic sheet to valid predictions file (stub scorer)

**Checkpoint**: US1 independently demonstrable: file in, valid predictions file out.

## Phase 4: US2 gold + metrics (Team-C, needs Phase 2 contracts)

- [ ] T030 [P] [US2] `gold.py::generate` — scenario templates × perturbations, seeded, ≥200 rows with known labels + `tests/unit/test_gold.py`
- [ ] T031 [US2] `evaluate.py::compute_metrics` — sklearn accuracy/macro/micro/weighted F1, per-class report, confusion matrix, A0-vs-A1 delta, latency stats + `tests/unit/test_evaluate.py`
- [ ] T032 [US2] `__main__.py` CLI — `run`, `evaluate`, `gold`, `doctor` subcommands + `tests/integration/test_cli_us2.py` (seed reproducibility: identical metrics twice)

**Checkpoint**: US1+US2 demonstrable: baselines measured and reproducible.

## Phase 5: US3 UI + packaging (Integrator)

- [ ] T040 [US3] `app.py` Streamlit — upload, results table with confidence/evidence, JSON+XLSX download (reuses pipeline, no new logic)
- [ ] T041 [US3] `docker-compose.yml` — offline `app` + `llm` services, weights volume
- [ ] T042 Polish — `ruff check`, full `pytest`, `quickstart.md` validation walkthrough, 500-row demo run

**Checkpoint**: All three stories independently functional; contracts/ reports archived next to outputs.

## Dependencies & Execution Order

- Phase 1 → unblocks A, B, C in parallel (they code to `labels.py`/`schemas.py`/data-model contracts).
- Phase 2 → unblocks Phase 3 and 4 integration tests.
- B-T020 and C-T030 are [P] immediately after Phase 1 (no Phase 2 dependency except shared contracts).
- Phase 5 after US1+US2 green.

## Parallel Opportunities

- T010–T014 sequential within Team-A (same pipeline chain); T020+T030 in parallel on other teams.
- All `tests/unit` files are independent per module.
