"""Download a GGUF model and print the llama-server launch command.

No download happens on import; all work is inside main()/helpers.
"""

from __future__ import annotations

import argparse
import json
import urllib.request


def pick_gguf(files: list[str]) -> str | None:
    """Prefer *Q4_K_M* GGUF, else first GGUF file."""
    ggufs = [f for f in files if f.lower().endswith(".gguf")]
    if not ggufs:
        return None
    for f in ggufs:
        if "Q4_K_M" in f:
            return f
    return sorted(ggufs)[0]


def check_server(endpoint: str, timeout: int = 10) -> bool:
    """Ping {endpoint}/health; True on HTTP 200."""
    url = endpoint.rstrip("/") + "/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def launch_command(model_path: str, endpoint: str = "http://127.0.0.1:8080") -> str:
    """Render the llama-server launch command for a local GGUF file."""
    host, _, port = endpoint.replace("http://", "").replace("https://", "").partition(
        ":"
    )
    host = host or "127.0.0.1"
    port = port or "8080"
    return f'llama-server -m "{model_path}" --host {host} --port {port}'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch GGUF weights for VouchIQ.")
    parser.add_argument("--repo", default="unsloth/Qwen3.5-4B-GGUF")
    parser.add_argument("--out", default="models/")
    parser.add_argument("--endpoint", default="http://127.0.0.1:8080")
    parser.add_argument("--check", action="store_true", help="Ping {endpoint}/health")
    args = parser.parse_args(argv)

    if args.check:
        ok = check_server(args.endpoint)
        print(json.dumps({"endpoint": args.endpoint, "healthy": ok}))
        return 0 if ok else 1

    from huggingface_hub import hf_hub_download, list_repo_files

    files = list(list_repo_files(args.repo))
    chosen = pick_gguf(files)
    if chosen is None:
        print(f"No .gguf files found in repo {args.repo}")
        return 1
    print(f"Selected: {chosen}")
    path = hf_hub_download(repo_id=args.repo, filename=chosen, local_dir=args.out)
    print(f"Downloaded to: {path}")
    print(launch_command(path, args.endpoint))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
