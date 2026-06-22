# Fulfillment Studio — Handoff

> **Status as of 2026-06-04** · `feature/fulfillment-studio` · 126 tests passing, 4 skipped ·
> Fulfillment Studio dashboard live in pywebview · Windows build path documented

This document is the single source of truth for getting the project
running, knowing what it can do, and knowing what's still missing. If
something here disagrees with the code, the code wins — open an issue
and the doc gets corrected.

---

## Table of contents

1. [TL;DR — 30 seconds](#1-tldr--30-seconds)
2. [Quick start on Windows](#2-quick-start-on-windows)
3. [Operating the app day-to-day](#3-operating-the-app-day-to-day)
4. [What's built today](#4-whats-built-today)
5. [What's NOT built yet](#5-whats-not-built-yet)
6. [Maintenance recipes](#6-maintenance-recipes)
7. [Troubleshooting](#7-troubleshooting)
8. [File layout reference](#8-file-layout-reference)

---

## 1. TL;DR — 30 seconds

**Fulfillment Studio** is a desktop order-fulfillment dashboard for a
laser-engraving workshop. It opens as a pywebview window (a native desktop
frame hosting a local HTML/JS app). Operators see all pending orders
grouped by product type, click a side's "Engrave · LightBurn" button to
open that side's design PDF directly in LightBurn, mark sides as engraved
as work progresses, and ship orders when all sides are done. Progress
persists across restarts in a local SQLite database.

**Tech stack:** Python 3.12 · pywebview (Edge WebView2 on Windows) ·
SQLite · lxml · pypdfium2. Architecture is hexagonal
(core / ports / adapters / app / web) with import-linter enforcing layer
boundaries. Built with PyInstaller for distribution.

**LightBurn integration:** direct-open (`cmd /c start "" file.pdf` on
Windows) — LightBurn imports the design PDF natively. We never auto-fire.

**What's not done:** code-signing the bundle, real Airtable/Supabase
backend (currently using seeded JSON files), real laser material values.
See [§5](#5-whats-not-built-yet) for the full list.

---

## 2. Quick start on Windows

### 2.1 Prerequisites checklist

You need these installed on the Windows laptop before cloning:

- [ ] **Python 3.12** — <https://www.python.org/downloads/windows/>
  - **Tick "Add python.exe to PATH"** during install.
- [ ] **uv** — Astral's package manager. Open **PowerShell** and run:
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
  Restart PowerShell so `uv` lands on PATH.
- [ ] **Git** — <https://git-scm.com/download/win>. Default settings are fine.
- [ ] **LightBurn** — verified on LightBurn Pro 2.0.05. The app opens
  design PDFs directly in LightBurn, so LightBurn must be installed but
  does **not** need any special file-association setup beyond a working
  install.
- [ ] **Edge WebView2** — ships with Windows 11 by default. If the app
  opens with a blank white window on an older Windows version, install the
  WebView2 Evergreen Bootstrapper from:
  <https://developer.microsoft.com/microsoft-edge/webview2/>

Sanity-check in one PowerShell session:

```powershell
python --version    # Python 3.12.x
uv --version        # uv 0.10.x or later
git --version       # git 2.40.x or later
```

### 2.2 Setup commands

In PowerShell, from a directory you own (e.g., `C:\Projects\`):

```powershell
git clone https://github.com/gabriel-tutor/lightburn-tool.git
cd lightburn-tool

# Install Python deps. First run takes 3–5 minutes; subsequent runs are seconds.
uv sync --dev

# Smoke-run the app from source to verify everything wires up.
uv run python -m lbb
```

The dashboard window opens. On first run, seed orders are copied from the
bundled `src/lbb/web/assets/seed-orders/` into `%USERPROFILE%\.flanacom-tool\orders\`.
You should see two sample Amazon orders in the dashboard.

**If this works, you're done with verification.** Quit the dev launch
and build the distributable next.

```powershell
# Build the production binary (~3 min cold, 30s warm).
uv run pyinstaller packaging/lbb.spec --clean --noconfirm

# Run the built binary.
.\dist\"Fulfillment Studio"\"Fulfillment Studio.exe"
```

The bundled binary lives at `dist\Fulfillment Studio\Fulfillment Studio.exe`
along with its DLLs. To distribute, zip the entire `dist\Fulfillment Studio\` folder.

### 2.3 First-run verification (5-minute smoke test)

With the binary running and LightBurn open:

1. **Dashboard** loads showing the two seed orders grouped by product type.
2. **LightBurn pill** should turn green ("LightBurn — Running") within ~2 seconds
   if LightBurn is running.
3. **Click an order** to open the order view. Products with Front/Back sides are listed.
4. **Click "Engrave Front · LightBurn"** on a product. LightBurn comes to the
   foreground with the design PDF open. The side's checkbox marks ✓.
5. **Mark remaining sides engraved**, then click **"Mark as shipped"**. A gift-box
   reminder modal appears (for gift-box orders); confirm to ship.
6. The order moves to Shipped filter.

If any step fails, jump to [§7 — Troubleshooting](#7-troubleshooting).

---

## 3. Operating the app day-to-day

### 3.1 Dashboard

The dashboard groups all orders by product type in workshop queue order:
**Bracelets → Necklaces → Keychains → Flasks**, oldest first within each group.

- **Search** by order number (top bar).
- **Filter** by To-do (all non-shipped) or Shipped.
- Each order card shows product summary, placed date, status badge, and
  a progress bar (engraved sides / total sides).

### 3.2 Operator — engrave a customer order

1. **Open Fulfillment Studio.** Confirm the LightBurn status pill is green.
2. **Click an order** in the dashboard to open the order view.
3. **Review the order**: recipient, channel, gift-box flag, products.
4. For each product, for each side (Front / Back):
   - **Click "Engrave [Side] · LightBurn"**. The design PDF for that side
     opens directly in LightBurn (no `.lbrn2` generation — LightBurn
     imports the PDF natively).
   - **Position the workpiece** in the laser bed.
   - **Press Start** on the physical laser controller. We never auto-fire —
     this is a deliberate safety boundary (see [§4.5](#45-safety)).
   - The side marks ✓ in the app automatically when you clicked Engrave.
5. When all sides across all products are done, click **"Mark as shipped"**.
   For gift-box orders a reminder modal appears — confirm packing before shipping.
6. The order disappears from To-do and appears in Shipped.

### 3.3 Additional operator tools in the order view

- **Status dropdown**: manually set received / engraving / engraved / shipped / on-hold.
  Shipped and on-hold are explicit overrides; the other statuses are derived
  from actual engraved-side progress.
- **Comments**: add freeform notes visible in the order view.
- **Shipping label**: open (Preview) or print the label PDF for the order.
- **Amazon link**: opens the Amazon order page in the default browser.
- **Instructions URL**: opens product instruction page in the default browser.

---

## 4. What's built today

### 4.1 Architecture map

```
┌─────────────────────────────────────────────────────┐
│  web/  (pywebview desktop window)                   │
│  • shell.py     — creates the window over index.html│
│  • bridge.py    — JsApiBridge, exposed as           │
│                   window.pywebview.api              │
│  • assets/      — index.html, app.css, app.js,      │
│                   bridge-client.js, seed-orders/    │
└────────────────────────┬────────────────────────────┘
                         │  JS calls → Python
┌────────────────────────▼────────────────────────────┐
│  app/  (orchestration)                              │
│  • FulfillmentService — merges orders + state,      │
│    derives status, dispatches to LightBurn,         │
│    returns JSON view models                         │
│  • container.py — wires real adapters               │
└──────────┬─────────────────────────┬────────────────┘
           │                         │
┌──────────▼──────────┐  ┌───────────▼──────────────┐
│  ports/             │  │  adapters/               │
│  FulfillmentRepo    │  │  JsonFulfillmentRepo      │
│  FulfillmentState   │  │    (orders.json + PDFs)  │
│  LightBurnPort      │  │  SqliteStateStore         │
│                     │  │    (state.sqlite)        │
│                     │  │  LightBurnShellAdapter   │
└──────────┬──────────┘  └──────────────────────────┘
           │
┌──────────▼──────────┐
│  core/  (no I/O)    │
│  FulfillmentOrder   │
│  Product / Side     │
│  OrderStatus        │
│  derive_status      │
│  queue_sort_key     │
└─────────────────────┘
```

Import-linter contracts enforce: `core/` cannot import from `adapters/`
or `app/`; `web/` cannot import directly from `adapters/`. Violations
break the commit hook and CI.

### 4.2 Key modules

| Module | Role |
|---|---|
| `core/fulfillment.py` | Domain: `FulfillmentOrder`, `Product`, `Side`, `OrderStatus`, `derive_status`, `queue_sort_key` |
| `ports/fulfillment.py` | `FulfillmentRepository` + `FulfillmentStateStore` Protocols |
| `adapters/json_fulfillment.py` | Reads orders from `~/.flanacom-tool/orders/orders.json` + per-side PDFs; seeds on first run |
| `adapters/sqlite_state.py` | Persists engraved sides, status overrides, comments in `state.sqlite` |
| `app/fulfillment_service.py` | Business brain: merges repo + state, derives status, dispatches to LightBurn, returns JSON |
| `web/bridge.py` | `JsApiBridge`: thin marshaller exposed to JS as `window.pywebview.api` |
| `web/shell.py` | `run_app(service)`: creates pywebview window over `web/assets/index.html` |
| `web/assets/` | `index.html`, `app.css`, `app.js`, `bridge-client.js`, `seed-orders/` |
| `__main__.py` | Entry point: `build_fulfillment_service` + `run_app` |
| `adapters/lightburn_shell.py` | `LightBurnShellAdapter`: opens files in LightBurn via OS shell; detects running process |

### 4.3 LightBurn integration — what we use and why

The community-documented UDP protocol turned out to be unreliable on
LightBurn Pro 2.0.05 / macOS. We use the OS's standard "open file with
the registered app" mechanism instead, and LightBurn natively imports PDF:

| Platform | Open file in LightBurn | Detect running |
|---|---|---|
| macOS | `open -a "LightBurn" file.pdf` | `pgrep -x LightBurn` |
| Linux | `xdg-open file.pdf` | `pgrep -x LightBurn` |
| Windows | `cmd /c start "" file.pdf` | `tasklist /FI IMAGENAME eq LightBurn.exe` |

`LightBurnUDPAdapter` is still in the repo and tested; it's not wired in
production. See git log before 2026-05 for the earlier UDP setup.

### 4.4 Data directory

```
~/.flanacom-tool/            (macOS/Linux)
%USERPROFILE%\.flanacom-tool\ (Windows)
├── orders/
│   ├── orders.json          ← order definitions (seeded from bundled seed-orders/ on first run)
│   ├── <order>-A-Front.pdf  ← per-side design PDFs
│   ├── <order>-A-Back.pdf
│   └── labels/
│       └── <order>.pdf      ← shipping label PDFs
└── state.sqlite             ← engraved sides, status overrides, comments (SqliteStateStore)
```

The JSON + PDF layout simulates the future Airtable/Supabase backend. Swapping
to a real backend means replacing `JsonFulfillmentRepository` with a new adapter
behind the same `FulfillmentRepository` port — no service or UI changes.

### 4.5 Safety

We **never send `START`** to LightBurn. The engrave flow ends at "PDF loaded;
operator sees the job in LightBurn." The operator positions the workpiece and
physically presses Start on the laser controller. This is a deliberate boundary:
automated firing changes the liability profile of the tool.

---

## 5. What's NOT built yet

### 5.1 Pre-demo / pre-handoff items

- **Code-signing.** Windows Defender SmartScreen warns on unsigned `.exe` bundles.
  For client distribution, Authenticode-sign the `.exe`.
- **Real order backend.** Currently reads from a seeded JSON file. The plan is
  Airtable or Supabase — swap `JsonFulfillmentRepository` for a new adapter behind
  the same port.
- **Real material values / LightBurn template tuning.** The old pipeline path
  (`core/template_builder.py`) is still present for the SKU-based `.lbrn2` workflow
  but is not used by Fulfillment Studio. The fulfillment path opens design PDFs
  directly — LightBurn's own per-layer settings govern speed/power.

### 5.2 Deferred features (v1 / v2)

- **Airtable/Supabase sync.** Replace `JsonFulfillmentRepository` with a live-pull adapter.
- **Watched-folder / webhook ingest.** New orders arrive automatically.
- **Multi-workstation.** A small API server hosts state; multiple Studio clients pull from it.
- **Analytics dashboard.** Jobs per day, top SKUs, error rates.
- **Auto-update channel.** Currently manual download of new builds.

### 5.3 Known issues / quirks

| Quirk | Impact | Workaround |
|---|---|---|
| `AppVersion="1.7.04"` in synthesized `.lbrn2` template; LightBurn Pro 2.0.05 reads it fine | Not verified on LightBurn 1.7.x | Test on 1.7.x before going live there |
| `AuditLog` port is defined but no implementation exists | No audit trail today | Add `SqliteAuditLog` adapter when needed; ~50 lines |
| Pillow installed transitively via fpdf2 in dev | Slight extra dev install size | None — not used in production path |
| pywebview shows a blank white window on older Windows | App unusable | Install Edge WebView2 Evergreen Bootstrapper (see §2.1) |

---

## 6. Maintenance recipes

### 6.1 Rebuild for distribution

After any code change, refresh the binary:

```powershell
# Windows
uv run pyinstaller packaging/lbb.spec --clean --noconfirm
# → dist\Fulfillment Studio\Fulfillment Studio.exe
```

To zip for transfer:
```powershell
Compress-Archive -Path "dist\Fulfillment Studio" -DestinationPath FulfillmentStudio-win.zip
```

### 6.2 Update a template (old SKU pipeline path)

If you change cut settings or canvas size in a `.lbrn2` template under
`templates/`, update the golden so tests stay green:

```bash
uv run python scripts/regenerate_goldens.py
```

Eyeball the diff — if only intended changes moved, commit.

### 6.3 Regenerate PDF fixtures

```bash
uv run python scripts/generate_fixtures.py
```

Then regenerate goldens (above) because new PDFs change the pipeline's golden output.

### 6.4 Add or update seed orders

Edit `src/lbb/web/assets/seed-orders/orders.json` and add/replace the
corresponding design PDFs and label PDFs in the same directory.

On the next first-run (or after deleting `~/.flanacom-tool/orders/`), the
updated seed will be copied into the data directory.

### 6.5 Bump dependency versions

```bash
uv sync --upgrade --dev
uv run pytest
git add uv.lock && git commit -m "chore: bump deps"
```

---

## 7. Troubleshooting

### "uv: command not found" after installing

Restart PowerShell. The uv installer adds itself to `$env:Path` but
existing shells don't pick up the change until restarted. If still
missing, manually add `%USERPROFILE%\.local\bin` to PATH via System
Properties → Environment Variables.

### Tests pass locally but CI fails on Windows

Most common cause: a test inadvertently depends on POSIX semantics
(`pgrep`, slashes vs backslashes, line endings). If a new test breaks on
Windows, check for `subprocess.run` with POSIX commands, hardcoded `/tmp/`,
or file-path string comparisons that assume forward slashes.

### PyInstaller build hangs at "Building EXE"

Usually antivirus scanning the in-progress executable. Add the project
directory and `dist/` to antivirus exclusions. On Windows: Defender →
Virus & threat protection settings → Add exclusion.

### App opens a blank white window

Edge WebView2 is missing or not initialized. Install the WebView2
Evergreen Bootstrapper from:
<https://developer.microsoft.com/microsoft-edge/webview2/>

WebView2 ships with Windows 11 by default; this issue typically only
appears on Windows 10 machines that haven't received it via Windows Update.

### "LightBurn — Not running" stays grey even with LightBurn open

The status pill checks `tasklist /FI IMAGENAME eq LightBurn.exe` (Windows)
or `pgrep -x LightBurn` (POSIX). The match is case-sensitive and exact.
If your LightBurn executable is named differently (`LightBurn Pro.exe`, etc.),
the pill will miss it. Open `src/lbb/adapters/lightburn_shell.py` and adjust
the process name, then rebuild.

### LightBurn opens but the design file doesn't load

On Windows, `cmd /c start "" file.pdf` relies on the OS to open the PDF
with the registered application. If LightBurn is not associated with `.pdf`
files, Windows may open a different app (or nothing). Fix: in LightBurn,
go to File → Import and verify PDF imports work. Alternatively, right-click
a PDF → Open With → Choose another app → LightBurn → "Always use this app."

### LightBurn crashes when our generated `.lbrn2` file is loaded

(Applies to the old SKU pipeline path, not to Fulfillment Studio's direct-PDF path.)
Could be a schema-compatibility issue between our synthesized template and
your specific LightBurn version. Author a fresh template inside LightBurn
itself and replace the file in `templates/` — LightBurn-authored templates
are guaranteed schema-compatible.

### General "I have no idea what's wrong"

Launch the bundle from PowerShell so stderr is visible:

```powershell
cd "C:\Projects\lightburn-tool\dist\Fulfillment Studio"
.\"Fulfillment Studio.exe"
```

Reproduce the issue. Stack traces print to stderr. Copy the traceback into an issue.

---

## 8. File layout reference

```
lightburn-tool/
├── HANDOFF.md                  ← you are here
├── README.md                   ← short intro + build commands
├── pyproject.toml              ← deps + tool config
├── .importlinter               ← architectural contracts
├── .pre-commit-config.yaml     ← ruff + import-linter on commit
│
├── docs/
│   ├── build-windows.md        ← Windows-build details
│   ├── designer-pdf-spec.md    ← PDF contract for the design team
│   └── plans/
│       ├── 2026-05-16-lightburn-bridge-design.md
│       └── 2026-06-04-fulfillment-studio-web.md
│
├── src/lbb/
│   ├── __main__.py             ← entry point (`python -m lbb`)
│   ├── core/                   ← pure domain, no I/O
│   │   ├── fulfillment.py      ← FulfillmentOrder, Product, Side, OrderStatus, derive_status
│   │   ├── models.py           ← Sku, Material, Template, etc. (SKU pipeline)
│   │   └── ...
│   ├── ports/
│   │   ├── fulfillment.py      ← FulfillmentRepository + FulfillmentStateStore Protocols
│   │   └── ...
│   ├── adapters/
│   │   ├── json_fulfillment.py ← reads orders.json + PDFs; seeds on first run
│   │   ├── sqlite_state.py     ← engraved sides, overrides, comments → state.sqlite
│   │   ├── lightburn_shell.py  ← OS shell integration (open file + process detect)
│   │   └── ...
│   ├── app/
│   │   ├── fulfillment_service.py ← business brain; headless-testable
│   │   ├── container.py           ← composition root; build_fulfillment_service()
│   │   └── ...
│   └── web/
│       ├── shell.py            ← run_app(): pywebview window over index.html
│       ├── bridge.py           ← JsApiBridge (window.pywebview.api)
│       └── assets/
│           ├── index.html
│           ├── app.css
│           ├── app.js
│           ├── bridge-client.js
│           └── seed-orders/    ← bundled starter orders.json + design/label PDFs
│
├── templates/                  ← production .lbrn2 templates (SKU pipeline)
│   └── wallet-small.lbrn2
│
├── tests/
│   ├── fixtures/               ← PDFs and templates for tests
│   ├── golden/                 ← byte-stable .lbrn2 snapshots
│   ├── unit/                   ← isolated unit tests (core + adapters)
│   └── integration/            ← pipeline integration tests
│
├── scripts/
│   ├── generate_fixtures.py    ← emit test PDFs deterministically
│   └── regenerate_goldens.py   ← refresh golden .lbrn2 snapshots
│
├── packaging/
│   └── lbb.spec                ← PyInstaller spec
│
└── .github/workflows/
    └── ci.yml                  ← test + build matrix
```

User data (created at runtime, not in git):

```
~/.flanacom-tool/               ← macOS / Linux
%USERPROFILE%\.flanacom-tool\   ← Windows
├── orders/
│   ├── orders.json             ← order definitions (seeded from bundled seed-orders/)
│   ├── <order>-A-Front.pdf     ← per-side design PDFs
│   └── labels/
│       └── <order>.pdf         ← shipping label PDFs
└── state.sqlite                ← operator progress (SqliteStateStore)
```

---

## Appendix — Quick commands cheatsheet

```powershell
# Run from source
uv run python -m lbb

# Run tests
uv run pytest

# Run a specific test
uv run pytest tests/unit/adapters/ -v

# Lint
uv run ruff check
uv run lint-imports

# Build distributable (Windows)
uv run pyinstaller packaging/lbb.spec --clean --noconfirm
# → dist\Fulfillment Studio\Fulfillment Studio.exe

# Regenerate fixtures + goldens after a deliberate change
uv run python scripts/generate_fixtures.py
uv run python scripts/regenerate_goldens.py
```
