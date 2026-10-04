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
