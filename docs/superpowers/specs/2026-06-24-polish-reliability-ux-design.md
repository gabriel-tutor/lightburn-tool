# Polish, Reliability & UX Hardening — Design

**Date:** 2026-06-24
**Status:** Approved (design), pending implementation
**Builds on:** the live-API tool (`2026-06-22`) and dynamic order screen (`2026-06-23`).

## Problem

The tool works end-to-end but a three-part audit (interaction integrity, UX
states/feedback, data/CRUD/resilience) found concrete gaps that either break in
edge cases or make the app feel static/janky. The goal: every button, nav, flow,
toast, loading state, and write path is correct, resilient, and feels alive — no
gaps, no regressions — so it impresses the client (Hauke).

Every item below is a real finding traced through the actual code against the
live API. Items the audit confirmed already-correct are explicitly preserved.

## Principles

- **Truthful actions:** `engrave` and `ship` trigger real-world effects (launch
  LightBurn / write shipped status) — they must NEVER update optimistically.
  Only cheap metadata writes (status pill, flag-for-revision) may update
  optimistically and reconcile.
- **No uncaught throws reach the user:** every async action degrades to a toast.
- **No regressions:** the existing 141 tests stay green; new behavior is TDD'd.
- **No new runtime dependencies; no architecture changes.**

## A. Backend reliability

### A1. Bounded retry + backoff in the HTTP transport
`UrllibTransport.request` currently makes one attempt; any `URLError`/timeout/
`OSError` raises, and a single flaky GET empties the whole dashboard. Add bounded
retry (default 3 attempts) with exponential backoff + jitter for: transport
exceptions (`URLError`/`TimeoutError`/`OSError`) and retryable HTTP status codes
(`429`, `500`, `502`, `503`, `504`). Do NOT retry other 4xx. Backoff is injectable
(a `sleep` callable) so tests run instantly. GET and POST both benefit; POST
retry is safe here because the only POST is an idempotent status set.

### A2. Expired signed-URL fallback re-GET
`download_file` resolves a URL via the 50-min staleness timer, but the signed
URL's 1h TTL starts at server mint time (before our fetch), so the timer cannot
guarantee a live link. On a download response that indicates an expired/invalid
link (`400`/`403`/`410`), force one `self._fetch()` to mint fresh URLs, re-resolve
the key, and retry the download once before raising. Applies to engraving PDFs,
the product image, and the shipping label.

### A3. No uncaught backend exceptions
- `product_image`: wrap the `path.read_bytes()` + base64 encode in try/except so a
  corrupt/partial cached file returns `{"ok": False}` instead of throwing.
- `engrave_side`: broaden the post-download `except` to also catch `OSError`
  (not only `EngravingApiError`/`LbbError`), so any LightBurn-launch failure
  becomes `{"ok": False, "error": ...}` and the key is NOT marked engraved.

### A4. Drop the dead `qty` field
`Product.qty` is never populated from the API (no per-product quantity exists)
and is unused by the frontend. Remove `qty` from `Product` and from the
`get_order` payload to eliminate a misleading always-`1` field. (`amount` is the
real order item count and stays.)

## B. Frontend robustness

### B1. `try/finally` on every async action
`engrave`, `confirmShip`, `onStatusSelect`, `flagRevision`, `engraveNext` must
reset `busy` and clear any loading class in a `finally`. Today if the bridge
rejects, `busy` stays `true` and the order view freezes permanently.

### B2. Stale-request guard
A late `getOrder`/`engrave`-refetch can resolve after the operator navigated away
and overwrite `CURRENT`. Introduce a monotonically increasing `viewToken`; capture
it before each await; on resolve, bail if the token changed (the pattern already
used correctly in `loadProductPhoto`). Apply to `openOrder`, `engrave`'s refetch,
`onStatusSelect`, `flagRevision`.

### B3. Extend the `busy` lock to all writes
Set `busy=true` around ship/status/flag (not just engrave) and disable the
relevant controls, preventing overlapping/contradictory POSTs.

### B4. Defensive guards
- `tasksOf`/`firstPendingProduct`: tolerate a missing `products` array
  (`o.products||[]`) so `openOrder` never throws before `renderOrder`'s guard.
- `pollLightBurn`: `const res = await API.lightburnStatus().catch(()=>null);
  const running = res && res.running;` — never destructure null; never throw on
  the pre-ready first tick.
- `copyOrder`: await `navigator.clipboard.writeText` when available; fall back to
  a hidden-textarea `document.execCommand('copy')`; only toast success on a real
  success, else an error toast.
- Amazon link: when there is no Amazon URL, the control is a true no-op
  (`pointer-events:none` + dimmed), never calling `openAmazon('#')`. Surface
  `open_amazon`/`open_label`/`print_label` failures as error toasts (inspect the
  returned `{ok}`).

## C. Live feel — loading & optimistic UI

### C1. Skeleton loaders
- Dashboard: before the `listOrders` await, render shimmer skeleton rows in
  `#orderList` and set `#dashSub` to "Loading…"; replace on resolve.
- Order view: `openOrder` switches to the order view immediately with a skeleton
  layout (placeholder product card + detail rows), then populates when `getOrder`
  resolves — so the click feels instant instead of freezing the dashboard.

### C2. Wire the existing button spinners
`.cta.is-loading` and `.sbtn.is-loading` styles already exist but are unused. Add
`is-loading` to: the Engrave action-bar button + the specific side button during
engrave; the Ship/confirm button during the ship chain; the Refresh button during
reload. Remove in `finally`.

### C3. Debounce search → client-side filter
Order-number search is a substring match on already-loaded cards. Filter the
in-memory `ORDERS` client-side on input (instant, no network), and debounce any
actual reload by ~250ms. Eliminates per-keystroke network calls and out-of-order
flicker.

### C4. Product-photo cache
Cache the returned `data_uri` per `(order_number, product_index)` so switching
product tabs (or returning to a product) shows the photo instantly instead of
re-downloading. Show a subtle spinner/shimmer on the visual only on first load
when `has_image`.

## D. Honest states & polish

### D1. Toast variants
`toast(msg, kind)` gets three visual variants with correct icon + color:
`success` (green check), `error` (amber/red warning triangle), `info` (neutral).
All current error call-sites switch from the misleading checkmark to `error`.

### D2. Refresh feedback
Refresh spins its icon, disables during reload, and toasts "Orders updated" on
completion. A subtle "Updated HH:MM" (or relative) is shown near `#dashSub`.

### D3. Actionable error banner + differentiated empty states
- The API-error banner gets a **Retry** button (re-runs `loadDashboard`) and a
  dismiss control.
- When `error` is set, `#orderList` shows a distinct "Couldn't reach Flanacom —
  Retry" state, NOT the "no orders match your search" copy.
- Empty states differentiate: all-caught-up (celebratory), filtered-empty,
  search-empty.

### D4. Modal dismissal
The ship-confirm modal closes on Escape and on backdrop click (not only the
Cancel button); focus moves into the modal on open.

### D5. Micro-polish
A brief pop animation when a side flips to `done`; the label "Open" control
becomes a real `<button>`; `productSVG` gains MiniFlask/Lighter fallbacks.

## Preserve (audit-confirmed correct — do NOT change)

- `list_orders` always re-GETs (never served from cache).
- Every write path sets `_fetched_at=None` (cache invalidated) so the next read
  is fresh; `confirmShip` reloads the dashboard before hopping on.
- `mark_engraved` runs strictly AFTER a successful LightBurn load — no
  false-positive progress. Keep this ordering.
- All 3 statuses map 1:1 to API strings; `not_done_yet` posts validly; ship is
  gated on full engrave and re-ship is idempotent.
- `loadProductPhoto` already guards against a stale order/product.
- The 11 `API.*` wrappers map 1:1 to bridge methods with correct arity.

## Error handling

Every async UI action: `try { … } catch { toast(error) } finally { busy=false;
clear loading }`. Backend: retries are bounded and logged; non-retryable errors
surface as typed `{ok:false,error}`; nothing reaches the operator as an uncaught
throw or a misleading success.

## Testing

- **Backend (pytest, no network):** retry attempts + backoff (injected sleep);
  retryable vs non-retryable status codes; download expired-link re-GET + retry;
  `product_image` corrupt-file → `{ok:false}`; `engrave_side` OSError → not
  marked + `{ok:false}`; `qty` removed from payload. Existing 141 stay green.
- **Frontend (no unit harness):** `node --check`; manual trace + grep guards for
  each behavior (loading classes applied/cleared, debounce, toast variants,
  stale-token bailouts, modal escape). Live GUI smoke against the 3 real orders.

## Out of scope

- Real-time/websocket order updates (manual Refresh remains the model).
- Editing any order field other than status (API forbids it).
- Reworking the visual theme/branding.
