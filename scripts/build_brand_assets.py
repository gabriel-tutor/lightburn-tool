"""Generate Flanacom branding assets (ICO + PNG header logo) from the source JPG.

Run from repo root:
    uv run python scripts/build_brand_assets.py

Outputs:
    assets/flanacom.ico         — multi-resolution Windows icon (bag-only, square crop)
    assets/flanacom-logo.png    — full wordmark, ~64px tall, for the app header
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_WORDMARK = REPO_ROOT / "flanacom-logo.jpg"       # full horizontal lockup
SOURCE_ICON = REPO_ROOT / "flanacom-logo-icon.png"      # square bag mark, transparent bg
# Inside the package so importlib.resources finds it in dev AND in the
# PyInstaller bundle (the spec bundles src/lbb/ui/assets via `datas`).
ASSETS = REPO_ROOT / "src" / "lbb" / "ui" / "assets"
_ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
_HEADER_HEIGHT = 64


def main() -> None:
    ASSETS.mkdir(exist_ok=True)

    # ── 1. ICO (Windows app icon, also used by Qt setWindowIcon) ────────────
    # Use the dedicated icon source (just the shopping-bag mark). Pad to
    # square if needed so each ICO resolution stays well-proportioned.
    icon = Image.open(SOURCE_ICON).convert("RGBA")
    w, h = icon.size
    side = max(w, h)
    if (w, h) != (side, side):
        square = Image.new("RGBA", (side, side), (255, 255, 255, 0))
        square.paste(icon, ((side - w) // 2, (side - h) // 2))
        icon = square
    ico_path = ASSETS / "flanacom.ico"
    icon.save(ico_path, sizes=[(s, s) for s in _ICO_SIZES])

    # ── 2. Header PNG (in-app header) ───────────────────────────────────────
    # Full horizontal wordmark scaled to a usable header height.
    wordmark = Image.open(SOURCE_WORDMARK).convert("RGBA")
    ww, wh = wordmark.size
    target_h = _HEADER_HEIGHT
    target_w = int(ww * target_h / wh)
    header = wordmark.resize((target_w, target_h), Image.LANCZOS)
    png_path = ASSETS / "flanacom-logo.png"
    header.save(png_path)

    print(f"  ✓ {ico_path.relative_to(REPO_ROOT)}  ({len(_ICO_SIZES)} resolutions, {side}×{side})")
    print(f"  ✓ {png_path.relative_to(REPO_ROOT)}  ({target_w}×{target_h})")


if __name__ == "__main__":
    main()
