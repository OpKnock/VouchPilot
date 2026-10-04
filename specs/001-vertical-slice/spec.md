# Feature Specification: Vertical Slice — End-to-End Predictions File

**Feature Branch**: `001-vertical-slice`

**Created**: 2026-10-03

**Status**: Draft

**Input**: VouchIQ README §§ P0–P1 (Setup + Baselines). First shippable slice: ingest → zero-shot SLM → predictions file → metrics.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bulk triage to predictions file (Priority: P1)

An evaluator runs one command against an unlabelled `.xlsx` (voucher-type column missing) and gets `predictions.jsonl` + `predictions.xlsx` with exactly one valid label per row from the 27-label set, minimum record `{"invoice_number": …, "voucher_type": …}`.

**Why this priority**: Without an end-to-end file nothing else can be measured. This is the README P1 exit criterion.

**Independent Test**: Run `python -m vouch_engine run --input sample.xlsx --out predictions.jsonl` on a 50-row synthetic sheet; validate every row has a valid label via Pydantic schema.

**Acceptance Scenarios**:

1. **Given** an `.xlsx` with title rows and blank lines, **When** the pipeline runs, **Then** the header row is detected, all data rows are classified, and no row is dropped silently.
2. **Given** a sheet with renamed headers (e.g. `Seller Name` → `Supplier`), **When** the pipeline runs, **Then** alias plus fuzzy mapping still produces a predictions file with one valid label per row.

---

### User Story 2 - Reproducible baseline metrics (Priority: P1)

The same run emits an evaluation report: accuracy, macro/micro/weighted F1, per-class precision/recall/F1, confusion matrix — for both the keyword baseline (A0) and the raw-row zero-shot LLM baseline (A1).

**Why this priority**: Baselines are the floor every later component must beat (ablation ladder A0–A1). No baselines, no measurable progress.

**Independent Test**: Run `python -m vouch_engine evaluate --gold gold.csv --pred predictions.jsonl`; check the report contains both baselines and the A1-vs-A0 delta table.

**Acceptance Scenarios**:

1. **Given** a gold file with known labels, **When** evaluation runs twice with fixed seeds, **Then** all metrics are bit-identical across runs.
2. **Given** predictions with an invalid label string, **When** validation runs, **Then** the row is counted, logged, and reported — never silently dropped.

---

### User Story 3 - Minimal upload and download UI (Priority: P2)

An evaluator opens the Streamlit app, uploads an `.xlsx`, sees a results table with voucher type plus confidence and evidence per row, and downloads JSON/XLSX.

**Why this priority**: Evaluator-friendly inspection is a Must feature, but it rides on top of Stories 1–2 and can slip a phase without breaking measurement.

**Independent Test**: Upload the same 50-row sheet via UI; downloaded JSON matches CLI output row-for-row.

**Acceptance Scenarios**:

1. **Given** the app running offline via Docker Compose, **When** a file is uploaded, **Then** results render with per-row evidence and a download button.

### Edge Cases

- Rows with no party, no items, and no money (e.g. attendance rows): must still get one valid label plus `needs_review: true`, never an empty output.
- Fully offline run with model weights missing: fail fast with a clear message stating the expected weights path, not a stack trace.
- Duplicate invoice numbers across rows: each row classified independently; row_id keeps outputs distinct.
- Indian digit grouping (`1,23,456.00`) and mixed date formats: parsed to canonical numbers/ISO dates or flagged in the field-presence profile.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST read `.xlsx` via openpyxl/pandas, detect the header row, infer column types, and record per-column fill rates.
- **FR-002**: System MUST map arbitrary headers onto the canonical schema via alias dictionary then RapidFuzz similarity; unmapped columns MUST be retained as free-text metadata for the model.
- **FR-003**: System MUST attach a perspective tag in {seller, buyer, neither, unknown} per row (frequency plus invoice-series signals; `unknown` on failure, never a guess presented as fact).
- **FR-004**: System MUST compute the minimal evidence-tag set (perspective, doc-sign, has-items, tax-split, pay-mode, currency, people-fields, narration cues) and pass it to the model.
- **FR-005**: System MUST score rows with Qwen3.5-4B instruct Q4 via local llama.cpp using constrained group-then-member decoding; raw-row zero-shot prompt for the A1 baseline (no evidence), evidence prompt for the pipeline variant.
- **FR-006**: System MUST emit `predictions.jsonl` and `predictions.xlsx` with minimum records plus `confidence`, `needs_review`, and `evidence` fields; exactly one valid label per row enforced by Pydantic.
- **FR-007**: System MUST compute accuracy, macro/micro/weighted F1, per-class precision/recall/F1 with support, and the confusion matrix for A0 (keyword baseline) and A1 (zero-shot baseline).
- **FR-008**: System MUST run fully offline with no network calls and no proprietary model in the decision path.
- **FR-009**: System MUST pin library versions, fix random seeds, use greedy decoding, and record model file hashes so metrics reproduce bit-identically.
- **FR-010**: Keyword baseline MUST cover all 27 labels with a versioned keyword table (shared with the future playbook), so A0 is a fair floor.
- **FR-011**: Hidden-dataset schema is unknown [NEEDS CLARIFICATION: exact column names and sign conventions for returns will only be known at final; alias dictionary ships with best-guess coverage plus value-pattern inference].

### Key Entities

- **CanonicalRow**: typed transaction fields (parties, doc refs, items, money, tax, currency, people, references) with nulls where absent, plus field-presence profile.
- **EvidenceTags**: human-readable per-row tag list plus soft feasibility mask over the 27 labels.
- **Prediction**: `row_id`, `invoice_number`, `voucher_type`, `confidence`, `needs_review`, `top_k`, `evidence`.
- **EvalReport**: metrics tables, confusion matrix, A0-vs-A1 delta, latency and memory figures, stored as JSON next to the report.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: End-to-end predictions file for a 500-row sheet completes on the recommended machine (16 GB RAM + 6 GB VRAM) with no manual intervention.
- **SC-002**: Re-running the pipeline plus evaluation with fixed seeds reproduces every reported metric exactly.
- **SC-003**: Pipeline variant (evidence prompt) scores at or above the A0 keyword baseline on the first synthetic gold set — reported honestly either way.
- **SC-004**: 100% of output rows pass Pydantic validation with exactly one label from the 27-label set.

## Assumptions

- A1: one flat sheet, one transaction per row (README §2.5).
- A2: rows come from one reporting entity's books or a small number of entities.
- A3: no labelled sample from organisers; the slice builds its own synthetic gold (gold-set factory v1 follows in feature 002).
- A4: machine-readable output is required; minimum record is invoice_number plus voucher_type.
- A5: where two labels overlap, the more specific one wins (precedence policy v1, versioned).
- Scope is the vertical slice only: retrieval, calibration, challenger, cross-record graph, and QLoRA are explicitly out of this feature.
