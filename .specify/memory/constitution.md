# VouchIQ Constitution

## Core Principles

### I. LLM Decides (NON-NEGOTIABLE)
No deterministic component ever outputs a voucher label. Code produces evidence tags plus a soft feasibility mask; the open-weight SLM gives the verdict as probabilities. Removing the LLM must remove the label entirely.

### II. Perspective Before Reasoning
Resolve whose books these are before any classification: reporting entity via party-name/GSTIN frequency, fuzzy near-duplicate merging, and own-invoice-series detection. Every row carries perspective in {seller, buyer, neither, unknown}.

### III. Probabilities, Not Strings
Constrained label-code scoring (group A–G, then member — two single-token steps over the 27-label hierarchy); temperature-scaled calibration; margin plus entropy drive the `needs_review` flag. Target: ECE ≤ 0.08.

### IV. Spend Compute Where Uncertainty Is
Single-pass tier resolves the large majority of rows. Only low-margin rows reach the pairwise challenger (position-swapped) or the escalation model, under a fixed escalation cap per run.

### V. Evaluate Honestly (NON-NEGOTIABLE)
Leave-template-out splits by scenario template and perturbation family. Synthetic, human-verified gold (double-annotated, Cohen's kappa reported), and organiser-sample results are reported separately — never mixed. Ablation ladder A0–A9 for every claim. Numeric targets are goals to be measured, including misses, never claims.

### VI. No Silent Fallbacks (NON-NEGOTIABLE)
Every degraded path WARNs on stderr with the cause and is counted (invalid, skipped, fallback). A uniform or random fallback must never masquerade as a model verdict — silent fallbacks once cost us a fake 3.7% measurement.

### VII. Parallelism Must Prove Equivalence
Bit-identical reproduction is the default (workers=1). Higher parallelism ships only with a measured flip report (label flips and max confidence delta on a fixed set) recorded in specs/.

## Additional Constraints

Technology stack: Python 3.11+, pandas/openpyxl, Pydantic, RapidFuzz, sentence-transformers (multilingual-e5-small), FAISS, llama.cpp server (GGUF Q4; vLLM optional), scikit-learn, FastAPI plus Streamlit, Docker Compose. Pinned requirements, fixed seeds, greedy decoding, recorded model hashes.
Offline and open: no network call and no proprietary model anywhere in the decision path. Apache-2.0-compatible dependencies only. Synthetic data only in the repo; no real GSTINs or taxpayer data.
Output contract: exactly one valid label per row from the 27-label set. Minimum record `{"invoice_number": …, "voucher_type": …}`; extended record adds `confidence`, `needs_review`, `top_k`, `evidence`.

## Development Workflow

Vertical slice first: an end-to-end predictions file plus metrics exists within the first session (ingest → zero-shot LLM → output → metrics). Every later change must move a measured number on the gold set. MoSCoW scope per README §15; defined cut list (§16.3) when time is short. pytest plus ruff gates; one command regenerates every metric and plot from fixed seeds.

## Governance

Constitution supersedes all other practices. Amendments require a version bump with rationale. All reviews verify the LLM-decides rule, the offline rule, and the honest-evaluation rule. Added complexity must be justified by an ablation gain.

**Version**: 1.1.0 | **Ratified**: 2026-10-03 | **Last Amended**: 2026-10-04 (VI no-silent-fallbacks, VII parallelism-equivalence — both learned from measured incidents)
