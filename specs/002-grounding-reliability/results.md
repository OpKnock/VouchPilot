# Measured ladder (Qwen3.5-4B Q4, llama.cpp b11374 CUDA, 2026-10-03)

Subset gold54 (seed 11) / full gold270 (seed 7), greedy, seeds fixed.

| Variant | Subset acc | Subset macro-F1 | Full-270 acc | Full-270 macro-F1 |
|---|---|---|---|---|
| A0 keyword | 0.796 | 0.755 | 0.796 | 0.800 |
| A1 raw SLM | 0.241 | 0.100 | - | - |
| A4 grounded (k=5) | 0.259 | 0.114 | - | - |
| A7 challenger (margin 0.15) | 0.463 | 0.309 | 0.411 | 0.338 |
| A4+A7 | 0.500 | 0.349 | - | - |

Calibration (T=1.1 fit on 54): fit-set ECE 0.124 to 0.070; full-270 ECE 0.355 to 0.304.

Caveats: synthetic gold shares vocabulary with keyword table (flatters A0); SLM numbers are zero/few-shot with no fine-tuning; challenger fired on 100pct of rows (tie-heavy margins) so cost is 5x calls per row; server lean config c1024 plus q8 KV cache.


Parallelism (2026-10-04): ThreadPool row workers, order-preserving. 20-row check workers1-vs-workers4: 0 label flips, max conf diff 0.055 (server batching wobble); 3.8x speedup (79s vs 301s). Root causes fixed along the way: (1) unified KV pool too small for 4 parallel prompts -> -c 4096; (2) silent uniform fallbacks hid HTTP 500s -> retry plus WARN logs; (3) cache_prompt disabled (flaky restore path in b11374). Default --workers 1 for bit-identical repro.

