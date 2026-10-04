# VouchPilot — offline GST voucher intelligence

VouchPilot classifies Indian accounting transactions into 1 of 27 GST voucher
categories (Purchase, Sales, Import, Export, returns, payments, orders,
job-work, stock, payroll and more). Give it a spreadsheet with the voucher
type missing; it returns the label plus confidence, evidence tags and an
honest `needs_review` flag. Everything runs locally — no accounts, no cloud.

## 30-second start (no model needed)

```powershell
pip install -e .[dev]
python -m pytest tests/ -q                      # expect: 146 passed
python -m vouch_engine gold --n 270 --seed 7 --out demo\gold
python -m vouch_engine run --input demo\gold.xlsx --out demo\pred.jsonl --scorer keyword
python -m vouch_engine evaluate --gold demo\gold_labels.json --pred demo\pred.jsonl
```

## Web app (one command)

```powershell
powershell -ExecutionPolicy Bypass -File start-vouchpilot.ps1
# or double-click start-vouchpilot.bat / VouchPilot.exe, then open http://127.0.0.1:8000
```

First build the premium UI once: `cd web && npm install && npm run build && cd ..`.
The same backend also serves the API (`/predict`, `/evaluate`, `/health`,
`/settings`, `/system`, `/labels`) with free OpenAPI docs at `/docs`.

## Real AI scoring (optional, needs GPU + downloads)

```powershell
python scripts/fetch_model.py --out models      # ~2.7 GB Qwen3.5-4B Q4
python scripts/fetch_server.py                  # ~650 MB llama.cpp CUDA build
# server starts automatically via start-vouchpilot.ps1, or manually:
.\tools\llama-server\bin\llama-server.exe -m models\Qwen3.5-4B-Q4_K_M.gguf --host 127.0.0.1 --port 8080 -c 4096 --n-gpu-layers 99 --cache-type-k q8_0 --cache-type-v q8_0
python -m vouch_engine run --input demo\gold.xlsx --out demo\pred.jsonl --scorer server --workers 4
```

Minimum 8 GB RAM CPU-only; recommended 16 GB RAM + 6 GB VRAM GPU.

## What is "keyword" scorer?

The built-in rules classifier: instant, no download, strong baseline
(macro-F1 0.80 on synthetic gold). `server` is the Qwen3.5-4B AI model
(needs the llama server above); `vouchpilot` adds fraud screening on top;
`stub` is a deterministic placeholder for tests.

## Measured numbers (Qwen3.5-4B Q4, local RTX 4050)

| Variant | acc | macro-F1 |
|---|---|---|
| A0 keyword (270 synthetic) | 0.796 | 0.800 |
| A0 keyword (60 hand-verified) | 0.867 | 0.825 |
| A1 raw SLM (54) | 0.241 | 0.100 |
| A4 grounded k=5 (54) | 0.259 | 0.114 |
| A7 challenger (54 / 270) | 0.463 / 0.411 | 0.309 / 0.338 |
| A4+A7 (54) | 0.500 | 0.349 |

Synthetic gold flatters the keyword baseline (shared vocabulary); the
human-verified set in `gold/verify.csv` is the honest check. Calibration
(T=1.1) cut fit-set ECE 0.124 to 0.070.

## Layout

- `src/vouch_engine/` — pipeline (ingest, normalise, perspective, evidence,
  scorers, challenger, calibration, eval, agent loop, API)
- `extensions/` — fraud screens, auth, RAG evidence, retraining skeleton,
  vendor reports, tamper pins (all optional, off by default)
- `web/` — premium React UI (build it, then it is served by the API)
- `gold/verify.csv` — 60 hand-checked rows across all 27 labels
- `specs/` — Spec-Kit history (constitution, specs, measured results)
- `pilot.py`, `app.py` — legacy Streamlit apps (still work)

## Docs

- `docs/RELEASING.md` — building `VouchPilot.exe` and the desktop zip
- `specs/*/` — design history and honest measurement logs
