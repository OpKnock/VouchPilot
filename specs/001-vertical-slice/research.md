# Research: 001-vertical-slice

**Date**: 2026-10-03 | **Spec**: `spec.md`

## R1. No torch / embeddings / FAISS in this slice — DEFERRED to 002

Retrieval grounding is a Should-feature (README §15), not needed for the P1 baselines exit criterion (first output file + A0/A1 metrics). Header matching uses alias dictionary + RapidFuzz + value-pattern inference only. Rationale: keeps `pip install` to pure wheels, avoids 2GB+ torch, keeps slice shippable in one session. Retrieval arrives with feature 002.

## R2. LLM serving = llama.cpp server binary, client over HTTP with stdlib

No compilation on Windows: use the official llama.cpp release `llama-server` binary plus a Q4 GGUF fetched via `huggingface_hub`. Client uses `urllib` POST to `/completion` with `n_probs` for next-token probabilities (group step, then member step). No new dependency. A `StubScorer` (deterministic round-robin over mask-feasible labels) ships for tests and for runs without downloaded weights. Full grammar-constrained JSON decoding deferred to 002.

## R3. Constrained decoding v1 = two prompted single-token reads

Prompt lists group codes A–G; read top token + probs; repeat for member codes of the top two groups; final P = P(group) × P(member|group), mask-multiplied, renormalised. Matches README §4.3 without needing server-side grammar support.

## R4. Metrics = scikit-learn (preinstalled 1.9.0)

Accuracy, macro/micro/weighted F1, per-class report, confusion matrix. Calibration/ECE arrives with feature 003 (reliability layer).

## R5. FastAPI deferred; slice ships CLI + Streamlit

Spec stories US1–US3 require CLI, metrics, UI. FastAPI endpoint is README stack (§14) but not in the slice stories — added in 002 alongside retrieval. No code written for it now (constitution simplicity).

## R6. Windows-first paths, offline-first runtime

All paths via `pathlib`; no POSIX assumptions. Nothing in the decision path touches the network; model fetch is an explicit setup step (`scripts/fetch_model.py`), verified by `vouch_engine doctor`.
