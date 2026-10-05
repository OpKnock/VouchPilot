# VouchPilot

**Offline-first GST voucher intelligence for Indian accounting workflows.**

VouchPilot turns messy accounting records into one of **27 GST voucher categories**, then shows confidence, evidence, alternatives, and a human review path before export.

It is built for three operating modes:

- **Desktop / offline** — a normal Windows user can run VouchPilot without Python or Node.
- **Developer / self-hosted** — run the FastAPI + React application locally or in Docker.
- **Hosted / SaaS** — point the React client at a private VouchPilot API for internal or private-beta use.

> **Important:** VouchPilot is an accounting classification tool, not a tax filing service or a regulatory certification. Its validation reports are engineering evidence and should not be presented as GST, audit, or regulatory approval.

---

## What VouchPilot does

### Classify

Upload common Indian accounting inputs:

- XLSX / XLSM
- CSV
- PDFs
- Bill images

The ingestion layer handles messy headers, title rows, merged cells, multiple sheets, and multilingual accounting data before classification.

### Explain

Each prediction can include:

- voucher category
- confidence
- top alternatives
- evidence tags
- needs_review
- row-level review status

### Review

Uncertain rows can be sent through a human checkpoint:

**Approve → Override → Escalate**

Exports stay behind the review workflow so teams can inspect edge cases before producing a final output.

### Protect

The application includes defensive controls for:

- malformed model responses
- unavailable local model servers
- oversized uploads
- oversized images / PDFs
- excessive worker counts
- unsafe archive extraction
- spreadsheet formula injection
- untrusted persisted browser data
- remote LLM endpoints that are not explicitly trusted

---

# For normal Windows users

You do **not** need to install Python, Node.js, npm, or clone the repository.

The supported end-user package is:

**VouchPilot-Windows.zip**

It contains a standalone **VouchPilot.exe** built for Windows.

### Install

1. Download the latest Windows package from **GitHub Releases**.
2. Extract the ZIP.
3. Double-click **VouchPilot.exe**.
4. VouchPilot opens its local workspace in your browser.
5. Upload your accounting file and start a classification run.

The executable contains the application runtime and built web UI.

For scripted installation, the repository also includes:

**Install-VouchPilot.ps1**

and

**Install-VouchPilot.bat**

See **desktop/INSTALL.md** for the normal-user guide.

### Local AI is optional

The default **keyword** scorer works without downloading a model.

The optional **server** scorer can use a local GGUF model through llama.cpp. VouchPilot does not silently substitute fake predictions when a required model server is unavailable.

---

# Developer quickstart

## 1. Clone

~~~powershell
git clone https://github.com/OpKnock/VouchPilot.git
cd VouchPilot
~~~

## 2. Install the Python package

~~~powershell
pip install -e ".[dev]"
~~~

## 3. Run the backend tests

~~~powershell
python -m pytest tests/ -q
~~~

## 4. Build the web UI

~~~powershell
cd web
npm install
npm run build
cd ..
~~~

## 5. Start VouchPilot

~~~powershell
powershell -ExecutionPolicy Bypass -File start-vouchpilot.ps1
~~~

Open:

**http://127.0.0.1:8000**

API documentation:

**http://127.0.0.1:8000/docs**

---

# Docker

VouchPilot can build the React UI and Python runtime together.

~~~powershell
docker build -t vouchpilot .
docker run --rm -p 8000:8000 vouchpilot
~~~

Or:

~~~powershell
docker compose up --build
~~~

The optional llama.cpp profile can be enabled when a compatible GGUF model is mounted in models/:

~~~powershell
docker compose --profile llm up --build
~~~

---

# Scorers

| Scorer | Description | Model required |
|---|---|---:|
| keyword | Fast built-in accounting rules baseline | No |
| vouchpilot | Rules plus fraud / injection screening hooks | No |
| server | Local open-weight model through llama.cpp | Yes |
| stub | Deterministic test scorer | No |

The **server** scorer is intentionally fail-closed: if the local model server is unavailable or returns an unusable response, VouchPilot returns an explicit failure instead of fabricating a plausible voucher label.

---

# Enterprise accounting validation

VouchPilot includes a repeatable validation harness:

~~~powershell
python scripts/validate_enterprise.py --gold <labelled-dataset.csv>
~~~

You can also validate precomputed predictions:

~~~powershell
python scripts/validate_enterprise.py \
  --gold <labelled-dataset.csv> \
  --predictions <predictions.jsonl> \
  --dataset-type production
~~~

The report measures:

| Measurement | Why it matters |
|---|---|
| Accuracy | Overall classification correctness |
| Macro-F1 | Prevents strong classes from hiding weak classes |
| Per-class precision / recall / F1 | Shows which voucher categories need work |
| Review rate | Measures human-review load |
| High-confidence error rate | Detects dangerous overconfidence |
| Expected calibration error | Measures confidence calibration |
| Class coverage | Detects incomplete benchmark coverage |
| Unknown labels | Detects taxonomy mismatches |

The command can run keyword, vouchpilot, or server scoring through the scorer option.

For a server-based run, provide a local endpoint such as http://127.0.0.1:8080.

### Validation tiers

**Synthetic** → regression testing only.

**Hand-verified** → useful for engineering benchmarks, but still subject to sampling bias.

**Production-labelled** → representative enterprise data, independently labelled, with a documented sampling strategy.

Only the production-labelled tier can satisfy the tool's **enterprise_ready** condition.

See **specs/enterprise-validation.md**.

### Current repository benchmark

The repository's current hand-verified benchmark contains **60 labelled rows**.

Its latest CI report was:

| Metric | Result |
|---|---:|
| Accuracy | **86.67%** |
| Macro-F1 | **82.53%** |
| Review rate | **13.33%** |
| High-confidence error rate | **3.33%** |
| ECE | **0.0767** |
| Engineering gate | **PASS** |
| Enterprise-ready | **NO** |

The final result is intentionally **NO** because a small hand-verified benchmark is not enough to establish enterprise readiness.

---

# SaaS / hosted mode

VouchPilot remains local-first by default, but the web client can connect to a private hosted API.

Configure the frontend with:

~~~env
VITE_API_URL=https://api.example.com
VITE_RUNTIME_MODE=hosted
VITE_DESKTOP_DOWNLOAD_URL=https://github.com/OpKnock/VouchPilot/releases/latest/download/VouchPilot-Windows.zip
~~~

Configure the API with:

~~~env
VOUCH_SAAS_MODE=1
VOUCH_CORS_ORIGINS=https://app.example.com
~~~

Hosted mode is designed for a private deployment or beta, not as a claim that the repository already provides a complete multi-tenant SaaS platform.

For a real production SaaS deployment, put the API behind an authentication / identity layer, TLS, rate limiting, logging, and an appropriate reverse proxy or WAF.

See **docs/saas.md**.

---

# API

Base URL:

**http://127.0.0.1:8000**

| Endpoint | Method | Purpose |
|---|---|---|
| /health | GET | Liveness and module health |
| /predict | POST | Classify an uploaded accounting file |
| /predict-rows | POST | Classify raw JSON rows |
| /audit | POST | Compare recorded voucher types with predictions |
| /evaluate | POST | Compare predictions with gold labels |
| /labels | GET | Return the 27 voucher categories |
| /settings | GET / POST | Workspace settings |
| /system | GET | Runtime, model and module status |
| /launcher | GET | Packaged launcher information |
| /desktop-package | GET | Packaged desktop download path |

Interactive OpenAPI docs are available at:

**http://127.0.0.1:8000/docs**

---

# Configuration

Local workspace settings include:

**scorer**, **endpoint**, **workers**, **challenger**, **fraud**, **auto_approve_threshold**, **export_format**, **include_evidence**, and **theme**.

Useful environment variables include:

| Variable | Purpose |
|---|---|
| VOUCH_MAX_UPLOAD_BYTES | Server-side upload ceiling |
| VOUCH_LLM_ALLOWED_HOSTS | Additional explicitly trusted model hosts |
| VOUCH_SAAS_MODE | Enable hosted/private-beta behavior |
| VOUCH_CORS_ORIGINS | Allowed hosted frontend origins |
| VOUCHPILOT_APP_ROOT | Runtime application root for packaged builds |
| VOUCHPILOT_WEB_ROOT | Runtime React build directory for packaged builds |

Worker concurrency is capped server-side to prevent an untrusted request from creating an unbounded amount of work.

---

# OCR and document intake

Text PDFs can be parsed directly.

Scanned PDFs and bill photos use Tesseract when the external OCR binary and language data are installed.

Example Windows setup:

~~~powershell
winget install UB-Mannheim.TesseractOCR
python scripts/fetch_tessdata.py
~~~

The default OCR language set includes:

- English
- Hindi
- Marathi
- Gujarati

If OCR is unavailable, VouchPilot reports the problem instead of silently treating missing OCR text as valid accounting data.

---

# Try sample data

Generate a deterministic demo dataset:

~~~powershell
python -m vouch_engine gold --n 270 --seed 7 --out demo\gold
python -m vouch_engine run --input demo\gold.xlsx --out demo\pred.jsonl --scorer keyword
python -m vouch_engine evaluate --gold demo\gold_labels.json --pred demo\pred.jsonl --report demo\eval.json
~~~

You can also upload demo\gold.xlsx through the web workspace and review uncertain rows.

---

# Project structure

~~~
src/vouch_engine/        Core pipeline, scorers, calibration, API and CLI
extensions/              Fraud screens and optional extension modules
web/src/                 React / Vite application
gold/                    Verification and benchmark data
specs/                   Validation and implementation specifications
scripts/                 Validation, server and OCR helpers
desktop/                 Standalone Windows launcher + PyInstaller spec
tests/                   Unit and integration regression coverage
~~~

The older pilot.py / app.py Streamlit paths are retained for compatibility/reference. The supported product UI is the React frontend served by FastAPI.

---

# Verification

The repository CI checks the main product surfaces:

- Python test suite
- Python wheel + import smoke tests
- Ruff static checks
- React TypeScript checks
- React production build
- Docker build
- Enterprise validation benchmark
- Windows standalone executable build

Run the core checks locally with:

~~~powershell
python -m pytest tests/ -q
ruff check src tests scripts extensions app.py pilot.py

cd web
npx tsc --noEmit
npm run build
~~~

The Windows release workflow produces a downloadable **VouchPilot-Windows.zip** artifact for tagged releases.

---

# Project status

**VouchPilot is production-hardened at the application/code level, with a verified Windows packaging path and a repeatable enterprise validation framework.**

The remaining enterprise work is evidence and operations rather than pretending the current benchmark is sufficient:

- collect representative, independently labelled enterprise accounting data;
- establish customer-specific accuracy / review / calibration thresholds;
- complete security, authentication, retention, and deployment controls for a public SaaS;
- obtain professional accounting / tax review before making compliance-oriented claims.

---

## License

See the repository for the current license and third-party model terms.
