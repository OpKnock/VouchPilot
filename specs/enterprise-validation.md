# Enterprise validation protocol

VouchPilot must not claim accounting or audit accuracy from synthetic data alone.

## Validation tiers

**Tier 1 — Synthetic:** seeded generated data used for regression testing. Useful for engineering, not evidence of real-world quality.

**Tier 2 — Hand-verified:** representative rows reviewed by a human. Useful for pre-production benchmarking, but still subject to selection bias.

**Tier 3 — Production sample:** independently labelled historical enterprise records from the intended customer population, with a documented sampling strategy and separation from development/tuning data.

Only Tier 3 can set **enterprise-ready** in the validation report.

## Required measurements

The validation command reports:

- overall accuracy and macro-F1 across all 27 voucher categories;
- per-category precision, recall, F1 and support;
- review/abstention rate;
- high-confidence error rate;
- expected calibration error;
- class coverage and minimum class support;
- unknown/unrecognised predicted labels.

## Release gate

Run:

\`python scripts/validate_enterprise.py --gold <dataset.csv> --dataset-type production\`

For an enterprise pilot, require thresholds agreed with the customer before evaluating the model. The command defaults to accuracy ≥ 0.80, macro-F1 ≥ 0.70, review rate ≤ 0.60, high-confidence error rate ≤ 0.05, and at least one labelled row per class.

These defaults are engineering gates, not regulatory standards.

## Current repository evidence

\`gold/verify.csv\` is a hand-verified benchmark and therefore cannot, by itself, establish enterprise readiness. Use its report to find weak categories and guide the next data-collection cycle.

Never label a classifier “GST compliant”, “audit approved”, or “regulator validated” without domain-specific evidence and professional review.
