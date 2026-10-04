# Bug assessment: flaky-suite (2026-10-04)

## Symptom
Full suite failed twice (1 failed / ~130 passed) across ~20 runs, never the same test twice, never reproduced on demand.

## Evidence
- 12+ consecutive green runs plus 3 PYTHONHASHSEED variants (1, 2, 42), all green.
- Grep for time/sleep/random/glob nondeterminism in tests/: one hit (auth ms timestamps, TTL-guarded, not racy).
- No shared-state files: all integration tests use tmp_path; no xdist parallelism.

## Suspected cause
Transient Windows file/timing noise (both failures occurred in runs concurrent with heavy machine load: server downloads, parallel sweeps). No code defect identified.

## Verdict: UNREPRODUCIBLE — no fix attempted (fixing without reproduction risks cargo-cult changes).
Mitigations instead: loop-runner note in quickstart (re-run once on single red, send FAILED line), hash-seed sweep documented green.

