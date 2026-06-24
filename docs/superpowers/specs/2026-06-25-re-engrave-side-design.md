# Re-engrave a Finished Side — Design

**Date:** 2026-06-25
**Status:** Approved (design), pending implementation
**Builds on:** the close-previous-LightBurn flow (`runEngrave` / `#lbModalBg`
confirm-modal pattern), merged to main.

## Problem

When a side is already engraved, the operator sometimes needs to redo it (bad
burn, smudge, mis-position). Today the green **"✓ Engraved"** button doubles as a
re-open trigger (`onclick="engrave(active,si)"`, title "Re-open in LightBurn"),
but that is (a) not discoverable as "re-engrave" — it looks like a status — and
(b) has no re-engrave-specific confirmation, so an accidental click re-opens the
job. Hauke wants a clear, simple icon to re-engrave, gated by a confirmation.

## Decision (from brainstorm)

On an already-engraved side, split the control into:
- **`✓ Engraved`** — a plain, non-clickable **status chip** (removes the
  accidental re-open).
- A small **↻ re-engrave icon button** (ghost style, tooltip "Re-engrave").

Clicking ↻ opens a quick confirm — **"Re-engrave <Side>? The design will reopen
in LightBurn for another run."** → **[Cancel] [Re-engrave]**. On confirm, the
side's PDF re-opens in LightBurn for another run.

**One confirm, not two:** re-engrave usually happens while LightBurn still has the
job open. The re-engrave confirm *is* the safety gate, so it handles the close
silently — on "Re-engrave" it checks `lightburn_status()` and, if running, passes
`close_previous=true` to the engrave (force-close + reopen fresh, no "Save
changes?" dialog, pill reads "Closing previous · opening LightBurn…"). No second
prompt.

## Architecture — frontend only

**No backend change.** `engrave_side(order, file_key, close_previous)` already
downloads → (optionally closes) → opens → marks; marking an already-engraved key
is idempotent (the side stays "Engraved"). Re-engrave just calls the existing
`runEngrave(pi, si, closePrevious)`. So this is purely `web/assets/`.

### Front-end (`web/assets/app.js`, `index.html`, `app.css`)

- **Sides rendering** (`renderOrder`, the `#sides` map): for an engraved side,
  render a `<span class="sbtn ok done">✓ Engraved</span>` status chip **plus** a
  `<button class="sbtn redo" title="Re-engrave" onclick="askReengrave(active,si)">`
  with a circular-arrow (↻) icon. Un-engraved sides keep the existing
  `Engrave <side>` button unchanged.
- **Confirm modal** `#reModalBg` (mirrors `#lbModalBg`): dynamic text in
  `#reText` ("Re-engrave <Side>? …"), [Cancel] / [Re-engrave]. Helpers:
  - `askReengrave(pi,si)` — `if(busy) return`; set `#reText`, store
    `_reSide={pi,si}`, show the modal.
  - `confirmReengrave()` — read `_reSide`, `closeReModal()`, fresh
    `await API.lightburnStatus()` (try/catch → not running on error),
    `runEngrave(pi,si, running)`.
  - `closeReModal()` — null-safe hide + clear `_reSide`.
- **Navigation safety:** `showView()` clears the pending re-engrave confirm too
  (`closeReModal()`), same pattern as the close-previous fix.
- **Escape / backdrop:** the existing keydown handler also calls
  `closeReModal()`; add a `#reModalBg` backdrop-click listener.
- **Toast nicety:** `runEngrave(pi, si, closePrevious, isRedo=false)` — when
  `isRedo`, the success toast says "<Side> re-engraved" instead of "engraved".
  `confirmReengrave` passes `isRedo=true`; the normal engrave path passes the
  default. (Keeps the close-previous flow's call sites valid via the default.)

## Error handling

- Cancel / Escape / backdrop → no engrave, no state change, no busy/spinner.
- `lightburn_status()` throwing during the pre-check → treat as not running
  (proceed without close) — never block re-engrave on a status hiccup.
- Re-engrave failure surfaces an error toast; `busy`/spinners reset in
  `runEngrave`'s `finally` (unchanged).

## Testing

Frontend has no unit harness → `node --check` + grep guards:
- engraved side renders a non-clickable `✓ Engraved` chip + a `redo` button that
  calls `askReengrave`; `#reModalBg` present; `confirmReengrave` routes to
  `runEngrave(..., true)`; `showView` clears `_reSide`.
- Existing 155 backend tests stay green (no backend change).
- Live GUI smoke: re-engrave an engraved side → confirm → LightBurn closes &
  reopens that PDF; Cancel/Escape do nothing; un-engraved sides unchanged.

## Out of scope

- Any backend/API change (none needed).
- Keeping the "✓ Engraved" chip clickable (deliberately a pure status; the ↻
  icon is the single, confirmed re-engrave path).
- A re-engrave audit trail / counter (YAGNI).
