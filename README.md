# Fulfillment Studio

An order-fulfillment dashboard desktop app for a laser-engraving workshop. Operators see all pending orders grouped by product type, click to open a side's design PDF in LightBurn, mark engraved sides, and ship orders — all in a pywebview window backed by the existing direct-open LightBurn engine.

## Status

126 tests passing, 4 skipped. Fulfillment Studio UI live on `feature/fulfillment-studio`. See [HANDOFF.md](HANDOFF.md) for the full operating guide, architecture, and troubleshooting.

## Documentation

- **Handoff (start here):** [`HANDOFF.md`](HANDOFF.md) — Windows setup, operating guide, architecture, troubleshooting
- **Designer PDF spec:** [`docs/designer-pdf-spec.md`](docs/designer-pdf-spec.md)
- **Windows build details:** [`docs/build-windows.md`](docs/build-windows.md)

## Development

```bash
# install deps
uv sync --dev

# run the app from source (opens the pywebview dashboard window)
uv run python -m lbb

# tests
uv run pytest

# lint
uv run ruff check
uv run lint-imports
```

## Architecture

Hexagonal (core / ports / adapters / app) plus a `web/` layer (pywebview window + `JsApiBridge` + HTML/CSS/JS assets). Python 3.12, pywebview (Edge WebView2 on Windows), SQLite. Single language, single process.

## Building a distributable binary

```bash
uv sync --dev
uv run pyinstaller packaging/lbb.spec --clean --noconfirm
# Windows → dist\Fulfillment Studio\Fulfillment Studio.exe
```

**Windows builds must happen on a Windows host** — PyInstaller doesn't
cross-compile. See [`docs/build-windows.md`](docs/build-windows.md) for
details.

The bundle is currently unsigned. For client distribution, Authenticode-sign
the `.exe` on Windows to suppress SmartScreen warnings.

