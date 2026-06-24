# Close Previous LightBurn Job (Frictionless Engrave) — Design

**Date:** 2026-06-25
**Status:** Approved (design), pending implementation
**Context:** Hauke wants no manual action to close the previously-opened PDF in
LightBurn between engraving sides. Reinstates the "close-previous-job" capability
that existed pre-rebuild (commit `4d1366`, in the deleted PySide6 `MainWindow`)
but wires it into the current pywebview flow with a single quick confirm.

## Problem

`FulfillmentService.engrave_side` currently downloads the side's PDF and calls
`lightburn.load_file(pdf)` — it never closes the previous job. So when the
operator engraves the next side, LightBurn still has the prior PDF loaded and
surfaces a **"Save changes?"** dialog the operator must dismiss manually. That is
friction Hauke wants removed.

The capability already exists and is unused: `LightBurnPort.close_running()` and
`LightBurnShellAdapter.close_running()` (force-close via `taskkill /F /IM
LightBurn.exe` on Windows / `pkill -x LightBurn` on POSIX, tolerant of "no
process") survived the rebuild. We only need to invoke it from the engrave flow,
gated by a one-click confirm.

## Decision (from brainstorm)

**Auto-close the previous job, with a quick one-click confirm.** When the
operator clicks Engrave and LightBurn is already running, show
"LightBurn still has a job open. Close it and open this side?" → **[Close & open]
/ [Cancel]**. On confirm, force-close LightBurn (no save dialog) and open the new
PDF fresh. When LightBurn is **not** running (first engrave of the session, or
already closed), there is **no prompt** — it just opens.

- Force-close discards unsaved LightBurn state; acceptable because the operator
  finishes the cut before clicking the next side, and the confirm is the guard.
- `close_running()` is safe to call when LightBurn isn't running.

## Architecture

No new ports/adapters, no new dependencies. The close decision is a frontend UX
gate (the confirm); the backend just exposes a `close_previous` flag on engrave
and invokes the existing port method.

### Service — `app/fulfillment_service.py`

`engrave_side(order_number, file_key, close_previous=False)`. After a successful
download (so we never kill LightBurn when the download itself fails), if
`close_previous` is set, call `self.lightburn.close_running()` **before**
`self.lightburn.load_file(pdf)`. Mark-on-success ordering is unchanged (the key
is marked only after a successful load). Ordering: download → (close if
requested) → load → mark.

### Bridge — `web/bridge.py`

`engrave_side(self, order_number, file_key, close_previous=False)` → pass the
flag through to the service. (`bridge-client.js`'s generic `wrap()` already
forwards all args, so `API.engraveSide(order, fileKey, closePrevious)` reaches
the bridge with no bridge-client change.)

### Front-end — `web/assets/`

Split the current `engrave(pi, si)` into:
- **`engrave(pi, si)`** — the entry/decision point. `if(busy) return;` then a
  fresh `await API.lightburnStatus()`. If running → open the confirm modal whose
  "Close & open" runs `runEngrave(pi, si, true)`; Cancel aborts (nothing
  happens). If not running → `runEngrave(pi, si, false)` directly.
- **`runEngrave(pi, si, closePrevious)`** — the existing engrave body
  (busy lock, spinner, `viewToken` guard, try/finally), but it passes
  `closePrevious` to `API.engraveSide(order, file_key, closePrevious)` and sets
  the pill text to "Closing previous · opening LightBurn…" when closing, else
  "Opening LightBurn…".

`engraveNext()` keeps calling `engrave(...)`, so it inherits the prompt.

A dedicated small confirm modal `#lbModalBg` (separate from the ship `#modalBg`
to avoid entangling its gift-box logic) with [Cancel] / [Close & open]. Escape
and backdrop-click close it (extend the existing keydown/backdrop handlers).

## Error handling

- Cancel → no engrave, no state change.
- `lightburn_status()` throwing during the pre-check → treat as not running
  (no prompt, proceed) — never block the engrave on a status hiccup.
- Engrave failures still surface as an error toast; `busy`/spinners reset in
  `finally` (unchanged from the hardened flow).
- `close_running()` never raises (tolerates no process); a non-200 / OS error in
  the subsequent `load_file` is caught by the existing
  `(EngravingApiError, LbbError, OSError)` handler → `{ok:false}` + the key is
  NOT marked.

## Testing (TDD)

- `engrave_side(..., close_previous=True)` calls `close_running()` **before**
  `load_file` (fake records an ordered event log: `['close', ('load', pdf)]`).
- `engrave_side(..., close_previous=False)` never calls `close_running`;
  `loaded` still contains the pdf (existing assertions preserved).
- Download failure → `close_running` NOT called, returns `{ok:false}`.
- Default param: `engrave_side(order, file_key)` → `close_previous` defaults
  False.
- Bridge passes the flag through.
- Front-end: `node --check` + grep guards (confirm modal present, `runEngrave`
  defined, `engraveSide` called with 3 args); live GUI smoke.
- Existing 151 tests stay green.

## Out of scope

- A "don't ask again this session" toggle (YAGNI; add later if Hauke wants fewer
  confirms).
- Any change to how LightBurn runs the job (we only manage open/close).
