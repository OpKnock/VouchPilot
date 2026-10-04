# Bake-off + QLoRA spike (2026-10-03, subset gold54 unless noted)

| Model | A1 acc | A1 macro-F1 | A4 acc | A4 macro-F1 |
|---|---|---|---|---|
| Qwen3.5-4B Q4 | 0.241 | 0.100 | 0.259 | 0.114 |
| Gemma 4 E4B Q4 | 0.130 | 0.064 | 0.222 | 0.090 |

Decision: freeze Qwen3.5-4B default; Gemma stays challenger option. Gemma collapses to Stock Journal under bare-code protocol (harness mismatch, not a model verdict).

Rate cap: --max-challenge-rate 0.25 challenges exactly 14/54 (lowest-margin first); A7-54 at 25pct budget: acc 0.333 macro-F1 0.177 vs full A7 0.463/0.309.

QLoRA spike verdict: NOT feasible on this laptop (torch CPU-only; bitsandbytes has no Windows wheels; Unsloth is WSL-only). Plan B stays: Linux/cloud-GPU in the final; pipeline is adapter-ready. No training run attempted (would be CPU-bound).

