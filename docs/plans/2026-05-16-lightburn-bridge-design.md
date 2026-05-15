# LightBurn Bridge — System Design

**Date:** 2026-05-16
**Status:** Validated through collaborative brainstorming
**Owner:** Gabriel (engineering lead)
**Client context:** E-commerce shop in the laser-engraving customization niche. Operators run LightBurn on the shop floor; the office staff fulfill orders. Goal: eliminate manual setup steps between "PDF design arrives" and "laser ready to fire."

---

## 1. Problem statement

The client engraves customized products (wallets, tumblers, plaques, etc.). Each order produces a PDF design. The operator currently:

1. Opens LightBurn.
2. Imports the PDF.
3. Manually selects the correct material/speed/power profile based on what product was ordered.
4. Adjusts layer assignments.
5. Presses Start.

Steps 2–4 are error-prone (wrong settings = ruined product) and slow. We want to collapse 2–4 into a single drag-and-drop that loads a fully-configured `.lbrn2` into LightBurn, with the operator confirming and pressing Start.

## 2. Locked decisions (from brainstorming)

| Decision | Choice | Reason |
|---|---|---|
| Workstation OS | Cross-platform (Win/Mac/Linux) | Client has mixed machines |
| Operator workflow | Operator-assisted (load + verify, **don't** fire) | Safety, reliability, LightBurn's actual capabilities |
| PDF authoring control | Full control — client's design team creates them | Enables a "designer PDF spec" contract |
| SKU scale (default) | Medium (SQLite + LightBurn Material Library) | Scales down to small, up to large without rearchitecting |
| Job trigger | Manual desktop app (drag/pick PDF) | Simplest UX, demo-friendly, extensible later |
| Tech stack | Python 3.12 + PySide6 | Single language, best domain libs, fast to ship, professional UI |

## 3. LightBurn integration — feasibility findings

Research (forum.lightburnsoftware.com, official docs, nuCarve reverse-engineering writeups) established:

**Supported automation surfaces:**
- Windows helper `SendUDP.exe` opens files into a running LightBurn instance
- LightBurn listens on **UDP 127.0.0.1:19840** with documented-by-community commands: `LOADFILE://`, `FORCELOAD://`, `START`, `STATUS`, `PING`, `CLOSE`, `FORCECLOSE` — returns `OK`
- `.lbrn2` files are **plain XML** — `<CutSetting>` blocks define per-layer parameters; shapes carry `CutIndex` (0–29) pointing at the layer
- PDF import auto-maps stroke colors to LightBurn's fixed 30-color palette → cut layers
- Material Library (`.clb`) files store presets; layers can `Link` to them (live-synced)

**Hard limits:**
- **No official API, SDK, plugin system, or scripting interface.** Confirmed by LightBurn staff July 2025 ("on the long-term roadmap, no timeline").
- **No headless mode** — LightBurn GUI must be running.
- `.lbrn2` and `.clb` schemas are **reverse-engineered**; LightBurn updates can break us.
- Windows is the only first-class CLI target; Mac/Linux requires raw UDP plumbing.
- No completion callback for DSP controllers (Ruida/GRBL); galvo controllers expose I/O pins but we're not targeting unattended firing.

**Sources** (key URLs for ongoing reference):
- Forum 9297 — Launch via CLI: https://forum.lightburnsoftware.com/t/launch-lightburn-and-load-files-into-lightburn-using-command-line-interface/9297
- Forum 59622 — Full UDP command list: https://forum.lightburnsoftware.com/t/full-list-of-lightburn-udp-commands/59622
- Forum 176431 — Staff response on CLI/API roadmap: https://forum.lightburnsoftware.com/t/request-command-line-interface-cli-tool-for-batch-exporting-lbrn2-projects/176431
- nuCarve LBRN format breakdown: https://nucarve.com/lightburn-file-format-whats-in-a-shape/
- Palette reference: https://docs.lightburnsoftware.com/latest/Reference/UI/ColorPalette/
- Material Library docs: https://docs.lightburnsoftware.com/latest/Reference/MaterialLibrary/

## 4. Architecture

### 4.1 High-level data flow

```
┌───────────────────────┐    drag/pick      ┌──────────────────────────┐
│  Operator's desktop   │ ───── PDF ───────▶│  LightBurn Bridge (our    │
│   (LightBurn open)    │                   │  PySide6 desktop app)     │
└───────────────────────┘                   └──────────────────────────┘
              ▲                                          │
              │  UDP: LOADFILE://path                    │
              │                                          ▼
   ┌──────────┴──────────┐                  ┌───────────────────────────┐
   │  LightBurn process  │ ◀── .lbrn2 ───── │  Job Pipeline (in-app):   │
   │  (any version)      │   on disk        │   1. SKU extractor        │
   └─────────────────────┘                  │   2. Profile resolver     │
                                            │   3. Preflight validator  │
                                            │   4. Template builder     │
                                            │   5. UDP dispatcher       │
                                            └───────────────────────────┘
                                                       │
                                                       ▼
                                       ┌───────────────────────────────┐
                                       │  Local state                  │
                                       │   • profiles.sqlite (mapping) │
                                       │   • templates/*.lbrn2 (base)  │
                                       │   • LightBurn Material Lib    │
                                       │     (.clb, shared via Qt)     │
                                       │   • settings.json (paths)     │
                                       │   • audit.log (every job)     │
                                       └───────────────────────────────┘
```

### 4.2 Components

1. **UI shell (PySide6)** — drag-drop zone, job preview, settings/admin pages
2. **Job pipeline** — pure-Python, no UI deps; composable, testable, swappable
3. **SKU extractor** — pulls SKU from filename (regex driven, configurable)
4. **Profile resolver** — queries SQLite: `SKU → MaterialProfile` (template + material + overrides)
5. **Preflight validator** — vector-only check, palette-match check, canvas-fit check
6. **Template builder** — opens a base `.lbrn2` template, injects PDF geometry, writes job-specific `.lbrn2` to temp
7. **UDP dispatcher** — sends `PING` to verify LightBurn is up, then `LOADFILE://<path>`
8. **Local state** — SQLite (SKU mappings) + on-disk templates + LightBurn's own Material Library (for cut parameters)

### 4.3 Two-tier settings model

- **What template + material to use for this SKU** lives in **our SQLite** (per-SKU)
- **Actual cut parameters** (speed, power, passes, air assist, focus) live in **LightBurn's own Material Library** (`.clb`)

This means the laser engineer maintains presets in LightBurn (the tool they already trust); the office admin maintains SKU→preset mapping in our UI. The right tool for each job; no duplication.

## 5. SKU resolution & data model

### 5.1 Filename convention (PDF spec contract)

```
<SKU>__<anything>.pdf
e.g.   LB-WALLET-LEATHER-S__order-2381.pdf
       LB-TUMBLER-20OZ-SS__customer-name.pdf
```

Two underscores delimit SKU. Configurable regex in settings allows future convention changes without code edits.

### 5.2 SQLite schema (three tables)

```sql
CREATE TABLE materials (              -- engraver-facing presets
  id              INTEGER PRIMARY KEY,
  name            TEXT UNIQUE,        -- "Leather 2mm — Vegetable Tan"
  clb_library     TEXT,               -- which .clb file to link
  clb_entry       TEXT,               -- the exact entry name inside it
  notes           TEXT
);

CREATE TABLE templates (              -- per product-type base .lbrn2
  id              INTEGER PRIMARY KEY,
  name            TEXT UNIQUE,        -- "Wallet — Small"
  lbrn2_path      TEXT,               -- on-disk template
  canvas_w_mm     REAL,
  canvas_h_mm     REAL
);

CREATE TABLE sku_profiles (           -- the actual lookup table
  sku             TEXT PRIMARY KEY,   -- "LB-WALLET-LEATHER-S"
  template_id     INTEGER REFERENCES templates,
  material_id     INTEGER REFERENCES materials,
  overrides_json  TEXT,               -- optional per-SKU tweaks
  updated_at      DATETIME,
  updated_by      TEXT
);
```

### 5.3 Unknown-SKU fallback

When a SKU has no profile:
1. UI shows "Unknown SKU" card with the parsed filename
2. Operator picks template + material from dropdowns (autocomplete) → offered "save this mapping"
3. Job continues; audit log captures who created the mapping
4. **Never silently guess.** Wrong settings = ruined product

### 5.4 Bulk authoring

CSV import/export in admin UI for onboarding hundreds of SKUs from an existing product catalog spreadsheet.

## 6. LightBurn integration layer

### 6.1 Template-plus-PDF composition

For each product type, author a base `.lbrn2` template **once, by hand in LightBurn**:
- Correct canvas size + machine origin
- Jig alignment marks pre-positioned
- Layer slots **already linked** to Material Library entries
- A clearly-named placeholder group (`<Group Name="DESIGN_PLACEHOLDER">`)

At job time, `TemplateBuilder`:

```
1. Load base template (.lbrn2 XML via lxml)
2. Convert PDF vectors to SVG (pypdfium2 → svgwrite)
3. Replace DESIGN_PLACEHOLDER group with parsed shapes,
   tagged with CutIndex values matching the template's pre-built layers
4. Write to temp:  /tmp/lightburn-bridge/<sku>-<timestamp>.lbrn2
5. Golden-file schema sanity check
6. Hand off to UDP dispatcher
```

**Why generate `.lbrn2` instead of just opening the PDF directly?** Determinism. Generated output is byte-stable and test-coverable; runtime palette mapping is fragile across LightBurn versions.

### 6.2 UDP dispatcher

```python
class LightBurnUDPAdapter(LightBurnPort):
    HOST, PORT = "127.0.0.1", 19840
    TIMEOUT = 2.0

    def is_running(self) -> bool:
        return self._roundtrip(b"PING") == b"OK"

    def load_file(self, path: Path) -> None:
        if not self.is_running():
            raise LightBurnNotRunning()
        resp = self._roundtrip(f"LOADFILE://{path}".encode())
        if resp != b"OK":
            raise LightBurnRejected(resp)
```

Three commands cover the MVP: `PING`, `LOADFILE://`, `STATUS`. **We deliberately do NOT send `START`** — operator presses Start physically. That is our safety boundary.

### 6.3 Schema version pinning

- On first run, detect installed LightBurn version (parse executable metadata)
- Maintain `schemas/lightburn-v1.7.x.json` describing tested-good XML shape per version
- On mismatch, show yellow banner: *"Untested LightBurn version — please test one job before going live."* Don't break; warn loud.

### 6.4 Port interface (clean architecture)

```python
class LightBurnPort(Protocol):
    def is_running(self) -> bool: ...
    def load_file(self, path: Path) -> None: ...
    def status(self) -> LBStatus: ...
```

Real impl = UDP. Test impl = in-memory fake. If LightBurn ever ships an HTTP API, only this file changes.

## 7. UI/UX

Visual language: **dark, technical, confident** — laser-shop floor lighting is dim, screens used through safety glasses. Linear/Raycast aesthetic, not consumer-glossy.

### 7.1 Screen 1: Operator Home (the 90% screen)

```
┌──────────────────────────────────────────────────────────────────────┐
│  ◐  LightBurn Bridge                              ● LightBurn Ready  │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│                  ┌─────────────────────────────────┐                 │
│                  │       ⤓  Drop PDF here          │                 │
│                  │      or click to browse         │                 │
│                  │   filename must contain SKU     │                 │
│                  └─────────────────────────────────┘                 │
│                                                                      │
│   Recent jobs                                            ⟳ refresh   │
│   ┌──────────────────────────────────────────────────────────────┐   │
│   │ 05:32  LB-WALLET-LEATHER-S__order-2381.pdf      ✓ Sent       │   │
│   │ 05:18  LB-TUMBLER-20OZ-SS__sarah-k.pdf          ✓ Sent       │   │
│   │ 04:55  unknown-design.pdf                       ⚠ SKU added  │   │
│   └──────────────────────────────────────────────────────────────┘   │
│                                          [ ⚙ Admin ]  [ 📋 Audit ]   │
└──────────────────────────────────────────────────────────────────────┘
```

Status pill is real-time UDP `PING`. Red = LightBurn isn't running → "Open LightBurn" button surfaced.

### 7.2 Screen 2: Job Preview (the confirmation step — the "wow")

After a PDF is dropped, **before** firing UDP, we show what we found:

```
┌──────────────────────────────────────────────────────────────────────┐
│  ← Back                                          LB-WALLET-LEATHER-S │
├──────────────────────────────────────────────────────────────────────┤
│   ┌─────────────────────────┐     SKU detected                       │
│   │   [PDF thumbnail        │     LB-WALLET-LEATHER-S                │
│   │    via pypdfium2]       │                                        │
│   │                         │     Product template                   │
│   │                         │     Wallet — Small  (95 × 110 mm)      │
│   │                         │                                        │
│   │                         │     Material profile                   │
│   │                         │     Leather 2mm — Vegetable Tan        │
│   └─────────────────────────┘       Speed   180 mm/s                 │
│                                     Power   42 %                     │
│   ✓ PDF is vector-only                Passes  1                      │
│   ✓ All strokes match palette         Air     ON                     │
│   ✓ Fits canvas (94.2 × 108.7 mm)                                    │
│                                          [ ✕ Cancel ]  [ ⏎ Send →  ] │
└──────────────────────────────────────────────────────────────────────┘
```

Preflight checks run synchronously. **Any red check blocks the Send button** — failing loud beats failing silent on a $300 piece of leather.

### 7.3 Screen 3: Admin

Tabbed: **SKUs** · **Templates** · **Materials** · **Settings** · **Audit log**. Sortable/filterable tables, inline-editable. CSV round-trip on SKUs.

### 7.4 Design system

- Dark theme by default (laser floor)
- Inter / IBM Plex Sans
- 8pt grid, Qt Fluent base, custom QSS color tokens
- Status colors: lime `#A3E635` good, amber `#FBBF24` warn, rose `#FB7185` error — high-contrast through safety glasses
- **No animations on safety-critical actions**

## 8. Code structure

```
lightburn-bridge/
├── pyproject.toml              # uv / hatchling
├── src/lbb/
│   ├── __main__.py             # python -m lbb
│   ├── core/                   # ── pure domain, no I/O ──
│   │   ├── models.py           #    Sku, Profile, Template, Material (frozen dataclasses)
│   │   ├── extractor.py        #    filename → Sku
│   │   ├── preflight.py        #    PDF validation rules
│   │   ├── template_builder.py #    PDF + template → .lbrn2 bytes
│   │   └── errors.py           #    typed exceptions
│   ├── ports/                  # ── interfaces only ──
│   │   ├── lightburn.py        #    LightBurnPort Protocol
│   │   ├── repository.py       #    ProfileRepository, TemplateRepository, AuditLog
│   │   └── pdf.py              #    PdfReader Protocol
│   ├── adapters/               # ── real I/O lives here ──
│   │   ├── lightburn_udp.py
│   │   ├── lightburn_fake.py   #    in-memory fake (tests)
│   │   ├── sqlite_repo.py
│   │   └── pdfium_reader.py
│   ├── app/                    # ── orchestration ──
│   │   ├── pipeline.py         #    SkuExtract → Resolve → Preflight → Build → Dispatch
│   │   ├── job.py              #    Job state machine
│   │   └── container.py        #    DI wiring (one place)
│   └── ui/                     # ── PySide6 ──
│       ├── main_window.py
│       ├── views/              #    Home, JobPreview, Admin, AuditLog
│       ├── widgets/            #    DropZone, StatusPill, PdfThumb
│       └── theme/              #    QSS + tokens
├── tests/
│   ├── unit/                   # core/ in isolation
│   ├── integration/            # pipeline w/ fakes
│   ├── golden/                 # .lbrn2 byte-stable fixtures
│   └── e2e/                    # real LightBurn (CI-gated)
├── schemas/                    # version-pinned LightBurn XML shapes
└── docs/
    ├── plans/
    └── designer-pdf-spec.md    # contract for client's designers
```

### 8.1 Design patterns (each earns its keep)

| Pattern | Where | Reason |
|---|---|---|
| Hexagonal / Ports & Adapters | `core` + `ports` + `adapters` | LightBurn API may ship someday — only adapter changes |
| Pipeline (chain of stages) | `app/pipeline.py` | Pure-function stages; replayable from audit log; testable in isolation |
| Result/Either over exceptions | Stage returns | Preflight failures are expected, not exceptional |
| Repository | `ports/repository.py` | SQL hidden from rest of code; easy to fake |
| Composition root / DI container | `app/container.py` | Single wiring point; swap real↔fake in one place |
| Command Query Separation in UI | `ui/views/*` | Avoids Qt signal spaghetti |

### 8.2 Architectural lint (enforced)

- `core/` may never import from `adapters/` or `ui/` (import-linter enforced)
- `ui/` may never import from `adapters/` (must go through `app/container`)
- Every `LightBurnPort` call goes through an audit-log decorator
- `.lbrn2` bytes are built **only** in `core/template_builder.py` — single source of truth

## 9. Testing strategy

| Layer | Tooling | Coverage | Speed |
|---|---|---|---|
| Unit | `pytest` | `core/` in isolation | ~1s |
| Property-based | `hypothesis` | SKU extractor regex | ~5s |
| Golden file | `pytest` + `lxml` | `.lbrn2` byte-stable per LightBurn version | ~2s |
| Integration | `pytest` + `LightBurnFake` | Full pipeline w/ fake UDP | ~5s |
| UI smoke | `pytest-qt` | Drop-zone, preview, send-button states | ~10s |
| E2E (CI-gated) | Real LightBurn in Windows VM | 5 canonical SKUs load correctly | ~2 min |

Golden-file tests are the strategic moat — they catch the day LightBurn ships a `.lbrn2` schema change *before* it ruins a customer's product.

## 10. Distribution

- **Build:** GitHub Actions matrix → Win/Mac/Linux. `pyinstaller --onefile` per OS.
- **Signing:** Windows SignTool (avoid SmartScreen warnings). macOS notarized via `notarytool`.
- **Auto-update:** `pyupdater` or version-check-on-launch against GitHub release. Critical for shipping schema-pin updates.
- **First-run wizard:** detect LightBurn install path, verify UDP listener, ask for Material Library path.

## 11. Roadmap

**MVP (Weeks 1–3) — demo-able**
- Drop-zone → SKU extract → SQLite lookup → static template → UDP load
- Job preview screen with preflight checks
- Admin CRUD for SKUs/Templates/Materials
- 5 pre-seeded SKUs for client demo
- Designer PDF spec document delivered to client

**v1 (Weeks 4–6) — production**
- Audit log + CSV export
- CSV import for bulk SKU onboarding
- Auto-update channel
- Signed Windows + macOS builds
- Operator training doc + 5-min screencast

**v2 (Weeks 7+) — upsell**
- Watched-folder mode
- Shopify / WooCommerce job-source adapter
- Multi-workstation: central settings server (FastAPI), workstation app pulls
- Job analytics dashboard
- Per-SKU "first-run preview job" — auto-engrave on test material first

## 12. Risk register

| Risk | Mitigation |
|---|---|
| LightBurn ships breaking schema change | Schema version pinning + auto-update + golden tests + visible warning banner |
| UDP port collision | Detect on startup, surface clearly, fall back to file-drop hot folder |
| Operator overrides settings then forgets | Audit log every change; "revert to SKU defaults" button on preview |
| Designer ships malformed PDF | Preflight blocks job loud and clear; "what's wrong" hints |
| Schema reverse-engineering wrong | Start with templates **hand-authored in LightBurn**, then modify. Remixer, not creator. |
| `pypdfium2` PDF vector extraction edge cases | Golden-file tests across a corpus of real client PDFs before MVP ships |

## 13. What makes this trustworthy

1. **Honest about LightBurn's limits.** No vaporware promises of unattended firing.
2. **Brain lives in tools the client already trusts.** Material Library settings stay in LightBurn. Our app references; doesn't replace.
3. **Preflight catches problems before they ruin material.** Every product *not* scrapped pays for the tool.
4. **One operator-facing screen with a giant drop zone.** Anyone uses it on day one.
5. **Admin imports 100 SKUs from spreadsheet.** No engineer required for onboarding.

## 14. Open follow-ups (for client conversation)

1. Confirm OS distribution across their workstations (we built for cross-platform; double-check)
2. Confirm controller type (Ruida / GRBL / Galvo / xTool) — affects v2 unattended discussion only
3. Confirm whether the design team can adopt the PDF spec (filename + palette colors)
4. Confirm SKU count and growth rate — locks default vs. large scale architecture
5. Confirm LightBurn version + license tier (some features are tier-gated)
