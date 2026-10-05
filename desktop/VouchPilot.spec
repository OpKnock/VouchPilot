# PyInstaller spec for a standalone Windows VouchPilot executable.
# Build from repository root after building web/dist:
#   pyinstaller desktop/VouchPilot.spec --noconfirm

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path.cwd().resolve()
WEB_DIST = ROOT / "web" / "dist"

hiddenimports = (
    collect_submodules("vouch_engine")
    + collect_submodules("extensions")
    + [
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
    ]
)

a = Analysis(
    [str(ROOT / "desktop" / "launcher.py")],
    pathex=[str(ROOT / "src"), str(ROOT)],
    binaries=[],
    datas=[(str(WEB_DIST), "web/dist")],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="VouchPilot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
