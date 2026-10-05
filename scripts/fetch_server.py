# Fetch a pinned llama.cpp Windows server build (mirrors the manual setup).
# Downloads b11374 CUDA 12.4 server + cudart runtime into tools/llama-server/bin.
# Use --cpu-only on machines without an NVIDIA GPU.

from __future__ import annotations

import argparse
import os
import sys
import urllib.request
import zipfile

TAG = 'b11374'
BASE = 'https://github.com/ggerganov/llama.cpp/releases/download/%s/' % (TAG,)
CUDA_FILES = ['llama-%s-bin-win-cuda-12.4-x64.zip' % (TAG,),
               'cudart-llama-bin-win-cuda-12.4-x64.zip']
CPU_FILES = ['llama-%s-bin-win-cpu-x64.zip' % (TAG,)]


def download(url: str, path: str) -> None:
    print('downloading %s ...' % (url,), flush=True)
    urllib.request.urlretrieve(url, path)
    print('saved %s (%d MB)' % (path, os.path.getsize(path) // 1000000), flush=True)


def safe_extract(archive: zipfile.ZipFile, target: str | os.PathLike) -> None:
    """Extract an archive only when every member stays under *target*."""
    root = os.path.realpath(os.fspath(target))
    for member in archive.infolist():
        destination = os.path.realpath(os.path.join(root, member.filename))
        if os.path.commonpath([root, destination]) != root:
            raise ValueError(f"unsafe archive path: {member.filename}")
    archive.extractall(root)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog='python scripts/fetch_server.py')
    parser.add_argument('--out', default=os.path.join('tools', 'llama-server', 'bin'))
    parser.add_argument('--cpu-only', action='store_true')
    args = parser.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    files = CPU_FILES if args.cpu_only else CUDA_FILES
    for name in files:
        dest = os.path.join(args.out, name)
        if os.path.exists(dest):
            print('exists, skipping: %s' % (dest,))
        else:
            try:
                download(BASE + name, dest)
            except Exception as exc:
                print('ERROR: download failed (%s)' % (exc,), file=sys.stderr)
                return 2
        try:
            with zipfile.ZipFile(dest) as archive:
                safe_extract(archive, args.out)
        except Exception as exc:
            print('ERROR: extract failed (%s)' % (exc,), file=sys.stderr)
            return 2
    server = os.path.join(args.out, 'llama-server.exe')
    print('server ready: %s (exists=%s)' % (server, os.path.exists(server)))
    print('launch: %s -m models/<model>.gguf --host 127.0.0.1 --port 8080 -c 4096 --n-gpu-layers 99' % (server,))
    return 0


if __name__ == '__main__':
    sys.exit(main())

