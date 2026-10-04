# Results 004 (2026-10-04)

- API: /health /predict /predict-rows /evaluate contract-tested; SC-001 API==CLI labels on gold54 (covered in test_api via keyword determinism).
- Retro-audit: agreement + per-label confusions + disagreements list.
- O4 drop curve (keyword, gold270): 0.80 at 0/10/20/30pct -> PASS (within 10pts). O5 rename: 0.80 flat -> PASS.
- verify.csv: 60 hand-checked rows, 27 labels; keyword A0 = 0.867/0.825 (second independent confirmation above synthetic 0.80).
- kappa helper verified on known values (1.0 and 0.5 cases).

