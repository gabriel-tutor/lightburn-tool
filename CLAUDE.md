# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

For an end-to-end project overview (setup, status, what's built, what's NOT,
operating guide, troubleshooting), read **[HANDOFF.md](HANDOFF.md)** first —
it's the human-facing source of truth and answers most questions without
needing to read code.

## Commands

```bash
# Setup (first time on a fresh clone)
uv sync --dev

# Run the app from source (opens the pywebview Fulfillment Studio window)
uv run python -m lbb

# Tests
uv run pytest                                    # everything
uv run pytest tests/integration/                 # one directory
uv run pytest tests/unit/adapters/ -v            # one directory
uv run pytest tests/integration/test_pipeline.py::test_happy_path_loads_to_lightburn -v   # one test
uv run pytest -k "fulfillment"                   # by name pattern

# Lint / architecture checks (both run on every commit via pre-commit)
uv run ruff check                                # style + many bug-class lints
uv run ruff format                               # autoformatter (also re-runs on commit)
uv run lint-imports                              # architectural contract enforcement

# Build the distributable
uv run pyinstaller packaging/lbb.spec --clean --noconfirm
# → dist\Fulfillment Studio\Fulfillment Studio.exe  (Windows)

# Regenerate test artifacts after a deliberate template/builder change
uv run python scripts/generate_fixtures.py       # PDF fixtures
uv run python scripts/regenerate_goldens.py      # byte-stable .lbrn2 snapshots
```

## Architecture in one minute

**Hexagonal (ports & adapters).** Each layer can only see layers below it.
Two `import-linter` contracts (`.importlinter`) enforce this on every commit:

```
src/lbb/
├── core/        pure domain, NO I/O — frozen dataclasses, pure functions
├── ports/       Protocol interfaces (LightBurnPort, FulfillmentRepository, FulfillmentStateStore, ...)
├── adapters/    real I/O — LightBurnShellAdapter, JsonFulfillmentRepository, SqliteStateStore, PdfiumReader, ...
├── app/         orchestration — FulfillmentService, container.py wiring
└── web/         pywebview shell (shell.py) + JsApiBridge (bridge.py) + HTML/CSS/JS assets
```

The data path for the main operator action (dashboard → engrave a side):

```
JS: window.pywebview.api.engrave_side(order_number, item_id, side_name)
  → JsApiBridge.engrave_side(...)             web/bridge.py  (thin marshaller)
    → FulfillmentService.engrave_side(...)     app/fulfillment_service.py
      → repo.get(order_number)                ports/fulfillment.py / adapters/json_fulfillment.py
      → lightburn.load_file(side.pdf_path)    adapters/lightburn_shell.py
          → on macOS: `open -a "LightBurn"`
          → on Windows: `cmd /c start "" file`
          → on Linux: `xdg-open file`
      → state.mark_side(order_number, item_id, side_name, True)
          → persisted in state.sqlite          adapters/sqlite_state.py
      → returns {ok, status, progress} → JS updates the UI
```

## Non-obvious things that bite if you don't know them

- **Data directory is `~/.flanacom-tool/`** (Windows: `%USERPROFILE%\.flanacom-tool\`).
  On first launch, if `orders/` doesn't exist, `JsonFulfillmentRepository` seeds it by
  copying `src/lbb/web/assets/seed-orders/` (orders.json + design PDFs + label PDFs)
  into `~/.flanacom-tool/orders/`. Operator progress (engraved sides, status overrides,
  comments) is stored in `~/.flanacom-tool/state.sqlite` via `SqliteStateStore` — progress
  persists across restarts.

- **The web UI calls Python via `window.pywebview.api`.** Every JS call goes through
  `JsApiBridge` (`web/bridge.py`), which is registered as the `js_api` object when the
  pywebview window is created. `JsApiBridge` is a thin marshaller — no business logic.
  All logic lives in `FulfillmentService` (`app/fulfillment_service.py`).

- **PySide6 is NOT the UI.** The UI is a pywebview window (Edge WebView2 on Windows).
  PySide6 remains a dependency **only** because `adapters/pdfium_reader.py` uses `QImage`
  for PNG encoding of PDF thumbnails in the old pipeline path. The `ui/` Python source
  files were deleted; only `__pycache__` remains. Do not add new code to `ui/`.

- **`.lbrn2` schema is reverse-engineered.** Community-documented at
  nuCarve and forum.lightburnsoftware.com. We never assume anything we
  haven't seen in a real LightBurn-saved file. **Critical encoding
  quirks** in `core/template_builder.py`:
  - `<VertList>` and `<PrimList>` are **string-encoded** (`"V10 10c0x1c1x1V60 10c0x1c1x1..."`), not nested XML children. Older `.lbrn` was XML; `.lbrn2` is the string variant.
  - `c0x1c1x1` is the line-vertex sentinel meaning "no Bezier control handles."
  - Group shapes wrap children in `<Children>...</Children>`.
  - Closing edges are implicit: just emit `L<last> 0`, no special close primitive.
  - Coordinates are mm with top-left origin (Y-down) in the saved file.

- **`tests/golden/wallet-small-rect.lbrn2`** is a byte-stable snapshot
  of `build_lbrn2` output. It's the schema-drift tripwire: if `lxml`
  serialisation changes or the builder changes, this test fails and
  someone reviews the diff before regenerating. **Never blindly run
  `regenerate_goldens.py` to "make the test pass" without reading the
  diff first.**

- **Production uses the shell adapter, NOT the UDP adapter.**
  `LightBurnUDPAdapter` exists and has tests, but `container.py` wires
  `LightBurnShellAdapter` (open file via OS) on every platform. UDP
  was unreliable on LightBurn Pro 2.0.05 / macOS. If you're tempted to
  reach for UDP, read git log for `f98205b`, `34b8325`, `5cea30f`.

- **Operator-assisted only.** We **never send `START`** to LightBurn.
  The engrave flow ends at "PDF loaded in LightBurn; operator presses Start
  physically." This is a deliberate safety boundary — see HANDOFF.md §4.5.

- **Pre-commit auto-formats and may bounce commits.** `ruff-format` is
  in `.pre-commit-config.yaml`. If a commit fails because "files were
  modified by this hook," that's ruff reformatting — re-`git add` the
  modified files and re-commit. Don't `--no-verify`.

- **Template fixture is synthesized, not LightBurn-authored.**
  `templates/wallet-small.lbrn2` was hand-built from community schema
  docs because the dev box didn't have LightBurn. It's been verified
  to open in LightBurn Pro 2.0.05 but should be replaced with a
  LightBurn-authored template before client distribution. See
  HANDOFF.md §5.1.

## Testing layout

- `tests/unit/core/` — pure-function tests, microsecond-fast, no I/O
- `tests/unit/adapters/` — real I/O against tmp_path / mocked subprocess (includes fulfillment adapter + state store tests)
- `tests/integration/` — full pipeline end-to-end with real PDF fixtures
  + the real `.lbrn2` template + a `LightBurnFake` (in-memory test double)
- `tests/golden/` — byte-stable `.lbrn2` snapshots for schema-drift detection
- `tests/fixtures/` — input PDFs + helper conftest

126 tests, 4 skipped (all pass with `uv run pytest`). The old `tests/ui/` pytest-qt tests were retired with the PySide6 UI.

## When the user asks to add a feature

The expected flow on a feature task:
1. Write the failing test first (`pytest path::name -v` to see RED).
2. Make the smallest change that turns it green.
3. Run the full suite (`uv run pytest`) — never commit a feature on a
   passing subset alone, integration tests are cheap.
4. If a port + adapter is involved, write the fake first and exercise
   it through the integration test; the real adapter follows.
5. Commits should be small, atomic, and have a body explaining *why*.
   The git log already has 40+ examples of this format.

## Where to ask further questions

- **Operating questions** (how does the app behave day-to-day?) → HANDOFF.md §3
- **Setup questions** (Windows build, prereqs) → HANDOFF.md §2 + docs/build-windows.md
- **Design rationale** (why hexagonal? why these specific tests?) →
  docs/plans/2026-05-16-lightburn-bridge-design.md
- **What's NOT built and why** → HANDOFF.md §5
- **The PDF contract for the client's design team** → docs/designer-pdf-spec.md
