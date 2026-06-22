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
from PyInstaller.utils.hooks import collect_all

REPO_ROOT = Path(SPECPATH).resolve().parent
SRC = REPO_ROOT / "src"
ASSETS = SRC / "lbb" / "web" / "assets"

block_cipher = None

webview_datas, webview_binaries, webview_hiddenimports = collect_all('webview')

a = Analysis(
    [str(SRC / "lbb" / "__main__.py")],
    pathex=[str(SRC)],
    binaries=webview_binaries,
    datas=[
        # Web shell assets.
        (str(ASSETS / "index.html"), "lbb/web/assets"),
        (str(ASSETS / "app.css"), "lbb/web/assets"),
        (str(ASSETS / "app.js"), "lbb/web/assets"),
        (str(ASSETS / "bridge-client.js"), "lbb/web/assets"),
        # Brand assets (Flanacom icon + header logo).
        (str(ASSETS / "flanacom.ico"), "lbb/web/assets"),
        (str(ASSETS / "flanacom-logo.png"), "lbb/web/assets"),
    ] + webview_datas,
    hiddenimports=webview_hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # Dev-only — fpdf2 is for fixture generation, not production.
        "fpdf",
        # NOTE: PIL is NOT excluded — render_thumbnail_png needs it at runtime.
        # Excluding it caused a silent crash where Qt swallowed the ImportError
        # and the UI appeared to ignore PDF selection.
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
    name="Fulfillment Studio",
    icon=str(ASSETS / "flanacom.ico"),
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
    name="Fulfillment Studio",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Fulfillment Studio.app",
        bundle_identifier="com.flanacom.tool",
        icon=str(ASSETS / "flanacom.ico"),
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
