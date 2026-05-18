# LightBurn Bridge — Handoff

> **Status as of 2026-05-19** · 41 commits on `main` · 101 tests passing ·
> macOS .app verified end-to-end against LightBurn Pro 2.0.05 · Windows
> build path documented but not yet run by a human

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

LightBurn Bridge is a **cross-platform desktop app** that turns a
customer-order PDF into a configured LightBurn job. Operator drops a PDF
named with a product SKU; the app looks up the SKU, generates a
`.lbrn2` file with the right layer / speed / power settings, and opens
it in LightBurn ready for the operator to press Start.

**Tech stack:** Python 3.12 · PySide6 (Qt) · lxml · pypdfium2 ·
SQLite. Architecture is hexagonal (core / ports / adapters / app / ui)
with import-linter enforcing the boundaries. Built with PyInstaller for
distribution. Tests run via `pytest` on every commit across Linux /
macOS / Windows via GitHub Actions.

**Demo flow:** open the app → drop or click-to-browse a PDF named
`LB-WALLET-LEATHER-S__order-2381.pdf` → preview screen lights up with
thumbnail + SKU + template + material + ✓ preflight → click Send →
LightBurn comes to the foreground with the file loaded, ready to fire.

**What's not done:** code-signing the bundle, real material values from
the laser engineer, watched-folder mode, e-commerce integration, a few
admin-UX niceties (CSV bulk import, delete-SKU button). See
[§5](#5-whats-not-built-yet) for the full honest list.

---

## 2. Quick start on Windows

### 2.1 Prerequisites checklist

You need three things installed on the Windows laptop before cloning:

- [ ] **Python 3.12** — <https://www.python.org/downloads/windows/>
  - **Tick "Add python.exe to PATH"** during install. Without this,
    `uv` and `python` won't be findable from PowerShell.
- [ ] **uv** — Astral's package manager. Open **PowerShell** and run:
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
  Restart PowerShell so `uv` lands on PATH.
- [ ] **Git** — <https://git-scm.com/download/win>. Default settings are
  fine. Confirm with `git --version`.
- [ ] **LightBurn** (whatever version your client uses; verified on
  LightBurn Pro 2.0.05 / macOS). Make sure `.lbrn2` files are
  associated with LightBurn: right-click any `.lbrn2` → Open With →
  Choose another app → tick **"Always use this app"** → pick LightBurn.

Sanity-check everything in one PowerShell session:

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

# Install Python deps (PySide6 etc.). First run takes 3–5 minutes;
# subsequent runs are seconds because the wheels are cached.
uv sync --extra ui --dev

# Seed a demo SKU so dropping the showcase PDF actually does something.
uv run python scripts/seed_demo.py

# Smoke-run the app from source to verify everything wires up.
uv run python -m lbb
```

The app window opens, status pill flips to **● LightBurn — Ready**
within 2 seconds if LightBurn is running, and you can drop a PDF.
**If this works, you're done with verification.** Quit the dev launch
and build the distributable next.

```powershell
# Build the production binary. 30s for warm rebuilds, ~3 min cold.
uv run pyinstaller packaging/lbb.spec --clean --noconfirm

# Run the built binary.
.\dist\"LightBurn Bridge"\"LightBurn Bridge.exe"
```

The bundled binary lives at `dist\LightBurn Bridge\LightBurn Bridge.exe`
along with its DLLs and Qt plugins. To distribute, zip the entire
`dist\LightBurn Bridge\` folder.

### 2.3 First-run verification (5-minute smoke test)

With the binary running and LightBurn open:

1. **Status pill** should be **green** ("LightBurn — Ready") within
   ~2 seconds.
2. **Click the drop zone.** A native Windows file picker opens.
3. **Select the showcase PDF** that ships in the repo:
   `tests\fixtures\pdfs\LB-WALLET-LEATHER-S__showcase.pdf`. Copy it to
   your Desktop first if dragging is easier.
4. **Preview screen** lights up: PDF thumbnail on the left, SKU
   detected in mono+cyan, template "Wallet — Small (95 × 110 mm)",
   material "Leather 2mm — Vegetable Tan", green "✓ All preflight
   checks passed."
5. **Click Send.** LightBurn comes to the foreground with the
   generated `.lbrn2` open. Two layers visible in the Cuts/Layers
   panel: **C00** for cut, **C01** for engrave. Geometry renders
   correctly inside the 95×110mm canvas.
6. **Operator presses Start** on the real laser. (We never auto-fire
   — this is a deliberate safety boundary; see [§4.5](#45-safety).)

If any step fails, jump to [§7 — Troubleshooting](#7-troubleshooting).

### 2.4 If you'd rather not install Python on Windows

GitHub Actions builds the same `.exe` automatically on every push. Go
to <https://github.com/gabriel-tutor/lightburn-tool/actions>, click the
latest successful run, scroll to **Artifacts**, download
`lightburn-bridge-windows-latest.zip`. Unzip → `LightBurn Bridge\` →
run the `.exe`. No Python install needed on Windows. You still need
to run `seed_demo.py` somehow (either on your Mac and copy the
resulting `profiles.sqlite` over, or install Python anyway just to seed).

---

## 3. Operating the app day-to-day

Three roles use this tool. The same single binary serves all three —
they just touch different screens.

### 3.1 Operator — engrave a customer job

1. **Receive a PDF** from the order system, named with the product
   SKU: `LB-WALLET-LEATHER-S__order-2381.pdf` (the double underscore
   matters — everything before it is the SKU).
2. **Open LightBurn Bridge.** Confirm the status pill is **green**.
3. **Drop or click-to-browse** the PDF onto the dashed drop zone.
4. **Verify the preview screen.** Look at:
   - The SKU we detected matches the customer's product.
   - The template name and canvas size make sense.
   - The material profile is what the engineer expects for this product.
   - All four preflight checks are ✓ green.
5. **Click Send →**. LightBurn opens the generated job file.
6. **Position the workpiece** in the laser bed using the alignment
   marks rendered by the template.
7. **Press Start** on the physical laser controller.

If the preview shows red ✕ preflight failures, **do not send**. Fix the
source PDF (the failure list tells you what's wrong) and try again.

### 3.2 Admin — add a new SKU

When the design team launches a new product and you need to map a SKU
to the right template and material:

1. **In LightBurn Bridge**, click **Admin** (bottom-right).
2. The SKU table lists every mapping currently registered.
3. Click **+ Add SKU**.
4. In the dialog:
   - **SKU code**: the exact string the design team will put before
     the `__` in the filename. Example: `LB-WALLET-LEATHER-M`.
   - **Template**: pick the product template (these are pre-authored
     by the engineer in LightBurn — see §3.3).
   - **Material**: pick the material profile (these reference a
     `.clb` file in LightBurn's Material Library; the laser engineer
     maintains them in LightBurn itself).
5. **Save**. The new mapping is live immediately — no app restart.

### 3.3 Engineer — add a new product template

When you need a new product shape (different canvas size or different
layer behavior), the workflow is:

1. **In LightBurn**, File → New, set workspace to the product's
   canvas size.
2. **Add cut layers** (C00, C01, …) with the right speed / power /
   passes for each operation. Use LightBurn's Material Library to
   link layers to materials so the laser engineer's tuning lives in
   one place.
3. **Draw a placeholder rectangle** somewhere on the canvas. Group it
   (⌘+G / Ctrl+G).
4. **Save as** `<product-name>.lbrn2` in the repo's `templates/`
   directory.
5. **Open the saved file in a text editor.** Find the
   `<Shape Type="Group">` line that wraps your placeholder. Add
   `Name="DESIGN_PLACEHOLDER"`:
   ```xml
   <Shape Type="Group" Name="DESIGN_PLACEHOLDER">
   ```
6. **Save.** Then in Bridge's Admin, add a Template entry pointing at
   this new file with the right canvas dimensions.
7. **Regenerate the golden** if the template change affects an
   existing fixture:
   ```bash
   uv run python scripts/regenerate_goldens.py
   ```

---

## 4. What's built today

### 4.1 Architecture map

```
                    ┌──────────────────────────┐
                    │     UI  (PySide6)        │
                    │  • HomeView              │
                    │  • JobPreviewView        │
                    │  • AdminView             │
                    │  • DropZone / StatusPill │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │  App / orchestration     │
                    │  • run_pipeline()        │
                    │  • PipelineDeps DI       │
                    │  • container.py wiring   │
                    └────────────┬─────────────┘
                                 │
                ┌────────────────▼────────────────┐
                │   Ports (Protocols)             │
                │  • LightBurnPort                │
                │  • ProfileRepository            │
                │  • PdfReader, AuditLog          │
                └─────┬──────────┬─────────┬──────┘
                      │          │         │
   ┌──────────────────▼──┐   ┌───▼────┐  ┌─▼────────────────┐
   │  Core (pure, no I/O)│   │Adapters│  │Adapters (real I/O)│
   │  • models           │   │(fakes) │  │ • LightBurnShell  │
   │  • errors           │   │(tests) │  │ • LightBurnUDP    │
   │  • extractor        │   └────────┘  │ • SqliteProfile…  │
   │  • palette          │               │ • PdfiumReader    │
   │  • preflight        │               └───────────────────┘
   │  • template_builder │
   └─────────────────────┘
```

Import-linter contracts enforce: `core/` cannot import from
`adapters/`, `ui/`, or `app/`; `ui/` cannot import directly from
`adapters/`. Violations break the commit hook and CI.

### 4.2 Capability inventory

| Capability | Module(s) | Tests | Notes |
|---|---|---|---|
| SKU extraction from filename | `core/extractor.py` | 6 (+ hypothesis property) | `<SKU>__<anything>.pdf` |
| LightBurn 30-color palette | `core/palette.py` | 6 | `is_palette_color` + `layer_index_for_color` |
| PDF preflight | `core/preflight.py` | 6 | vector-only · palette · canvas · page-count |
| `.lbrn2` generation | `core/template_builder.py` | 11 | byte-stable golden file |
| Domain models | `core/models.py` | 4 | frozen dataclasses |
| Typed errors | `core/errors.py` | 2 | human-readable defaults |
| LightBurn shell integration | `adapters/lightburn_shell.py` | 12 | `open -a` / `start` + `pgrep` / `tasklist` |
| LightBurn UDP integration | `adapters/lightburn_udp.py` | 6 | kept for completeness; not in production wiring |
| LightBurn in-memory fake | `adapters/lightburn_fake.py` | 3 | for integration tests |
| SQLite profile repository | `adapters/sqlite_repo.py` | 6 | 3 tables · FK enforcement on |
| PDF reader (pypdfium2) | `adapters/pdfium_reader.py` | 8 | `read_info` + `extract_paths` + `render_thumbnail_png` (Qt-based PNG) |
| Job pipeline | `app/pipeline.py` | 5 | full end-to-end integration |
| DI container | `app/container.py` | (via pipeline) | composition root |
| Theme (QSS + tokens) | `ui/theme/` | — | platform-native font stack |
| DropZone widget | `ui/widgets/drop_zone.py` | 3 | drag-drop + click-to-browse |
| Status pill widget | `ui/widgets/status_pill.py` | 3 | dot + label, tinted by state |
| Home view | `ui/views/home.py` | 3 | wordmark header + drop zone + nav |
| Job preview view | `ui/views/job_preview.py` | 4 | preflight gates Send button |
| Admin view | `ui/views/admin.py` | 4 | SKU table + Add dialog |
| Main window controller | `ui/main_window.py` | 3 | stack navigation + broad-except diagnostics |
| Entry point | `__main__.py` | — | `python -m lbb` / bundled binary |

**Total: 101 tests, all passing.**

### 4.3 Tooling

- **Test runner**: pytest with hypothesis (property-based) and
  pytest-qt (Qt event-loop tests).
- **Linter**: ruff (formatter + checks) with project-specific rules
  in `pyproject.toml`.
- **Architectural lint**: import-linter contracts in `.importlinter`.
- **Pre-commit**: hooks block bad code before it hits git.
- **CI**: GitHub Actions matrix on Linux / macOS / Windows. After
  tests pass, a `build` job runs PyInstaller and uploads the artifact
  per OS.
- **Packaging**: PyInstaller spec at `packaging/lbb.spec` — produces
  `.app` on macOS, `.exe`+folder on Windows/Linux.
- **Fixture generation**: `scripts/generate_fixtures.py` emits
  deterministic vector PDFs via fpdf2. Goldens regenerate via
  `scripts/regenerate_goldens.py`.
- **Seeding**: `scripts/seed_demo.py` populates the user database
  with demo SKU profiles.

### 4.4 LightBurn integration — what we use and why

The community-documented UDP protocol turned out to be unreliable on
LightBurn Pro 2.0.05 / macOS (the listener didn't respond to PING).
We **retired UDP from production wiring** and use the OS's standard
"open file with the registered app" mechanism instead:

| Platform | Open file in LightBurn | Detect running |
|---|---|---|
| macOS | `open -a "LightBurn" file.lbrn2` | `pgrep -x LightBurn` |
| Linux | `xdg-open file.lbrn2` | `pgrep -x LightBurn` |
| Windows | `cmd /c start "" file.lbrn2` | `tasklist /FI IMAGENAME eq LightBurn.exe` |

This works regardless of LightBurn version, regardless of machine
configuration, regardless of whether LightBurn's UDP listener exists.
LightBurn launches automatically if not running.

### 4.5 Safety

We **never send `START`** to LightBurn. The pipeline ends at "file
loaded; operator sees the job in LightBurn." The operator is the one
who positions the workpiece and physically presses Start on the laser.
This is a deliberate boundary: automated firing requires controller
support that not all of our clients' lasers have (Ruida / GRBL
controllers don't expose a completion callback) and changes the
liability profile of the tool.

---

## 5. What's NOT built yet

Honest list. Some items are intentional MVP cuts, some are deferred
v1/v2 features, some are known issues.

### 5.1 Pre-demo blockers

These should be resolved before the client demo:

- **Code-signing.** macOS Gatekeeper blocks unsigned `.app` bundles on
  fresh machines; Windows Defender SmartScreen warns. For internal
  testing this is "click More info → Run anyway." For client
  distribution, sign with `codesign` (Apple Developer ID) + notarize
  via `notarytool`, and Authenticode-sign the `.exe` on Windows.
- **Real material values.** The current `templates/wallet-small.lbrn2`
  has placeholder cut settings (1000 mm/min @ 20% for cut, 50 mm/sec
  @ 15% for engrave). The client's laser engineer needs to dial in
  real values per material and update the template (or update the
  linked LightBurn Material Library entries).
- **Template stress-testing in real LightBurn.** Earlier in
  development LightBurn Pro 2.0.05 crashed after some interaction
  with our synthesized template. Loading the file works (verified);
  some interaction did not. Worth a 10-minute "click around in
  LightBurn with the file open" before ringing the bell on a final
  shipping build.

### 5.2 Deferred features (v1 / v2)

These were called out in the original design as out-of-scope for MVP:

- **Watched-folder mode.** Drop a PDF into `~/jobs/incoming/`, the app
  picks it up automatically. Plumbing is straightforward (QFileSystemWatcher).
- **E-commerce integration.** Shopify / WooCommerce backend feeds
  orders directly into a job queue inside the app. ~1 week of work.
- **Multi-workstation central settings.** A small FastAPI service
  hosts the SKU/template/material database; multiple Bridge clients
  pull from it. Useful when the client has 3+ laser stations.
- **Job analytics dashboard.** Jobs per day, top SKUs, error rates.
- **Per-SKU first-run test job.** Engrave on test material first
  before the real product, gated by an operator confirmation.
- **Auto-update channel.** Currently the user manually downloads new
  builds. A `pyupdater`-style check-on-launch would be nice for
  pushing schema-pin updates when LightBurn ships a new version.

### 5.3 Admin UX niceties not built

The current Admin view is intentionally minimal (just SKU add). To
match the original design's plan:

- **Delete SKU** button (currently you can re-add but not remove).
- **Edit SKU** in-line (currently delete-and-readd via the dialog).
- **Templates tab** to add/manage Template entries from the UI
  (currently you edit them directly in `templates/` and via the seed
  script).
- **Materials tab** to add/manage Material entries from the UI.
- **CSV import / export** for bulk SKU onboarding from the client's
  product-catalog spreadsheet.

### 5.4 PDF feature gaps (intentional MVP cut)

`PdfiumReader.extract_paths` and `core.template_builder.build_lbrn2`
both currently support:

- **M / L / Z** SVG path commands (move-to / line-to / close-path).
- **Single page** PDFs.
- **Stroke-color routing** (each stroke color → its palette layer).

They do **not** support:

- **Bezier curves** (BEZIERTO segments are silently skipped during
  extraction; build_lbrn2 has no curve support). For now, designs
  must outline curves as polylines.
- **Multi-page PDFs.** Preflight rejects them; we read only page 0
  even if you bypass.
- **Filled shapes** for engrave-scan operations. We treat fills as
  strokes for layer routing; LightBurn's engrave-fill behavior is
  driven by the per-layer `mode` in the template, not by us.
- **Raster images** in the PDF. Preflight rejects them; vector only.

These limits are documented in `docs/designer-pdf-spec.md` — the
contract document for the client's design team.

### 5.5 Known issues / quirks

| Quirk | Impact | Workaround |
|---|---|---|
| macOS drag-drop from Finder may not work after rebuild without `lsregister -f` | Cosmetic — click-to-browse always works | `/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister -f "$(pwd)/dist/LightBurn Bridge.app"` |
| Qt warns "missing font family SF Pro Text" at startup | None — fallback chain works | Ignore; or bundle the font (~1MB) |
| UDP polling blocks the GUI thread for 100ms per poll when LightBurn isn't running | Mild perceived lag once per 2s | Future: migrate to QUdpSocket for fully-async polling |
| `AppVersion="1.7.04"` in our synthesized template; LightBurn Pro 2.0.05 reads it fine | Not verified on LightBurn 1.7.x | Test on 1.7.x before going live there |
| `AuditLog` port is defined but no implementation exists | No audit trail today | Add `SqliteAuditLog` adapter when needed; ~50 lines |
| Pillow still installed transitively via fpdf2 in dev | Slight extra dev install size | None — Pillow isn't used in production path anymore (we use QImage) |

### 5.6 What would be nice but isn't necessary

- **Custom SVG icons.** Currently using unicode glyphs (●, ⌄). SVG
  from Lucide would be more consistent across platforms.
- **App icon.** The bundle has no custom icon yet — shows the generic
  PyInstaller icon on macOS Dock and Windows Start menu.
- **Light theme.** Currently dark-only. Light theme tokens are easy
  to add since QSS is already token-driven.
- **Localization.** All strings are hardcoded English. Qt has
  `tr()` / `.ts` files for i18n if needed.

---

## 6. Maintenance recipes

### 6.1 Rebuild for distribution

After any code change, refresh the binary:

```powershell
# Windows
uv run pyinstaller packaging/lbb.spec --clean --noconfirm
```

```bash
# macOS / Linux
uv run pyinstaller packaging/lbb.spec --clean --noconfirm
```

Output:
- macOS: `dist/LightBurn Bridge.app` (95MB)
- Windows: `dist/LightBurn Bridge/LightBurn Bridge.exe` + supporting DLLs
- Linux: `dist/LightBurn Bridge/LightBurn Bridge` (binary + libs)

To zip for transfer: `zip -r LightBurnBridge-mac.zip "dist/LightBurn Bridge.app"`
or the equivalent in PowerShell:
`Compress-Archive -Path "dist\LightBurn Bridge" -DestinationPath LightBurnBridge-win.zip`.

### 6.2 Update a template

You changed cut settings or canvas size in a `.lbrn2` template under
`templates/`. Update the golden so tests stay green:

```bash
uv run python scripts/regenerate_goldens.py
```

Eyeball the diff in the new golden file — if the only changes are
your intended changes, commit. If anything else moved, investigate
before committing.

### 6.3 Regenerate PDF fixtures

You changed `scripts/generate_fixtures.py` to emit different geometry:

```bash
uv run python scripts/generate_fixtures.py
```

Then regenerate goldens (above) because the new PDFs change the
pipeline's golden output too. Both fixture PDFs and goldens are
byte-stable (deterministic timestamps + fixed seeds) so diffs in git
should be minimal unless you actually changed the design.

### 6.4 Add a new SKU profile programmatically

For automation (e.g., bulk import from a spreadsheet):

```python
from pathlib import Path
from lbb.adapters.sqlite_repo import SqliteProfileRepository
from lbb.core.models import Material, Sku, SkuProfile, Template

DB = Path.home() / ".lightburn-bridge" / "profiles.sqlite"
repo = SqliteProfileRepository(DB)

t = repo.upsert_template(Template(0, "Tumbler 20oz", "templates/tumbler-20oz.lbrn2", 220, 75))
m = repo.upsert_material(Material(0, "Stainless 304", "default.clb", "SS304"))
repo.upsert(SkuProfile(Sku("LB-TUMBLER-20OZ-SS"), t, m, {}))
```

Run once, app picks it up live.

### 6.5 Bump dependency versions

```bash
# update the lockfile to latest matching versions
uv sync --upgrade --extra ui --dev

# run the full suite to confirm nothing broke
uv run pytest

# if green, commit the changed uv.lock
git add uv.lock && git commit -m "chore: bump deps"
```

---

## 7. Troubleshooting

### "uv: command not found" after installing

Restart PowerShell. The uv installer adds itself to `$env:Path` but
existing shells don't pick it up until they're restarted. If still
missing after restart, manually add `%USERPROFILE%\.local\bin` to
PATH via System Properties → Environment Variables.

### Tests pass locally but CI fails on Windows

Most common cause: a test inadvertently depends on POSIX semantics
(`pgrep`, slashes vs backslashes, line endings). The shell-adapter
tests already cover Windows; if a new test breaks on Windows, check
for `subprocess.run` with POSIX commands, hardcoded `/tmp/`, or
file-path string comparisons that assume forward slashes.

### PyInstaller build hangs at "Building EXE"

Usually antivirus scanning the in-progress executable. Add the project
directory and `dist/` to your antivirus exceptions for the duration of
the build. On Windows: Defender → Virus & threat protection settings →
Add exclusion.

### "LightBurn — Not connected" stays red even with LightBurn open

The status pill checks `pgrep -x LightBurn` (POSIX) or
`tasklist /FI IMAGENAME eq LightBurn.exe` (Windows). The match is
case-sensitive and exact. If your LightBurn executable is named
something else (`LightBurn Pro.exe`, `LightBurnPro.exe`,
`lightburn.exe`), the pill will miss it. Workaround: open
`src/lbb/app/container.py` and pass a custom name to the adapter:

```python
LightBurnShellAdapter(app_name="LightBurn Pro")
```

Rebuild and retest. Open an issue with the exact filename and we'll
add detection logic.

### Send button fails with "LightBurn isn't running" but LightBurn is running

Same root cause as above — the process-detection name doesn't match.
Try the workaround above.

### LightBurn opens but the file doesn't load

Means `start "" file.lbrn2` (Windows) or `open -a` (macOS) succeeded
but LightBurn didn't pick up the file. On Windows, this means `.lbrn2`
isn't associated with LightBurn. Right-click any `.lbrn2` → Open With →
Choose another app → check "Always use this app" → pick LightBurn.

### "Error -3 while decompressing data" when picking a PDF

Should be fixed as of `f98205b` (switched thumbnail encoding to QImage,
removed Pillow from the critical path). If you still see this, you may
be running an old build. Rebuild from latest `main`.

### LightBurn crashes when our file is loaded or interacted with

Could be a schema-compatibility issue between our synthesized template
and your specific LightBurn version. Workaround: author a fresh
`templates/wallet-small.lbrn2` (and any other templates) inside your
own LightBurn — see [§3.3](#33-engineer--add-a-new-product-template).
LightBurn-authored templates are guaranteed schema-compatible with
that LightBurn version.

### General "I have no idea what's wrong"

Launch the bundle from PowerShell so stderr is visible:

```powershell
cd "C:\Projects\lightburn-tool\dist\LightBurn Bridge"
.\"LightBurn Bridge.exe"
```

Reproduce the issue. Stack traces from unexpected exceptions now print
to stderr (added in commit `f98205b`). Copy the traceback into an
issue.

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
│       ├── 2026-05-16-lightburn-bridge-design.md       ← system design
│       └── 2026-05-16-lightburn-bridge-mvp-plan.md     ← original TDD plan
│
├── src/lbb/
│   ├── __main__.py             ← entry point (`python -m lbb`)
│   ├── core/                   ← pure domain, no I/O
│   ├── ports/                  ← Protocol interfaces
│   ├── adapters/               ← real I/O implementations
│   ├── app/                    ← orchestration (pipeline, DI)
│   └── ui/                     ← PySide6 widgets, views, theme
│
├── templates/                  ← production .lbrn2 templates
│   └── wallet-small.lbrn2      ← Wallet-Small SKU, 95×110mm
│
├── tests/
│   ├── fixtures/               ← PDFs and templates for tests
│   ├── golden/                 ← byte-stable .lbrn2 snapshots
│   ├── unit/                   ← isolated unit tests
│   ├── integration/            ← pipeline integration tests
│   └── ui/                     ← pytest-qt UI tests
│
├── scripts/
│   ├── generate_fixtures.py    ← emit test PDFs deterministically
│   ├── regenerate_goldens.py   ← refresh golden .lbrn2 snapshots
│   └── seed_demo.py            ← populate ~/.lightburn-bridge/profiles.sqlite
│
├── packaging/
│   └── lbb.spec                ← PyInstaller spec
│
└── .github/workflows/
    └── ci.yml                  ← test + build matrix on Linux/Mac/Windows
```

User data (created at runtime, not in git):

```
~/.lightburn-bridge/             ← macOS / Linux
%USERPROFILE%\.lightburn-bridge\  ← Windows
├── profiles.sqlite             ← SKU profile database (seed_demo populates this)
└── jobs/                       ← generated .lbrn2 files (one per Send click)
```

---

## Appendix — Quick commands cheatsheet

```bash
# Run from source (after uv sync --extra ui --dev)
uv run python -m lbb

# Run tests
uv run pytest

# Run only the UI tests
uv run pytest tests/ui/

# Run a specific test
uv run pytest tests/integration/test_pipeline.py::test_happy_path_loads_to_lightburn -v

# Lint
uv run ruff check
uv run lint-imports

# Build distributable
uv run pyinstaller packaging/lbb.spec --clean --noconfirm

# Seed demo data
uv run python scripts/seed_demo.py

# Regenerate fixtures + goldens after a deliberate change
uv run python scripts/generate_fixtures.py
uv run python scripts/regenerate_goldens.py
```
