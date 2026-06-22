# Live Engraving API Integration — Design

**Date:** 2026-06-22
**Status:** Approved (design), pending implementation
**Supersedes:** the seeded `JsonFulfillmentRepository` read path and the 5-value
`OrderStatus` model from `2026-06-04-fulfillment-studio-web-design.md`.

## Problem

Fulfillment Studio currently reads orders from bundled seed JSON and tracks a
rich 5-state status locally. Hauke (Flanacom GmbH, the client) has now provided a
**live Supabase Edge Function** that is the real source of truth for engraving
orders. The tool must read all orders + their files from this API and write back
processing status, so it becomes the operator's day-to-day workshop tool for the
Amazon engraving business. It must be accurate, reliable, and have no gaps.

## The backend contract (authoritative)

Base URL: `https://puscgcazmnqxazietgvy.supabase.co/functions/v1/engraving-api`
Auth: header `x-api-key: <SECRET>` on **every** request. Missing/wrong → `401`.
The secret must **never** be shipped in a frontend/client.

### Read — `GET`
Optional filter: `?status=not_done_yet` or `?status=not_done_yet,revision`.
Response: `{ "orders": [ ... ] }`. A single order:

| Field | Meaning |
|---|---|
| `id` | uuid — **required** to write status back |
| `order_number` | Amazon order number |
| `link_to_order` | Seller Central link |
| `order_date` | `YYYY-MM-DD` |
| `amount` | number of items in the order |
| `status` | current processing status (3 values, below) |
| `comment` | free-text instruction **from** Flanacom (e.g. "With Gift Box each") |
| `shipping_label_path` | storage key for the shipping label PDF |
| `product_picture_path`, `link_to_graphic` | optional |
| `created_at`, `updated_at` | ISO-8601 |
| `products[]` | items to engrave (below) |
| `signed_urls` | map: storage-key → temporary download URL |

Each `product`: `type` (`keychain｜necklace｜bracelet｜flask｜mini_flask｜lighter`),
`color_band_chain`, `color_coin_plate`, `multiple_coins`, `special_length`,
`length`, `image` (product-picture key), and `coins[]` where each coin is
`{ "front": <key>, "back": <key> }` — the engraving artwork PDFs.

**Files:** every file path (coin front/back, product image, shipping label) is a
**key** into that order's `signed_urls` map; the value is a direct download URL
valid for **1 hour**. Fetch fresh at processing time, not in advance.

### Write — `POST`
Body `{ "order_id": <uuid>, "status": <value> }`. Sets **only** status.
Response `{ "ok": true, "order": { ... } }`. Invalid status → `400`, unknown
`order_id` → `404`.

Allowed status values (the canonical model):

| Value | Meaning |
|---|---|
| `not_done_yet` | open / not yet engraved |
| `graviert_verschickt` | done — engraved **and** shipped |
| `revision` | question / rework needed |

## Decisions

- **Align to the API.** The 3 API statuses are the only canonical statuses. The
  tool displays exactly these; it never invents alternatives. Per-side engraving
  progress is a **local operator aid** (drives an `n/m` indicator and gates
  shipping) — not a status. The local `hold` concept is removed (no API analog).
- **Refresh:** manual Refresh re-GETs all orders; signed URLs are always fetched
  fresh at the moment a file is opened.
- **Live only:** the seeded JSON runtime path is removed. Tests use an in-memory
  fake gateway, not seed data.

## Architecture

Hexagonal layout is unchanged. We swap one adapter and remap the domain.

```
core/fulfillment.py     domain types + pure logic (3-status enum, mapping helpers)
ports/engraving.py      EngravingGateway, HttpTransport (Protocols)        [new]
ports/fulfillment.py    FulfillmentStateStore (local progress)             [trimmed]
adapters/engraving_api.py   EngravingApiClient over HttpTransport          [new]
adapters/http_urllib.py     UrllibTransport (stdlib, no new dependency)    [new]
adapters/sqlite_state.py    thread-safe local progress store               [bugfix]
adapters/config.py          load api_base_url + api_key (env → file)       [new]
app/fulfillment_service.py  the brain — download→LightBurn, status writes  [rewired]
web/bridge.py               window.pywebview.api                           [rewired]
web/assets/{app.js,app.css} status keys, revision action, file open        [rewired]
app/container.py, __main__.py   wire live gateway from config              [rewired]
```

### Ports

```python
class HttpTransport(Protocol):
    def request(self, method: str, url: str, *, headers: dict[str, str],
                body: bytes | None = None) -> tuple[int, bytes]: ...

class EngravingGateway(Protocol):
    def list_orders(self) -> list[FulfillmentOrder]: ...
    def get(self, order_number: str) -> FulfillmentOrder | None: ...
    def download_file(self, order_id: str, file_key: str, dest_dir: Path) -> Path: ...
    def set_status(self, order_id: str, status: OrderStatus) -> None: ...
```

`EngravingApiClient`:
- GET parses orders into domain types; caches parsed orders + each order's
  `signed_urls` map with a fetch timestamp.
- `download_file` ensures a non-expired URL (re-GETs if older than ~50 min or the
  key is absent), then streams the file to `dest_dir`. This is the single place
  "fetch fresh at processing time" is enforced.
- `set_status` POSTs `{order_id, status}`; raises a typed error on 400/404/401.
- All HTTP goes through the injected `HttpTransport`, so every behavior is
  unit-tested against a fake transport with **no network**.

`UrllibTransport` implements `HttpTransport` with stdlib `urllib.request`
(timeouts, header injection). Chosen over `httpx`/`requests` to keep the build
dependency-free and the PyInstaller bundle simple.

### Domain (`core/fulfillment.py`, stays pure)

- `OrderStatus(StrEnum)`: `NOT_DONE="not_done_yet"`, `DONE="graviert_verschickt"`,
  `REVISION="revision"`.
- `FulfillmentOrder` gains `order_id: str`, `amount: int`, `instruction: str`
  (the API `comment`, read-only). `placed_at` parsed from `order_date`.
- A `Side` carries `name` ("Front"/"Back", or "Coin n Front" when
  `multiple_coins`) and `file_key` (the signed-URL key). **Side identity for
  local progress is the `file_key`** — stable and unique even if products are
  reordered between GETs.
- `all_sides(order)` → set of file keys. Progress = engraved keys ∩ all keys.
- Product `type` is normalized to title case for the existing bucket/SVG code.

### Local state (`adapters/sqlite_state.py`)

Tracks engraved **file keys** per order (replaces item_id/side_name keying) and
nothing else (overrides/comments removed — status now lives in the API).
**Threading fix:** open with `check_same_thread=False` and guard writes with a
`threading.Lock`, because pywebview dispatches bridge calls on a worker thread
while the connection is created on the main thread (root cause of the observed
`sqlite3.ProgrammingError`).

### Service (`app/fulfillment_service.py`)

- `engrave_side(order_number, file_key)`: `gateway.download_file(...)` →
  `lightburn.load_file(local_pdf)` → mark key engraved. Re-openable.
- `ship_order`: all sides engraved → `gateway.set_status(order_id, DONE)`.
  Gift-box confirm modal preserved.
- `flag_revision(order_number)`: `set_status(order_id, REVISION)` — the
  operator's outbound channel, replacing the old local "comment" feature.
- `refresh()`: forces a fresh GET.
- Status shown = API status; local `n/m` progress shown alongside.
- Label open/print uses `download_file` on the shipping-label key.

### Front-end (`web/assets/`)

- Status keys become `not_done_yet｜graviert_verschickt｜revision`; labels/CSS
  updated; `hold` removed from the status selector; a "Flag for revision" action
  added. The inbound `instruction`/`comment` is shown read-only.
- Per-side rendering keyed by `file_key`. Manual Refresh button.
- Friendly states for: LightBurn not installed, API key missing, network error,
  expired link auto-retried.

## Error handling

- `401` → "API key rejected — check configuration" (and key-missing state).
- `400` → "Invalid status" (should never happen from UI; guarded).
- `404` on write → order no longer exists; prompt refresh.
- Network/timeout → toast + keep last good data; Refresh to retry.
- Expired signed URL → transparent re-GET inside `download_file`.
- LightBurn missing → existing `LightBurnRejected` message.

## Testing

TDD throughout, no network in unit tests:
1. Domain remap + mapping helpers (status, sides-from-coins, type normalization).
2. `EngravingApiClient` vs fake transport: GET parse, `?status=` filter, signed-URL
   resolution, stale re-GET, download-to-temp, 401/400/404, expired-link re-fetch.
3. `UrllibTransport` request shaping (headers/method/body) — light, hermetic.
4. Service flows: engrave→download→LightBurn, ship→DONE, flag→REVISION, refresh.
5. `SqliteStateStore` cross-thread safety (call from a second thread).
6. `config.py` precedence (env > file > absent).
7. `import-linter` contracts (core purity, web isolation) still pass.
8. Manual live smoke test against the real API; fresh PyInstaller build named
   "Fulfillment Studio".

## Out of scope

- Auto-polling/background refresh (manual + fresh-on-open is sufficient).
- Editing any order field other than status (API forbids it).
- Creating/deleting orders.
- Persisting operator free-text back to Flanacom (API accepts only status;
  `revision` is the channel).

## Risks

- **Secret distribution:** the key must reach the operator's machine without
  entering the repo. Handled via env var / git-ignored `~/.flanacom-tool/config.json`
  + `config.example.json` template; documented for the client.
- **Order identity:** products have no id; local progress keys on `file_key`
  (stable) to avoid drift if products are reordered between GETs.
