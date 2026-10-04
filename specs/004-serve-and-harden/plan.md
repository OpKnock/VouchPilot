# Implementation Plan: 004 Serve and Harden

**Branch**: 004-serve-and-harden | **Date**: 2026-10-04 | **Spec**: spec.md

## Summary
FastAPI service reusing pipeline functions (predict/evaluate/health), retro-audit disagreement reports, raw-level perturbation sweeps for O4/O5, hand-labelled verify.csv starter plus kappa helper.

## Technical Context
Language Python 3.11+; add fastapi/uvicorn (+ httpx? use fastapi.testclient — needs httpx; check availability, else starlette TestClient... fastapi.testclient requires httpx. If missing, pip install httpx (tiny) or test via uvicorn + urllib. Prefer httpx install.
Storage files only. Testing pytest. Platform Windows + Docker (Dockerfile CMD stays streamlit; document uvicorn alternative).

## Constitution Check
I-VII pass: API reuses scorer contracts; audit/robust warn-and-count; workers default 1; no silent fallbacks (new code paths print WARN). No violations.

## Structure
- src/vouch_engine/api.py (app factory create_app(), routes)
- src/vouch_engine/audit.py
- src/vouch_engine/robust.py
- gold/verify.csv + evaluate.cohen_kappa
- tests: test_api.py, test_audit.py, test_robust.py (kappa in test_evaluate or new)

## Complexity Tracking
None.

