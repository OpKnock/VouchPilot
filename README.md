# VouchPilot

**Offline GST voucher intelligence.** Upload Indian accounting data and VouchPilot returns one of 27 voucher categories per row, with confidence, evidence tags and an honest `needs_review` flag. The browser UI talks only to the local API; classification, document intake and workspace state stay on the machine.

- 🧾 **Classify** — XLSX, XLSM, CSV, PDFs and bill images
- ✅ **Review** — human approval gate: approve, override, escalate
- 📊 **Dashboard** — live distribution, confidence and saved runs
- 🛡️ **Fraud screen** — quishing-URL and prompt-injection checks in VouchPilot+ mode
- 🔌 **API + CLI** — core workflows are available without the web UI

---

## 1. Quickstart

```powershell
git clone https://github.com/OpKnock/VouchPilot.git
cd VouchPilot
pip install -e ".[dev]"
python -m pytest tests/ -q
```

## 2. Run the app

Build the React UI once, then launch the local FastAPI server:

```powershell
cd web
npm install
npm run build
cd ..
powershell -ExecutionPolicy Bypass -File start-vouchpilot.ps1
```

Open `http://127.0.0.1:8000`.

The launcher starts the optional local llama.cpp server when a GGUF weight and server binary are available. Keyword and VouchPilot+ modes do not require model weights.

**Photos, scans and PDFs**

Text PDFs are parsed directly. Scanned PDFs and bill photos use Tesseract only when the external binary is installed; otherwise VouchPilot fails loudly instead of silently producing empty OCR.

```powershell
winget install UB-Mannheim.TesseractOCR
python scripts/fetch_tessdata.py
```

Messy workbooks with title rows, merged cells, Hindi/Marathi headers and multiple sheets are routed through the resilient workbook reader before classification.

**Docker**

The production image builds the React UI and Python runtime together; no pre-built `web/dist` is required.

```powershell
docker build -t vouchpilot .
docker run --rm -p 8000:8000 vouchpilot
```

Open `http://127.0.0.1:8000`.

The compose file starts the app without a model server:

```powershell
docker compose up --build
```

For the optional local llama.cpp service (with `models/Qwen3.5-4B-Q4_K_M.gguf` present):

```powershell
docker compose --profile llm up --build
```

Set `VOUCH_MAX_UPLOAD_BYTES` to change the server-side upload ceiling (default 50 MiB).

## 3. Try sample data

```powershell
python -m vouch_engine gold --n 270 --seed 7 --out demo\gold
python -m vouch_engine run --input demo\gold.xlsx --out demo\pred.jsonl --scorer keyword
python -m vouch_engine evaluate --gold demo\gold_labels.json --pred demo\pred.jsonl --report demo\eval.json
```

Or upload `demo\gold.xlsx` in Classify and approve the uncertain rows in Review.

## 4. Scorers

| Scorer | What it is | Needs |
|---|---|---|
| `keyword` | Fast built-in rules classifier | Nothing |
| `vouchpilot` | Keyword + fraud/injection screening hooks | Nothing |
| `server` | Local Qwen3.5-4B AI model | GGUF weights + llama.cpp |
| `stub` | Deterministic placeholder for tests | Nothing |

## 5. API

Base URL: `http://127.0.0.1:8000`  
Interactive docs: `http://127.0.0.1:8000/docs`

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Liveness + module import checks |
| `/predict` | POST | Classify XLSX, XLSM, CSV, PDF or supported bill image |
| `/predict-rows` | POST | Classify raw JSON rows |
| `/evaluate` | POST | Compare predictions against gold labels |
| `/labels` | GET | Return all 27 voucher categories |
| `/settings` | GET/POST | Persist local workspace preferences |
| `/system` | GET | Module health, local model endpoint and weights |
| `/launcher` | GET | Download launcher when packaged |
| `/desktop-package` | GET | Download packaged desktop bundle when built |

## 6. Configuration

Settings persist locally in `settings.json`:

`scorer`, `endpoint`, `workers`, `challenger`, `fraud`, `auto_approve_threshold`, `export_format`, `include_evidence`, `theme`.

Supported export formats are `jsonl` and `csv`. The API also retains the legacy XLSX writer for CLI automation.

## 7. Project layout

```
src/vouch_engine/   pipeline, scorers, challenger, calibration, API, CLI
extensions/         fraud screens and optional extension modules
web/src/            React/Vite application
gold/verify.csv     hand-checked verification rows
specs/              implementation notes and measurement logs
scripts/            model, server and OCR resource helpers
desktop/            PyInstaller launcher sources
tests/              unit and integration regression coverage
```

`pilot.py` / `app.py` are earlier Streamlit applications retained as reference paths. The supported desktop web experience is the React/Vite frontend served by FastAPI.

## 8. Measurement notes

The keyword baseline is intentionally documented separately from the local SLM path. Synthetic gold data can overstate performance because the generated descriptions share vocabulary with the rules. Use the hand-verified set for honest comparisons.

## 9. Verification

```powershell
python -m pytest tests/ -q
ruff check src tests scripts extensions app.py pilot.py
cd web
npx tsc --noEmit
npm run build
```

The repository CI runs the Python test suite and the frontend build on pushes and pull requests.

## License

See the repository for the current license and third-party model terms.