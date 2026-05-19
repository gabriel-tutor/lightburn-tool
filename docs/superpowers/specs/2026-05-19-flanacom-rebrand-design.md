# Flanacom Rebrand — design

**Date:** 2026-05-19
**Status:** Approved
**Driver:** Client demo — the app needs to wear the client's brand (Flanacom)
to feel like *their* tool, not a generic engineering utility. Logo
(`flanacom-logo.jpg`) ships with the project; theme should reflect their
e-commerce identity (warm orange + clean black wordmark).

## Identity

| Aspect | Before | After |
|---|---|---|
| Window title | "LightBurn Bridge" | "Flanacom Tool" |
| Bundle name | `dist\LightBurn Bridge\…` | `dist\Flanacom Tool\Flanacom Tool.exe` |
| App icon | (generic PyInstaller default) | Multi-res ICO from Flanacom logo |
| Header wordmark | "LightBurn Bridge" (two-tone text) | Flanacom logo image + "Engraver" subtitle |
| Bundle identifier (macOS) | `com.hauke.lightburn-bridge` | `com.flanacom.tool` |

## Theme — light mode

Replace the dark/cyan theme with light/orange. Token table below; QSS rewritten
to match. `tokens.py` and `app.qss` stay in sync as a hard rule.

| Token | Old (dark) | New (light) | Use |
|---|---|---|---|
| `BG` | `#0A0C12` | `#FAFAFA` | Main window background |
| `SURFACE` | `#11141C` | `#FFFFFF` | Card surfaces, thumbnail card |
| `SURFACE_ELEVATED` | `#161A25` | `#FFFFFF` (+ shadow) | Modals, raised cards |
| `SURFACE_HOVER` | `#1B2030` | `#F5F5F4` | Ghost-button hover |
| `BORDER` | `#222837` | `#E5E7EB` | Subtle borders |
| `BORDER_STRONG` | `#2D3447` | `#D1D5DB` | Active borders |
| `TEXT` | `#E6E8EE` | `#1A1A1A` | Primary text (matches wordmark black) |
| `TEXT_DIM` | `#8A92A6` | `#6B7280` | Section labels, metadata |
| `TEXT_FAINT` | `#5B6479` | `#9CA3AF` | Hints, footnotes |
| `ACCENT` | `#7DD3FC` (cyan) | `#F58A1F` (Flanacom orange) | Primary action, focus, monocode |
| `ACCENT_HOVER` | `#A5E0FB` | `#FFA947` | Lighter on hover |
| `ACCENT_PRESSED` | `#5CC3F0` | `#D97706` | Darker on press |
| `ACCENT_DIM` | `#3FA0CC` | `#FBBF77` | Faded orange (e.g. focus rings) |
| `OK` | `#A3E635` | `#10B981` | Preflight ✓ |
| `WARN` | `#FBBF24` | `#F59E0B` | (unused for now) |
| `ERROR` | `#FB7185` | `#DC2626` | Preflight ✕ |
| `LAYER_CUT` | `#FFFFFF` | `#1A1A1A` | Black represents the C00 cut layer cleanly on a light bg |
| `LAYER_ENGRAVE` | `#7DD3FC` | `#F58A1F` | Engrave shown in Flanacom orange |

## UX polish

- **Border radii unified at 8px** (was a mix of 8/10/14/22 — feels more
  modern when consistent).
- **Drop zone**: dashed orange border (`#F58A1F`), light off-white interior.
  On drag-over: solid orange border, faint peach (`#FFF3E5`) fill. Helper
  text in dim. Upload glyph in orange.
- **Primary buttons** (Send / Open in LightBurn, Use SKU): solid orange,
  subtle vertical gradient `#FFA947→#F58A1F`. White text. Hover lifts to
  brighter orange + soft shadow. Pressed flattens to `#D97706`.
- **Ghost buttons** (Cancel, Admin, Audit): transparent → light-grey hover
  (`#F5F5F4`) with orange text. No border in idle state.
- **Card shadows**: 0 1px 2px rgba(0,0,0,.04) + 0 1px 3px rgba(0,0,0,.06)
  for raised surfaces. QSS can't do real shadows; approximated via
  `QGraphicsDropShadowEffect` on key cards.
- **Status pill**: green dot (`#10B981`) on running, grey dot (`#9CA3AF`)
  on stopped. Subtle pill background `#F5F5F4`.

## Implementation

### Files (~10)

- `packaging/lbb.spec` — rename `name="Flanacom Tool"`, add `icon=` arg
  to EXE, bundle `assets/` directory in `datas`, update macOS bundle id.
- `src/lbb/ui/theme/tokens.py` — full light palette.
- `src/lbb/ui/theme/app.qss` — full light rewrite.
- `src/lbb/ui/main_window.py` — window title "Flanacom Tool", `setWindowIcon`.
- `src/lbb/__main__.py` — `QApplication.setWindowIcon(...)` so the icon
  shows in the OS taskbar before the main window exists.
- `src/lbb/ui/views/home.py` — header replaces wordmark text with the
  logo image (`QLabel` + `QPixmap`); "Engraver" subtitle in dim.
- `src/lbb/ui/views/job_preview.py` — drop hardcoded `#B8C2DC` color on
  layer_setup_label; lean on QSS instead.
- `assets/flanacom.ico` — NEW (generated from JPG via PIL,
  resolutions 16, 24, 32, 48, 64, 128, 256).
- `assets/flanacom-logo.png` — NEW (logo rendered at ~64px height for the
  header).
- One-shot script `scripts/build_brand_assets.py` to (re)generate the .ico
  and .png from the source JPG so the process is reproducible.

### Tests

- All existing UI tests stay passing — they assert structure (object
  existence, signal emission, text presence), not pixel values.
- New: a smoke test confirms the brand asset script generates valid output.
- The "Send to LightBurn" → "Open in LightBurn" rename has already landed,
  no test churn from that here.

## Non-goals (out of scope, follow-up if requested)

- Replacing every unicode glyph (●, ▾, ⤓) with SVG icons.
- Localization (Qt `tr()` / `.ts` scaffolding).
- Animated cross-fades on view transitions.
- Light/dark toggle — single light theme for now.
