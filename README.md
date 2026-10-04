# VouchPilot

**Offline GST voucher intelligence.** Upload a spreadsheet of Indian
accounting transactions with the voucher-type column missing — VouchPilot
returns one of 27 voucher categories per row, with confidence, evidence tags
and an honest `needs_review` flag. No accounts, no cloud, nothing leaves
your machine.

- 🧾 **Classify** — Excel in, predictions out (27 GST voucher types)
- ✅ **Review** — human approval gate: approve, override, escalate
- 📊 **Dashboard** — accuracy, distributions, calibration
- 🛡️ **Fraud screen** — quishing-URL and prompt-injection checks on narrations
- 🔌 **API + CLI** — every UI action exists as a command or endpoint

---

## 1. Quickstart (2 minutes, no model download)

```powershell
git clone https://github.com/OpKnock/VouchPilot.git
cd VouchPilot
pip install -e ".[dev]"
python -m pytest tests/ -q
```

## 2. Run the app

**Option A — double-click (recommended for real users)**

Build the web UI once, then launch everything with one file:

```powershell
cd web; npm install; npm run build; cd ..
double-click VouchPilot.exe        # or: start-vouchpilot.bat
```

Open `http://127.0.0.1:8000` in your browser. The launcher starts the AI
model server if weights are present, then the backend, then stops everything
when you close it. It never opens browser tabs on its own.

**Option B — from source**

```powershell
powershell -ExecutionPolicy Bypass -File start-vouchpilot.ps1
```

**Option C — Docker**

```powershell
python scripts/fetch_model.py --out models
cd web; npm install; npm run build; cd ..
docker compose up --build
```

## 3. Try it on sample data

```powershell
python -m vouch_engine gold --n 270 --seed 7 --out demo\gold
python -m vouch_engine run --input demo\gold.xlsx --out demo\pred.jsonl --scorer keyword
python -m vouch_engine evaluate --gold demo\gold_labels.json --pred demo\pred.jsonl --report demo\eval.json
```

Or upload `demo\gold.xlsx` in the Classify tab and approve rows in Review.

## 4. Scorers — pick your engine

| Scorer | What it is | Needs |
|---|---|---|
| `keyword` (default) | Built-in rules classifier. Instant, surprisingly strong | Nothing |
| `vouchpilot` | Keyword + fraud screening + calibration hooks | Nothing |
| `server` | Qwen3.5-4B AI model, local GPU | `fetch_model.py` + `fetch_server.py` |
| `stub` | Deterministic placeholder for tests | Nothing |

`server` needs 16 GB RAM + 6 GB VRAM recommended (8 GB RAM CPU-only works,
slower). Gemma 4 E4B weights are supported as an alternative bake-off
candidate — see `specs/002-grounding-reliability/results_bakeoff.md`.

## 5. CLI reference

| Command | Does what |
|---|---|
| `gold` | Generate synthetic labelled datasets |
| `run` | Classify a sheet (`--scorer`, `--workers`, `--limit/--offset`, `--exemplars`, `--margin`, `--max-challenge-rate`, `--calibrator`) |
| `evaluate` | Accuracy, macro/micro F1, per-class report, ECE, pairwise F1 |
| `calibrate` | Fit temperature scaling on held-out predictions |
| `agent run` | Full loop: inspect → classify → challenge → human gate → export |
| `agent review-template` | Emit the review queue without exporting |
| `audit` | Retro-audit: recorded vs predicted voucher types |
| `robust` | Perturbation sweeps (missing fields, renamed headers) |
| `doctor` | Dependency, weights and server health check |

Every command prints `WARN:` lines on degradation and never drops rows.

## 6. API reference

Base `http://127.0.0.1:8000`, interactive docs at `/docs`.

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Liveness |
| `/predict` | POST | Classify an uploaded `.xlsx` |
| `/predict-rows` | POST | Classify raw JSON rows |
| `/evaluate` | POST | Score predictions against gold labels |
| `/labels` | GET | The 27 voucher categories |
| `/settings` | GET/POST | Workspace preferences |
| `/system` | GET | Module health, weights, server status |
| `/launcher`, `/desktop-package` | GET | Desktop downloads |

## 7. Configuration

Settings persist to `settings.json`: `scorer`, `endpoint`, `workers`
(1 = bit-identical repro), `challenger`, `fraud`,
`auto_approve_threshold` (review-queue cutoff shown in Review),
`export_format`, `include_evidence`, `theme`.

## 8. Project layout

```
src/vouch_engine/   pipeline, scorers, challenger, calibration, eval,
                    agent loop, FastAPI service
extensions/         fraud screens, auth, RAG evidence, retraining skeleton,
                    vendor reports, tamper pins (optional, default off)
web/src/            premium React UI (build with npm run build)
gold/verify.csv     60 hand-checked rows covering all 27 labels
specs/              design history + honest measurement logs
scripts/            fetch_model.py, fetch_server.py
desktop/            PyInstaller launcher sources (see docs/RELEASING.md)
```

`pilot.py` / `app.py` are the earlier Streamlit apps — still working,
kept for reference.

## 9. Measured results

Qwen3.5-4B Q4 on RTX 4050, fixed seeds:

| Variant | acc | macro-F1 |
|---|---|---|
| Keyword, synthetic 270 | 0.796 | 0.800 |
| Keyword, hand-verified 60 | 0.867 | 0.825 |
| Raw SLM zero-shot (54) | 0.241 | 0.100 |
| Grounded k=5 (54) | 0.259 | 0.114 |
| Challenger (54 / 270) | 0.463 / 0.411 | 0.309 / 0.338 |
| Full stack (54) | 0.500 | 0.349 |

Synthetic gold flatters the keyword baseline (shared vocabulary); the
hand-verified set is the honest check. Full logs in `specs/`.

## 10. Testing

```powershell
python -m pytest tests/ -q        # 146 tests, offline, no weights needed
ruff check src tests scripts extensions app.py pilot.py
cd web; npx tsc --noEmit; npm run build
```

## 11. Requirements

- Python 3.11+, Node.js 18+ (UI build only), ~2 GB free (code + deps)
- Optional AI path: +2.7 GB (Qwen weights) + ~650 MB (server) + NVIDIA GPU

## 12. Roadmap

Rate-capped challenger tuning · per-firm exemplars · human-verified gold
expansion · Tally XML export · sub-1B edge build.

---

Built by **CodeCarto** for the Hacktober Fest open-source AI hackathon
(Challenge 4: voucher classification with open-weight LLMs).
