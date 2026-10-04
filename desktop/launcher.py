"""VouchPilot desktop launcher (frozen to VouchPilot.exe with PyInstaller).

Never opens a browser on its own: it prints the URL and the user opens it.
Pass --open-browser once to open a single tab deliberately.
"""
import os
import subprocess
import sys
import time
import urllib.request

if getattr(sys, "frozen", False):
    ROOT = os.path.dirname(os.path.abspath(sys.executable))
else:
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LLAMA = os.path.join(ROOT, "tools", "llama-server", "bin", "llama-server.exe")
API = "http://127.0.0.1:8000/health"


def healthy(url, timeout=3):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def _python():
    import shutil

    if getattr(sys, "frozen", False):
        found = shutil.which("python") or shutil.which("python3")
        if found:
            return found
        raise RuntimeError("python not found on PATH (needed for the API backend)")
    return sys.executable


def main():
    procs = []
    try:
        models_dir = os.path.join(ROOT, "models")
        candidates = [(os.path.getsize(os.path.join(models_dir, f)), f)
                      for f in os.listdir(models_dir) if f.endswith(".gguf")] \
            if os.path.isdir(models_dir) else []
    except Exception:
        candidates = []
    if candidates and not healthy(API) and os.path.exists(LLAMA):
        gguf = sorted(candidates)[0][1]
        procs.append(subprocess.Popen(
            [LLAMA, "-m", os.path.join(ROOT, "models", gguf), "--host", "127.0.0.1",
             "--port", "8080", "-c", "4096", "--n-gpu-layers", "99",
             "--cache-type-k", "q8_0", "--cache-type-v", "q8_0", "--log-disable"],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        for _ in range(60):
            time.sleep(5)
            if healthy(API.replace("8000", "8080")):
                break
    env = dict(os.environ)
    api = subprocess.Popen([_python(), "-m", "uvicorn", "vouch_engine.api:create_app",
                            "--factory", "--host", "127.0.0.1", "--port", "8000"],
                           cwd=ROOT, env={**env, "PYTHONPATH": os.path.join(ROOT, "src")},
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    procs.append(api)
    for _ in range(30):
        time.sleep(2)
        if healthy(API):
            break
    print("VouchPilot running at http://127.0.0.1:8000/ - open it in your browser.")
    print("Close this window to stop.")
    if "--open-browser" in sys.argv[1:]:
        import webbrowser

        webbrowser.open("http://127.0.0.1:8000/")
    try:
        api.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    main()
