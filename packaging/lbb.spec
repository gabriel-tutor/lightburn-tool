# PyInstaller spec for LightBurn Bridge.
# Build from repo root:
#     uv run pyinstaller packaging/lbb.spec --clean --noconfirm
# Output:
#     dist/LightBurn Bridge.app   (macOS)
#     dist/LightBurn Bridge/      (Linux/Windows one-folder bundle)
#
# This is a one-folder build (easier to debug). For final distribution,
# switch EXE/COLLECT to a single-file build by passing exclude_binaries=False
# to EXE and dropping the COLLECT call.

# ruff: noqa  -- this is a pyinstaller spec, not regular Python

import sys
from pathlib import Path

REPO_ROOT = Path(SPECPATH).resolve().parent
SRC = REPO_ROOT / "src"

block_cipher = None

a = Analysis(
    [str(SRC / "lbb" / "__main__.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[
        # Bundle the QSS as package data — importlib.resources reads it from here.
        (str(SRC / "lbb" / "ui" / "theme" / "app.qss"), "lbb/ui/theme"),
    ],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # Dev-only — fpdf2 is for fixture generation, not production.
        "fpdf",
        "PIL",
    ],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LightBurn Bridge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="LightBurn Bridge",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="LightBurn Bridge.app",
        bundle_identifier="com.hauke.lightburn-bridge",
        info_plist={
            "NSHighResolutionCapable": True,
            "NSPrincipalClass": "NSApplication",
            "CFBundleShortVersionString": "0.1.0",
            "CFBundleVersion": "0.1.0",
            "LSMinimumSystemVersion": "12.0",
            # Declare we accept PDFs — required for Finder drag-drop into the .app.
            "CFBundleDocumentTypes": [
                {
                    "CFBundleTypeName": "PDF Document",
                    "CFBundleTypeRole": "Editor",
                    "LSHandlerRank": "Alternate",
                    "LSItemContentTypes": ["com.adobe.pdf"],
                },
            ],
        },
    )
