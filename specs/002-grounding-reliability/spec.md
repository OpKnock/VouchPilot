# Feature Specification: Grounding + Reliability (A4/A6/A7)

Measured A1: acc 0.24 vs keyword A0 0.80 on synthetic gold (270-row pending). This feature adds retrieval grounding (US1), temperature calibration (US2), pairwise challenger (US3) per README ladder.

## Stories
- US1 P1: run --exemplars/--k with class-balanced evidence-Jaccard retrieval; A4 macro-F1 greater than A1.
- US2 P1: calibrate command fits T on held-out split; evaluate reports ECE + coverage-accuracy; calibrated ECE lower.
- US3 P2: challenger recheck on low-margin rows, order-swapped averaging; pairwise F1 on 11 README pairs not worse.

## Requirements
- retriever.py build_index/retrieve/exemplars_from_gold; scorer predict() gains optional exemplars param.
- calibrate.py fit_temperature/apply/ece/coverage_accuracy.
- challenger.py recheck with order swap.
- CLI flags all optional; stdlib plus sklearn only; 001 tests stay green.

