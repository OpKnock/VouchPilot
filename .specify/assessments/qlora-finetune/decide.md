# Assessment decision: QLoRA fine-tune (2026-10-04)

## Intake
Proposal: QLoRA-finetune Qwen3.5-4B on synthetic gold to beat keyword A0 (0.80) before the final.

## Research (measured, this machine)
- torch 2.13.0+cpu, cuda=False. bitsandbytes: no Windows wheels. Unsloth: WSL-only.
- transformers 5.18 installs, but training would be CPU-bound and the serving stack is CUDA.
- VRAM 6GB could theoretically hold 4B QLoRA, but no Windows QLoRA toolchain exists natively.

## Define/shape
Would need: Linux or cloud GPU + pinned transformers/trl/peft supporting Qwen3.5 arch + held-out human gold for honest eval.

## Decision: STOP (kill)
Cost and risk exceed benefit on this laptop; zero-shot plus challenger plus calibration already move the numbers, and synthetic-only fine-tuning risks overfitting to generator vocabulary (constitution V). Revisit only with Linux/cloud GPU in the final.

