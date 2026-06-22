# Fulfillment Studio (web UI) — design

**Date:** 2026-06-04
**Status:** Approved (pending written-spec review)
**Driver:** The client (a German Amazon laser-engraving business — bracelets,
necklaces, keychains, flasks) provided a high-fidelity HTML prototype,
`engraving-fulfillment-tool.html`, of the workstation they actually want: an
**order-fulfillment dashboard**, not a single-PDF tool. Orders come from
Airtable/Supabase (seeded for now — no access yet). Each order has products;
each product has Front/Back **sides**; **each side is one LightBurn job**.
The operator works a queue, opens each side's design in LightBurn, marks
sides engraved, and ships — with a gift-box reminder. The proven engine
(direct-open to LightBurn) stays; the UI and domain grow up around it.

## Relationship to prior specs

This design **builds on** and in two places **supersedes** earlier specs:

- **Reuses:** the direct-open pipeline (`2026-05-19-direct-open-pivot`), the
  `Order` domain + `OrderRepository` port + directory-seeded
  `JsonOrderRepository` (`2026-05-26-order-aware-workflow`,
  `2026-05-26-search-first-home`), `LightBurnShellAdapter`, `AppPaths`,
  PyInstaller packaging, and the Flanacom light-theme brand
  (`2026-05-19-flanacom-rebrand`).
- **Supersedes — UI technology:** the PySide6 `ui/` layer (HomeView,
  OrderView, drop zone, dialogs) is **retired** in favour of a web UI rendered
  in a desktop window. We do not maintain two UIs.
- **Supersedes — completion persistence:** the order-aware spec chose
  *in-memory completion that resets on app close*. A fulfillment workstation
  must remember progress (a shipped order stays shipped after a restart), so
  completion/status/comments now **persist** in a local SQLite state store.

## Goals

1. Render the client's prototype faithfully as a real desktop app (its exact
   HTML/CSS/JS, wired to a live Python backend).
2. Dashboard of orders from the data source (seeded today), grouped by product
   type (Bracelet → Necklace → Keychain → Flask), oldest-first within type,
   with search + To-do/Shipped filters.
3. Per-side engraving: click → resolve the side's PDF → open it in LightBurn
   (direct-open) → mark the side engraved. Re-clicking a done side re-opens it.
4. Order lifecycle: status pipeline (received / engraving / engraved / shipped
   / on-hold), gift-box ship confirmation, operator comments, shipping-label
   open + print.
5. Progress persists locally and is shaped to **sync upward** to Airtable/
   Supabase once write access exists — no UI/controller changes needed then.
6. Single Windows `.exe` the client can run with no extra runtime install.

## Non-goals (v1)

- Live Airtable/Supabase **read or write** (seeded `JsonOrderRepository`
  today; the real adapters slot behind the same ports later).
- Authentication / multiple operator accounts (operator is a fixed label).
- Multi-station shared database.
- Reviving `.lbrn2` generation / vector parsing (direct-open handles fidelity;
  `template_builder` + `extract_paths` stay dormant).
- Injecting customization text into LightBurn automatically (displayed as
  operator guidance, as before).

## Architecture

Evolve `lightburn-tool` in place. Hexagonal layers stay; the UI technology and
domain extend:

```
src/lbb/
├── core/        order.py extended: Product, Side, OrderStatus, Label, Recipient
│                (palette/preflight/template_builder stay; dormant ones unchanged)
├── ports/       orders.py (read, extended shape) · state.py NEW
│                (FulfillmentStateStore: read/write progress) · lightburn.py (reuse)
├── adapters/    json_orders.py (seeded read, extended schema)
│                · sqlite_state.py NEW (progress; mirrors SqliteProfileRepository)
│                · lightburn_shell.py (reuse as-is)
├── app/         pipeline.py (reuse run_pipeline) · container.py (rewire deps)
│                · fulfillment_service.py NEW — the testable brain
└── web/         NEW (replaces ui/): static assets + pywebview shell + bridge
    ├── assets/  index.html, app.css, app.js  (ported from the prototype)
    ├── shell.py        — creates the pywebview window, injects the bridge
    └── bridge.py       — JsApiBridge: thin JSON marshaller → FulfillmentService
```

**`FulfillmentService`** (app layer) is the brain and the test seam: it owns
list/get/engrave/status/ship/comment/label logic, depends only on ports
(`OrderRepository`, `FulfillmentStateStore`, `LightBurnPort`) + the existing
pipeline, and knows nothing about pywebview or HTTP. **`JsApiBridge`** (web
layer) is a thin adapter that converts JS arguments to/from JSON and delegates
to the service. **pywebview** is only the window.

**Why pywebview's JS↔Python bridge, not a local HTTP server:** no socket bind
→ **no Windows Firewall prompt** on the client's first run, no CORS, fewer
moving parts, cleaner bundle. The service stays transport-agnostic, so a local
HTTP server could be added later for browser-based dev without touching it.

Import-linter: the existing `ui/`-may-not-import-`adapters/` contract is
repointed to `web/`. `core/` still cannot import `adapters/`, `app/`, or
`web/`. `web/bridge.py` may import `app/` only.

## Domain model (`core/order.py`)

The single-`pdf_path` `OrderItem` becomes a `Product` with metadata and
**sides**. Read-from-source types stay frozen; mutable progress lives in the
state store, never on these dataclasses.

```python
class OrderStatus(StrEnum):            # derived OR explicitly set (hold/shipped)
    RECEIVED = "received"
    ENGRAVING = "engraving"
    ENGRAVED = "engraved"
    SHIPPED = "shipped"
    HOLD = "hold"

@dataclass(frozen=True, slots=True)
class Side:
    name: str                          # "Front" | "Back"
    pdf_path: str                      # one LightBurn job (resolved by adapter)

@dataclass(frozen=True, slots=True)
class Recipient:
    name: str
    address: str = ""                  # "52525 Heinsberg, DE"

@dataclass(frozen=True, slots=True)
class Label:
    carrier: str                       # "DHL Kleinpaket · 1 kg"
    pdf_path: str = ""                 # shipping-label PDF (resolved)

@dataclass(frozen=True, slots=True)
class Product:                         # evolves OrderItem
    item_id: str                       # "A", "B" — unique within order
    name: str                          # "Heart necklace"
    product_type: str                  # "Bracelet"|"Necklace"|"Keychain"|"Flask"
    color: str                         # "Gold"|"Silver"
    qty: int
    sku: Sku
    sides: tuple[Side, ...]
    instructions_url: str = ""         # Google Drive link to artwork & notes
    customization: dict[str, str] = field(default_factory=dict)
    notes: str = ""

@dataclass(frozen=True, slots=True)
class Order:
    order_number: str
    recipient: Recipient
    products: tuple[Product, ...]      # was `items`
    channel: str = "Amazon · DE"
    amazon_url: str = ""
    gift_box: bool = False
    label: Label | None = None
    placed_at: datetime | None = None
    notes: str = ""
```

## Read-source vs local-state split

Two stores, merged into a view model the JS already expects:

- **`OrderRepository`** (read) — seeded `JsonOrderRepository` today;
  `AirtableOrderRepository`/`SupabaseOrderRepository` later, same port.
- **`FulfillmentStateStore`** (read/write, new) — SQLite, mirrors
  `SqliteProfileRepository`. Records:
  - per-side engraved: `(order_number, item_id, side_name) → engraved_at`
  - per-order override status (`hold`, `shipped`) + `shipped_at`
  - per-order operator comments (append-only log)

  Port (`ports/state.py`):
  ```python
  class FulfillmentStateStore(Protocol):
      def engraved_sides(self, order_number: str) -> set[tuple[str, str]]: ...
      def mark_side(self, order_number, item_id, side_name, engraved: bool) -> None: ...
      def get_override(self, order_number: str) -> OrderStatus | None: ...
      def set_override(self, order_number: str, status: OrderStatus | None) -> None: ...
      def comments(self, order_number: str) -> list[Comment]: ...
      def add_comment(self, order_number: str, text: str, author: str) -> None: ...
  ```

This split is the whole point: upstream orders are read-only until write access
exists; local progress is precisely what a future sync job pushes to Airtable.

## Status derivation (ported from the prototype)

`FulfillmentService` computes status the same way the prototype's `statusOf()`
does, with the SQLite override layered on:

```
override == shipped               → shipped
override == hold                  → hold
all sides engraved                → engraved
some (but not all) sides engraved → engraving
else                              → received
```

Queue ordering (`startEngraving`, dashboard sort) also ports verbatim: group
by `product_type` rank `[Bracelet, Necklace, Keychain, Flask]`, then oldest
`placed_at` first; only non-shipped, non-hold orders are in the engraving
queue.

## Data flow — the engrave action

```
JS: engrave(item_id, side)            (prototype button)
  → window.pywebview.api.engrave_side(order_number, item_id, side)
    → JsApiBridge → FulfillmentService.engrave_side(...)
      → resolve Side.pdf_path (adapter already absolutised it)
      → guard: file exists & is a .pdf  → else return {ok:false, error}
      → (optional) lightburn.close_running()  for a clean workspace
      → run_pipeline(Job(source_pdf=pdf), deps)   # direct-open: load_file(pdf)
      → on ok: state.mark_side(order, item_id, side, True)
      → recompute + return {ok:true, status, progress}
  → JS updates the side chip / stepper / action bar (existing optimistic UI)
```

Re-engrave (clicking a done side) repeats the same call; the side stays
engraved. Shipping is locked by the service until every side is engraved
(mirrors the prototype's `allEng` gate).

## JS API surface (`JsApiBridge`)

```
list_orders(filter, query)  → [OrderCard]          # dashboard rows + grouping
get_order(order_number)     → OrderDetail            # full order view model
engrave_side(order_number, item_id, side) → {ok, error?, status, progress}
set_status(order_number, status)          → {ok, error?, status}
ship_order(order_number)                  → {ok, error?}   # gift-box reminder is UI-side
add_comment(order_number, text)           → {ok}
open_label(order_number)                  → {ok, error?}   # opens label PDF in OS viewer
print_label(order_number)                 → {ok, error?}   # OS print verb
open_instructions(url) / open_amazon(url) → {ok}           # OS default browser
lightburn_status()                        → {running: bool}  # live status pill
```

All return JSON-serialisable dicts. The front-end keeps its optimistic toasts/
spinners, now reconciled against real outcomes (e.g. a failed engrave reverts
the chip and shows a red toast).

## Error handling

| Situation | Behaviour |
|---|---|
| LightBurn not installed / launch fails (`LightBurnRejected`) | `{ok:false}` → red toast "Cannot launch LightBurn — is it installed?"; side stays un-engraved |
| Side PDF missing / blank path | `{ok:false}` → toast "Design file not found for this side"; no dispatch |
| Ship requested before all sides engraved | Blocked by service → toast "Engrave all sides first" (matches prototype) |
| Label PDF missing | `open/print_label` → `{ok:false}` toast |
| Malformed `orders.json` | Logged to stderr; treated as empty; dashboard shows empty state |
| Print verb unsupported on platform | Graceful `{ok:false}` toast; Open still works |

A status pill polls `lightburn_status()` on an interval (JS `setInterval` →
bridge), tinted running/not-running.

## Seed data (extended schema, jewelry orders)

`src/lbb/web/assets/seed-orders/` (bundled via PyInstaller `datas`; copied to
`~/.flanacom-tool/orders/` on first run, per existing first-run policy):

```
seed-orders/
├── orders.json            # new schema: products[].sides[], gift_box, label, recipient
├── <design PDFs>          # one per side; reuse existing synthetic vector PDFs
└── labels/<order>.pdf     # synthetic DHL-style label PDFs
```

`orders.json` is reshaped from the prototype's `ORDERS` array (German
recipients, DHL Kleinpaket labels, gift-box flags, Front/Back sides, mixed
Gold/Silver). `scripts/generate_fixtures.py` gains a `make_seed_orders()` that
emits the per-side design PDFs and label PDFs deterministically (small, ~1 KB,
committed). Sides reference distinct PDFs so re-engrave/per-side is real.

## Testing

Mirror existing discipline; the test seam is `FulfillmentService`, exercised
without a browser:

- `tests/unit/core/test_order.py` — extend for `Product`/`Side`/`OrderStatus`,
  status derivation, queue sort.
- `tests/unit/adapters/test_json_orders.py` — new schema parse, per-side PDF
  resolution, malformed-file fallback.
- `tests/unit/adapters/test_sqlite_state.py` — new: mark/unmark side, override
  set/clear, comments append, FK + reopen persistence.
- `tests/integration/test_fulfillment.py` — new, the headline test: seeded
  JSON repo + temp SQLite + `LightBurnFake`; full flow — list → open order →
  engrave Front → engrave Back → status flips engraved → ship → next in queue;
  asserts `LightBurnFake` received each side's PDF and state persisted.
- `tests/web/test_bridge.py` — thin: bridge marshals args and delegates
  (service mocked); JSON-serialisable returns.
- Dormant `template_builder`/golden tests unchanged. Retired Qt `ui/` tests
  are removed with their views.

No PySide6/Qt test extra needed once `ui/` is gone (smaller dev install).

## Packaging & sharing

- Add `pywebview` to deps; drop `PySide6` from the runtime extra (kept only if
  any dormant tooling needs it — verify and remove otherwise).
- `packaging/lbb.spec`: bundle `web/assets/**` and `seed-orders/**` via
  `datas` (same pattern as the current QSS/seed bundling); collect pywebview.
- Output stays a single `dist\…\*.exe` folder → zip → hand to client.
- pywebview uses **Edge WebView2**, present on Windows 11 (the client's OS) —
  no extra runtime install. (HANDOFF gets a one-line note + the WebView2
  Evergreen bootstrapper link as a fallback for older Windows.)
- GitHub Actions Windows build job unchanged in shape.

## Phasing (the implementation plan will detail tasks/tests)

1. **Domain + state** — extend `order.py`; `FulfillmentStateStore` port +
   `SqliteStateStore` adapter; reshape seed `orders.json` + fixtures. Tests.
2. **Service (read + engrave)** — `FulfillmentService` list/get/status/queue +
   `engrave_side` via `run_pipeline`. Headline integration test.
3. **Web UI wiring** — port prototype HTML/CSS/JS into `web/assets/`; replace
   its in-memory `ORDERS` + `setTimeout` fakes with `pywebview.api` calls;
   `JsApiBridge`; live status pill.
4. **Lifecycle features** — ship + gift-box modal, status dropdown + hold,
   comments panel, label open/print.
5. **Shell + packaging** — `web/shell.py` pywebview window; rewire
   `container.py`/`__main__.py`; update `lbb.spec`; retire `ui/`; Windows
   smoke test; HANDOFF + CLAUDE.md updates.

## Edge cases

| Situation | Behaviour |
|---|---|
| Order with one product, one side | Renders normally; ships when that side is done |
| Re-open app after shipping some orders | Shipped/engraved state restored from SQLite |
| Operator re-engraves a finished side | Allowed; re-opens in LightBurn; stays ✓ |
| Product `product_type` not in rank list | Sorts last ("Other" bucket), still engravable |
| `~/.flanacom-tool/orders/` exists from prior version | Not re-seeded; operator's data wins |
| Status set to `shipped` via dropdown before all engraved | Blocked; toast "Engrave all sides first" |
| Status set to `hold` | Override stored; order leaves the active queue |
| WebView2 absent (older Windows) | Window fails to open; HANDOFF documents the Evergreen bootstrapper |

## Scope estimate

| Area | Δ |
|---|---|
| `core/order.py` | ~+70 (Product/Side/Status/Label/Recipient + derivation helpers) |
| `ports/state.py` | new ~25 |
| `adapters/sqlite_state.py` | new ~120 |
| `adapters/json_orders.py` | ~+60 (new schema, per-side resolution) |
| `app/fulfillment_service.py` | new ~180 |
| `web/bridge.py` | new ~90 |
| `web/shell.py` | new ~40 |
| `web/assets/` (html/css/js) | ~700 ported + ~150 rewired from prototype |
| `app/container.py` + `__main__.py` | ~+30 / ~−15 |
| `scripts/generate_fixtures.py` | ~+60 (per-side + label PDFs) |
| seed `orders.json` + PDFs | reshaped + new files |
| `packaging/lbb.spec`, deps | ~+15 |
| Retire `ui/` + Qt tests | ~−1500 (removed) |
| New/updated tests | ~+150 |

Net: a focused, single-product build that **reuses the engine and infra**,
swaps Qt for the client's web design, and persists fulfillment progress.
