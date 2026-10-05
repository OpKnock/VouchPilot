# Releasing VouchPilot desktop

## What ships

- `VouchPilot.exe` (~10 MB PyInstaller launcher, no console window)
- `VouchPilot-Desktop.zip` from `GET /desktop-package`: exe + `.bat` +
  `.ps1` + README with prerequisites (Python 3.11+, one pip line, weights)

The exe is a launcher, not a full bundle: the 7.7 GB models, the llama
binaries and the Python deps live next to it. A true single-file bundle
would exceed 2 GB and break on most machines, so this is the honest shape.

## Build the exe

```powershell
cd desktop
python -m PyInstaller --onefile --noconsole --name VouchPilot launcher.py
Copy-Item dist\VouchPilot.exe ..\VouchPilot.exe
```

## Rules

- Never auto-open browser tabs from the exe or scripts (past incident).
- Never commit `VouchPilot.exe`, `desktop/build|dist`, `models/*.gguf`,
  `tools/llama-server/`, `web/dist` (see .gitignore).
- The exe must work from any working directory (absolute paths only).
- After rebuilding: API up + UI shell served + full pytest before sharing.


## Web deployment

The recommended deployment artifact is the Docker image. It builds the Vite frontend and includes the FastAPI backend plus top-level extensions. No model weights are baked into the image.

For a CPU-only deployment, use the image without the optional `llm` compose profile and keep the workspace on `keyword` or `vouchpilot` mode. For local model inference, mount the GGUF under `models/` and start the optional compose profile.

Before release, verify:
- `GET /health` returns HTTP 200.
- `GET /labels` reports 27 labels.
- A CSV and messy XLSX upload both produce predictions.
- Review decisions update the saved run status.
- Production build and Docker image build pass in CI.
