# LightBurn Bridge

A cross-platform desktop tool that loads PDFs into LightBurn with the correct material/speed/power settings auto-applied based on the product SKU encoded in the filename. Operator confirms on screen and presses Start on the laser.

## Status

Pre-MVP. Phase 0 scaffolding complete. See `docs/plans/` for full design and implementation plan.

## Documentation

- **Design:** [`docs/plans/2026-05-16-lightburn-bridge-design.md`](docs/plans/2026-05-16-lightburn-bridge-design.md)
- **MVP plan:** [`docs/plans/2026-05-16-lightburn-bridge-mvp-plan.md`](docs/plans/2026-05-16-lightburn-bridge-mvp-plan.md)
- **Designer PDF spec:** [`docs/designer-pdf-spec.md`](docs/designer-pdf-spec.md)

## Development

```bash
# install core deps (engine, tests, lint) — fast
uv sync

# install UI deps (PySide6, ~420MB) — slower, only needed to run the app
uv sync --extra ui

# run app (requires --extra ui synced first)
uv run python -m lbb

# tests
uv run pytest

# lint
uv run ruff check
uv run lint-imports
```

## Architecture

Hexagonal (core / ports / adapters / app / ui). Python 3.12, PySide6, lxml, pypdfium2, SQLite. Single language, single process.

## Building a distributable binary

```bash
uv sync --extra ui --dev
uv run pyinstaller packaging/lbb.spec --clean --noconfirm

# macOS  → open "dist/LightBurn Bridge.app"
# Linux/Windows → run "dist/LightBurn Bridge/LightBurn Bridge"
```

**Windows builds must happen on a Windows host** — PyInstaller doesn't
cross-compile. See [`docs/build-windows.md`](docs/build-windows.md) for the
three paths: build directly on a Windows laptop, use GitHub Actions to
build remotely (artifact download), or run a Windows VM.

The macOS bundle is currently unsigned. For distribution to client machines, code-sign with `codesign` and notarize via `notarytool` before shipping.

