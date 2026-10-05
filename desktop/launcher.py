"""VouchPilot desktop launcher for source and standalone Windows builds.

Source mode starts the API as a child process. Frozen/PyInstaller mode runs the
FastAPI server in the bundled Python runtime, so end users do not need Python.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))
APP_ROOT = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parents[1]
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", APP_ROOT))
API_URL = "http://127.0.0.1:8000/"
API_HEALTH = API_URL + "health"
LLAMA_HEALTH = "http://127.0.0.1:8080/health"
LOG_PATH = APP_ROOT / "VouchPilot.log"


def _log(message: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass
    if not FROZEN:
        print(line)


def _error(message: str) -> None:
    _log("ERROR: " + message)
    if FROZEN:
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, "VouchPilot", 0x10)
        except Exception:
            pass


def healthy(url: str, timeout: float = 3) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status == 200
    except Exception:
        return False


def wait_for_healthy(url: str, attempts: int = 30, delay: float = 2) -> bool:
    for attempt in range(max(1, attempts)):
        if healthy(url):
            return True
        if attempt + 1 < attempts:
            time.sleep(delay)
    return False


def _model_candidates() -> list[Path]:
    models_dir = APP_ROOT / "models"
    try:
        return sorted(
            (path for path in models_dir.glob("*.gguf") if path.is_file()),
            key=lambda path: path.stat().st_size,
        )
    except OSError:
        return []


def _start_llama(procs: list[subprocess.Popen]) -> None:
    candidates = _model_candidates()
    llama = APP_ROOT / "tools" / "llama-server" / "bin" / "llama-server.exe"
    if not candidates or healthy(LLAMA_HEALTH) or not llama.exists():
        return

    model = candidates[0]
    _log(f"Starting local model server with {model.name}")
    procs.append(
        subprocess.Popen(
            [
                str(llama),
                "-m",
                str(model),
                "--host",
                "127.0.0.1",
                "--port",
                "8080",
                "-c",
                "4096",
                "--n-gpu-layers",
                "99",
                "--cache-type-k",
                "q8_0",
                "--cache-type-v",
                "q8_0",
                "--log-disable",
            ],
            cwd=str(APP_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    )
    if not wait_for_healthy(LLAMA_HEALTH, attempts=60, delay=5):
        _log("Local model server did not become healthy; keyword/VouchPilot+ modes remain available.")


def _open_browser() -> None:
    try:
        webbrowser.open(API_URL)
    except Exception as exc:
        _log(f"Browser open failed: {exc}")


def _run_frozen() -> int:
    import uvicorn

    from vouch_engine.api import create_app

    procs: list[subprocess.Popen] = []
    os.environ["VOUCHPILOT_APP_ROOT"] = str(APP_ROOT)
    os.environ["VOUCHPILOT_WEB_ROOT"] = str(RESOURCE_ROOT / "web" / "dist")
    try:
        _start_llama(procs)

        # The standalone build keeps the API and UI in the same executable.
        if "--no-browser" not in sys.argv[1:]:
            timer = threading.Timer(1.25, _open_browser)
            timer.daemon = True
            timer.start()

        _log("Starting standalone VouchPilot on http://127.0.0.1:8000/")
        uvicorn.run(
            create_app(),
            host="127.0.0.1",
            port=8000,
            log_level="warning",
            access_log=False,
        )
        return 0
    finally:
        for proc in procs:
            try:
                proc.terminate()
            except Exception:
                pass


def _python() -> str:
    if FROZEN:
        raise RuntimeError("standalone mode does not require a Python executable")
    return sys.executable


def main() -> int:
    if FROZEN:
        return _run_frozen()

    procs: list[subprocess.Popen] = []
    try:
        _start_llama(procs)
        env = dict(os.environ)
        env["VOUCHPILOT_APP_ROOT"] = str(APP_ROOT)
        api = subprocess.Popen(
            [
                _python(),
                "-m",
                "uvicorn",
                "vouch_engine.api:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            cwd=str(APP_ROOT),
            env={**env, "PYTHONPATH": str(APP_ROOT / "src")},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        procs.append(api)

        if not wait_for_healthy(API_HEALTH, attempts=30, delay=2):
            _error(
                "VouchPilot could not start its local API. "
                "Check VouchPilot.log and the installed Python dependencies."
            )
            return 1

        _log("VouchPilot is ready at http://127.0.0.1:8000/")
        if "--no-browser" not in sys.argv[1:]:
            _open_browser()
        api.wait()
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        _error(str(exc))
        return 1
    finally:
        for proc in procs:
            try:
                proc.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
