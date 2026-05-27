# Order-Aware Workflow — design

**Date:** 2026-05-26
**Status:** Approved (with two decisions: always show order view; in-memory completion)
**Driver:** Client's order system will eventually live in Supabase/Airtable. Real
orders frequently contain **multiple items under a single order number**
(e.g., a couple's matching wallets, gift sets) — each with its own SKU and
customization. The current "1 PDF = 1 engrave" model can't represent this.
We need an order-aware UX **today**, with simulated data, so the workflow is
ready when the real backend lands.

## Goals

1. Drop a PDF named by order number → see the **whole order** (customer +
   items) in one place.
2. Operator works through items sequentially. Mistakes prevented: every item
   is anchored to the same customer/order; operator can't mix designs across
   orders accidentally.
3. **Simulation today**: JSON file under the user's home directory. Seeded
   on first run. Future Supabase adapter slots in via the same Protocol —
   no UI/controller changes needed.
4. Defer per-item LightBurn-side settings (engraving text injection, layer
   power tuning per customization). Capture them in data; emit them as
   on-screen guidance for the operator for now.

## Data model

`src/lbb/core/order.py` (new):

```python
@dataclass(frozen=True, slots=True)
class Customer:
    name: str
    email: str = ""


@dataclass(frozen=True, slots=True)
class OrderItem:
    """One line item — references a SKU and carries customer-specific data."""
    item_id: str                          # "A", "B" — unique within order
    sku: Sku                              # which product profile to use
    customization: dict[str, str]         # {"engraving_text": "John 2026"}
    pdf_path: str                         # design file (absolute or in cwd)
    notes: str = ""


@dataclass(frozen=True, slots=True)
class Order:
    order_number: str                     # "305-6737580-7658721"
    customer: Customer
    items: tuple[OrderItem, ...]
    placed_at: datetime | None = None     # for display only
    notes: str = ""
```

`src/lbb/ports/orders.py` (new):

```python
class OrderRepository(Protocol):
    def get(self, order_number: str) -> Order | None: ...
    def list_all(self) -> list[Order]: ...
```

`src/lbb/adapters/json_orders.py` (new) — `JsonOrderRepository`:
- Reads from `~/.flanacom-tool/orders.json` (configurable for tests).
- If file missing on first instantiation, seeds it from a bundled
  `orders.seed.json` (committed in `src/lbb/ui/assets/` or similar).
- Malformed JSON / missing fields → logged to stderr, `get` returns `None`
  for every order so the existing SKU-only flow still works.

## Flow

```
DropZone.pdf_dropped
  → MainWindow._on_pdf_chosen
    │
    ├── filename stem == order_number  AND  repo.get(order_number) is not None
    │   │
    │   ├── ALWAYS show the new Order view (per user decision)
    │   │   • Operator clicks Engrave on an item
    │   │       → existing _continue_with_profile(item.pdf_path, profile)
    │   │       → preview screen → Open in LightBurn
    │   │       → on successful dispatch, mark item ✓ in memory
    │   │       → on dialog close, navigate BACK to Order view
    │   │   • Operator clicks "Back to home" to leave the order
    │   │
    │   └── (no other routing needed)
    │
    └── No matching order
        → fall back to today's flow (extract_sku / picker / preview)
```

### Single-item orders

Per user decision: still show the Order view (even with 1 item). Consistent
UX; operator always sees customer context before any engrave.

### Completion state

In-memory only — `MainWindow._completed_items: set[tuple[str, str]]` keyed by
`(order_number, item_id)`. Closing the app clears state. Mark on successful
LightBurn dispatch. Re-engraving a completed item is permitted (just shows ✓).

## Order view (new)

`src/lbb/ui/views/order_view.py`:

```
┌────────────────────────────────────────────────────────┐
│  [FLANACOM] Engraver                          [← Back] │
├────────────────────────────────────────────────────────┤
│  ORDER 305-6737580-7658721                             │
│  Jane & John Doe  •  placed 2026-05-15                 │
│                                                        │
│  [██████░░░░░░░░░░░░░░]   1 / 3 engraved              │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │ ✓ Item A   LB-WALLET-LEATHER-S                   │  │
│  │   "John 2026"                       Engraved     │  │
│  ├──────────────────────────────────────────────────┤  │
│  │ ◯ Item B   LB-WALLET-LEATHER-S         [Engrave] │  │
│  │   "Jane 2026"                                    │  │
│  ├──────────────────────────────────────────────────┤  │
│  │ ◯ Item C   LB-WALLET-LEATHER-M         [Engrave] │  │
│  │   "Gift card 2026"                               │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

Widget composition:
- `QLabel` order header (order number, big monospace)
- `QLabel` customer line (name • placed date)
- `QProgressBar` showing engraved-count / total
- `QListWidget` or vertically-stacked `QFrame`s per item:
  - Status glyph (✓ / ◯) + item_id + SKU code + customization text
  - "Engrave" button on right (greyed if SKU unknown to repo)
- `QPushButton` "Back" (ghost) returns to home

Signals:
- `item_chosen = Signal(OrderItem)` — fires when Engrave clicked
- `back_requested = Signal()`
- Public method `mark_completed(item_id: str) -> None` — toggles glyph + progress

## Seed data

Committed at `src/lbb/ui/assets/orders.seed.json`:

```json
{
  "orders": {
    "305-6737580-7658721": {
      "customer": {"name": "Jane & John Doe"},
      "placed_at": "2026-05-15T14:30:00Z",
      "items": [
        {"item_id": "A", "sku": "LB-WALLET-LEATHER-S",
         "customization": {"engraving_text": "John 2026"},
         "pdf_path": "305-6737580-7658721.pdf"},
        {"item_id": "B", "sku": "LB-WALLET-LEATHER-S",
         "customization": {"engraving_text": "Jane 2026"},
         "pdf_path": "305-6737580-7658721.pdf"},
        {"item_id": "C", "sku": "LB-WALLET-LEATHER-M",
         "customization": {"engraving_text": "Gift card 2026"},
         "pdf_path": "305-6737580-7658721.pdf"}
      ]
    },
    "304-4865183-6105121": {
      "customer": {"name": "Maria Smith"},
      "placed_at": "2026-05-16T09:15:00Z",
      "items": [
        {"item_id": "A", "sku": "LB-WALLET-LEATHER-T",
         "customization": {"engraving_text": "III.III.MMXX"},
         "pdf_path": "304-4865183-6105121.pdf"}
      ]
    }
  }
}
```

Notes on the seed:
- All items in order 305 reference the same PDF — we don't have per-item
  PDFs from the client yet. Different customization text per item shows the
  multi-item UX.
- `LB-WALLET-LEATHER-M` is referenced but not in the SKU DB yet — the order
  view will show "Engrave" disabled with a tooltip "SKU not registered;
  add via Admin." Demonstrates graceful degradation.
- 304 has a single item — but per user decision the order view still shows.

## Routing changes

`MainWindow`:
- New view `self.order = OrderView()` added to `QStackedWidget`.
- `_on_pdf_chosen(path)` checks `deps.orders.get(path.stem)` first:
  - Hit → populate order view, switch to it.
  - Miss → existing extract_sku / picker / preview flow.
- New signal handler `_on_item_chosen(OrderItem)`:
  - Looks up the SKU profile, builds the per-item pending state, navigates
    to the preview screen (existing code path).
  - On successful `_on_send`, also marks the item completed and routes
    back to the order view rather than home.
- `_show_home()` clears `_current_order` state.

`__main__.py` / `container.py`:
- New `AppPaths.orders_seed_path` (package resource) + `AppPaths.orders_json_path`
  (user home).
- `build_pipeline_deps` adds `orders=JsonOrderRepository(paths.orders_json_path,
  seed_path=paths.orders_seed_path)` and exposes it on `PipelineDeps`.

## Tests

1. **Adapter unit tests** (`tests/unit/adapters/test_json_orders.py` new):
   - `test_seeds_on_first_run` — empty file → seed copied.
   - `test_get_returns_order_when_present`.
   - `test_get_returns_none_when_absent`.
   - `test_malformed_json_falls_back_to_empty` — corrupted file → no crash,
     `get` returns None.
   - `test_list_all_returns_orders_sorted`.

2. **Core dataclass tests** (`tests/unit/core/test_order.py` new):
   - `OrderItem` / `Order` instantiation + equality.

3. **Order view tests** (`tests/ui/test_order_view.py` new):
   - `test_renders_customer_and_items`.
   - `test_engrave_button_emits_item_chosen`.
   - `test_mark_completed_updates_glyph_and_progress`.
   - `test_engrave_disabled_when_sku_not_in_repo` (SKU `LB-WALLET-LEATHER-M`
     isn't yet seeded → button disabled, tooltip explains).
   - `test_back_button_emits_back_requested`.

4. **Main window integration** (`tests/ui/test_main_window.py` additions):
   - `test_multi_item_order_drop_routes_to_order_view`.
   - `test_single_item_order_still_routes_to_order_view` (per user decision).
   - `test_no_matching_order_falls_back_to_picker_or_skuflow` —
     unchanged existing behaviour.
   - `test_engraving_an_item_returns_to_order_view_not_home`.
   - `test_back_from_order_view_returns_to_home`.

## Edge cases

| Situation | Behaviour |
|---|---|
| Filename matches an order in JSON | New order view |
| Filename doesn't match any order | Existing extract_sku / picker fallback (unchanged) |
| Item's SKU isn't in the profiles DB | Engrave button disabled; tooltip "Unknown SKU — add via Admin" |
| User reopens app | Completion state resets (in-memory only, per user decision) |
| Malformed orders.json | Logged to stderr; treated as empty; existing flows still work |
| Order has zero items | Show order view with "No items in this order — contact support" empty state |
| Operator re-engraves a completed item | Allowed — Engrave button remains active even when ✓; useful for reprints |

## Non-goals

- Live Supabase / Airtable connection (port is ready; future task).
- Injecting customization text into the .lbrn2 / LightBurn workspace
  automatically (we just display it; operator types it in LightBurn).
- Persisting completion across sessions (per user decision).
- Bulk-engrave-all-items button (each item is dispatched individually).
- Order CRUD UI (orders are read-only in this scope — they come from the
  upstream order system).

## Estimated scope

- 2 new files in `core/`, 1 in `ports/`, 1 in `adapters/`, 1 in `ui/views/`
- ~15 modified lines in MainWindow + __main__ + container
- 1 seed JSON file
- ~12 new tests
- **~280 LOC across ~9 files**
