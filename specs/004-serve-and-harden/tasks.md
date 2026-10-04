# Tasks: 004

## Phase 1: API (US1)
- T040 api.py create_app + POST /predict + GET /health + POST /evaluate; test_api.py contract tests

## Phase 2: Retro-audit (US2)
- T041 audit.py + CLI audit command + test_audit.py

## Phase 3: Robustness (US3)
- T042 robust.py perturb + sweep + CLI robust command + test_robust.py

## Phase 4: Human gold starter (US4)
- T043 gold/verify.csv (60 hand-checked rows) + evaluate.cohen_kappa + kappa test + CI smoke note

## Phase 5: Converge
- T044 full suite + ruff + SC-001..004 checklist + results_004.md

