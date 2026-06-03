# Fulfillment Studio (web UI) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the client's HTML order-fulfillment prototype into a real desktop app — a pywebview window over the existing direct-open LightBurn engine, with products-that-have-Front/Back-sides, persisted fulfillment state, and seeded order data.

**Architecture:** Build the new stack (fulfillment domain → state store → service → web bridge/shell) in NEW modules alongside the existing PySide6 stack so the suite stays green after every task; then a single cutover task points the entry point at the web shell and deletes the retired Qt `ui/` + legacy order modules. The `FulfillmentService` (app layer) is the testable brain; `JsApiBridge` (web layer) is a thin JSON marshaller; pywebview is only the window.

**Tech Stack:** Python 3.12 · pywebview (Edge WebView2 on Windows) · SQLite (stdlib `sqlite3`) · existing direct-open `run_pipeline` + `LightBurnShellAdapter` · pytest/hypothesis · PyInstaller. Front-end = the prototype's HTML/CSS/JS.

**Reference files:**
- Spec: `docs/superpowers/specs/2026-06-04-fulfillment-studio-web-design.md`
- Prototype UI: `C:\Users\Client\Documents\hauke\flanacom\engraving-fulfillment-tool.html`
- Engine entry: `src/lbb/app/pipeline.py` (`run_pipeline`), `src/lbb/app/job.py` (`Job`)

**Commands:**
- Run one test: `uv run pytest tests/path::name -v`
- Full suite: `uv run pytest`
- Lint + contracts: `uv run ruff check && uv run lint-imports`

---

## File Structure

**New files:**
- `src/lbb/core/fulfillment.py` — frozen domain: `Side`, `Recipient`, `Label`, `Product`, `FulfillmentOrder`, `OrderStatus`, `Comment`; pure helpers `derive_status`, `queue_sort_key`, `type_rank`.
- `src/lbb/ports/fulfillment.py` — `FulfillmentRepository` (read) + `FulfillmentStateStore` (read/write) Protocols.
- `src/lbb/adapters/json_fulfillment.py` — `JsonFulfillmentRepository` (directory-seeded read, new schema, per-side PDF resolution).
- `src/lbb/adapters/sqlite_state.py` — `SqliteStateStore` (engraved sides, status override, comments).
- `src/lbb/adapters/state_migrations.py` — `STATE_SCHEMA_V1`.
- `src/lbb/app/fulfillment_service.py` — `FulfillmentService` (list/get/engrave/status/ship/comment/label) + view-model dicts.
- `src/lbb/web/__init__.py`, `src/lbb/web/bridge.py` (`JsApiBridge`), `src/lbb/web/shell.py` (`run_app`).
- `src/lbb/web/assets/index.html`, `app.css`, `app.js` (ported from prototype), `bridge-client.js` (wires prototype functions to `window.pywebview.api`).
- `src/lbb/web/assets/seed-orders/orders.json` + per-side design PDFs + `labels/*.pdf`.
- Tests: `tests/unit/core/test_fulfillment.py`, `tests/unit/adapters/test_json_fulfillment.py`, `tests/unit/adapters/test_sqlite_state.py`, `tests/integration/test_fulfillment_service.py`, `tests/web/test_bridge.py`.

**Modified at cutover:**
- `src/lbb/__main__.py` (launch web shell), `src/lbb/app/container.py` (wire new deps), `.importlinter` (ui→web), `packaging/lbb.spec` (web assets), `pyproject.toml` (add pywebview; drop Qt runtime extra), `scripts/generate_fixtures.py` (`make_seed_orders`), `HANDOFF.md`, `CLAUDE.md`.

**Deleted at cutover:**
- `src/lbb/ui/` (entire tree), `src/lbb/core/order.py`, `src/lbb/ports/orders.py`, `src/lbb/adapters/json_orders.py`, and their tests (`tests/ui/`, `tests/unit/core/test_order.py`, `tests/unit/adapters/test_json_orders.py`).

---

## Phase 1 — Fulfillment domain (pure core)

### Task 1: Domain types + status derivation + queue sort

**Files:**
- Create: `src/lbb/core/fulfillment.py`
- Test: `tests/unit/core/test_fulfillment.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/core/test_fulfillment.py
from datetime import datetime

from lbb.core.fulfillment import (
    FulfillmentOrder,
    Label,
    OrderStatus,
    Product,
    Recipient,
    Side,
    derive_status,
    queue_sort_key,
    type_rank,
)
from lbb.core.models import Sku


def _order(order_number="306-1", ptype="Necklace", sides=("Front", "Back"),
           placed="2026-01-03T10:00:00Z"):
    return FulfillmentOrder(
        order_number=order_number,
        recipient=Recipient(name="Sabrina W.", address="52525 Heinsberg, DE"),
        products=(
            Product(
                item_id="A", name="Heart necklace", product_type=ptype,
                color="Gold", qty=1, sku=Sku("FL-NECK-HEART-G"),
                sides=tuple(Side(name=s, pdf_path=f"{order_number}-A-{s}.pdf") for s in sides),
            ),
        ),
        placed_at=datetime.fromisoformat(placed.replace("Z", "+00:00")),
        gift_box=True,
        label=Label(carrier="DHL Kleinpaket · 1 kg", pdf_path="labels/306-1.pdf"),
        amazon_url="https://example.com/o/306-1",
    )


def test_derive_status_received_when_nothing_engraved():
    o = _order()
    assert derive_status(o, engraved=set(), override=None) is OrderStatus.RECEIVED


def test_derive_status_engraving_when_partial():
    o = _order()
    assert derive_status(o, engraved={("A", "Front")}, override=None) is OrderStatus.ENGRAVING


def test_derive_status_engraved_when_all_sides_done():
    o = _order()
    eng = {("A", "Front"), ("A", "Back")}
    assert derive_status(o, engraved=eng, override=None) is OrderStatus.ENGRAVED


def test_override_shipped_wins_over_progress():
    o = _order()
    assert derive_status(o, engraved=set(), override=OrderStatus.SHIPPED) is OrderStatus.SHIPPED


def test_override_hold_wins():
    o = _order()
    eng = {("A", "Front"), ("A", "Back")}
    assert derive_status(o, engraved=eng, override=OrderStatus.HOLD) is OrderStatus.HOLD


def test_type_rank_orders_bracelet_first_other_last():
    assert type_rank("Bracelet") < type_rank("Necklace") < type_rank("Flask")
    assert type_rank("Unknown") == 99


def test_queue_sort_key_groups_by_type_then_oldest():
    early = _order("306-9", ptype="Bracelet", placed="2026-01-01T00:00:00Z")
    late = _order("306-8", ptype="Bracelet", placed="2026-01-05T00:00:00Z")
    neck = _order("306-7", ptype="Necklace", placed="2026-01-01T00:00:00Z")
    ordered = sorted([neck, late, early], key=queue_sort_key)
    assert [o.order_number for o in ordered] == ["306-9", "306-8", "306-7"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/core/test_fulfillment.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lbb.core.fulfillment'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/lbb/core/fulfillment.py
"""Domain types for the order-fulfillment workflow.

A customer order contains products; each product has Front/Back sides; each
side is one LightBurn job. These types are frozen and come from the upstream
order source (read-only). Mutable progress (which sides are engraved, status
overrides, comments) lives in the FulfillmentStateStore, never on these types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from lbb.core.models import Sku

_TYPE_ORDER = ("Bracelet", "Necklace", "Keychain", "Flask")


class OrderStatus(StrEnum):
    RECEIVED = "received"
    ENGRAVING = "engraving"
    ENGRAVED = "engraved"
    SHIPPED = "shipped"
    HOLD = "hold"


@dataclass(frozen=True, slots=True)
class Side:
    name: str  # "Front" | "Back"
    pdf_path: str  # one LightBurn job (resolved to absolute by the adapter)


@dataclass(frozen=True, slots=True)
class Recipient:
    name: str
    address: str = ""


@dataclass(frozen=True, slots=True)
class Label:
    carrier: str
    pdf_path: str = ""


@dataclass(frozen=True, slots=True)
class Product:
    item_id: str
    name: str
    product_type: str
    color: str
    qty: int
    sku: Sku
    sides: tuple[Side, ...]
    instructions_url: str = ""
    customization: dict[str, str] = field(default_factory=dict)
    notes: str = ""


@dataclass(frozen=True, slots=True)
class Comment:
    text: str
    author: str
    created_at: str  # ISO-8601 string from the store


@dataclass(frozen=True, slots=True)
class FulfillmentOrder:
    order_number: str
    recipient: Recipient
    products: tuple[Product, ...]
    channel: str = "Amazon · DE"
    amazon_url: str = ""
    gift_box: bool = False
    label: Label | None = None
    placed_at: datetime | None = None
    notes: str = ""


def all_sides(order: FulfillmentOrder) -> set[tuple[str, str]]:
    """Every (item_id, side_name) pair in the order."""
    return {(p.item_id, s.name) for p in order.products for s in p.sides}


def derive_status(
    order: FulfillmentOrder,
    *,
    engraved: set[tuple[str, str]],
    override: OrderStatus | None,
) -> OrderStatus:
    """Status = explicit override (shipped/hold) else progress-derived."""
    if override in (OrderStatus.SHIPPED, OrderStatus.HOLD):
        return override
    total = all_sides(order)
    done = engraved & total
    if total and done == total:
        return OrderStatus.ENGRAVED
    if done:
        return OrderStatus.ENGRAVING
    return OrderStatus.RECEIVED


def type_rank(product_type: str) -> int:
    try:
        return _TYPE_ORDER.index(product_type)
    except ValueError:
        return 99


def queue_sort_key(order: FulfillmentOrder) -> tuple[int, str]:
    """Group by product-type rank (first product), then oldest placed first."""
    primary = order.products[0].product_type if order.products else "Other"
    placed = order.placed_at.isoformat() if order.placed_at else ""
    return (type_rank(primary), placed)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/core/test_fulfillment.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/lbb/core/fulfillment.py tests/unit/core/test_fulfillment.py
git add src/lbb/core/fulfillment.py tests/unit/core/test_fulfillment.py
git commit -m "feat(core): fulfillment domain — products/sides, status, queue sort"
```

---

## Phase 2 — Persistence (state store)

### Task 2: SqliteStateStore schema + side engraving

**Files:**
- Create: `src/lbb/adapters/state_migrations.py`, `src/lbb/ports/fulfillment.py`, `src/lbb/adapters/sqlite_state.py`
- Test: `tests/unit/adapters/test_sqlite_state.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/adapters/test_sqlite_state.py
from lbb.adapters.sqlite_state import SqliteStateStore
from lbb.core.fulfillment import OrderStatus


def test_mark_side_then_read_back(tmp_path):
    s = SqliteStateStore(tmp_path / "state.sqlite")
    s.mark_side("306-1", "A", "Front", True)
    assert s.engraved_sides("306-1") == {("A", "Front")}


def test_unmark_side_removes_it(tmp_path):
    s = SqliteStateStore(tmp_path / "state.sqlite")
    s.mark_side("306-1", "A", "Front", True)
    s.mark_side("306-1", "A", "Front", False)
    assert s.engraved_sides("306-1") == set()


def test_override_set_get_clear(tmp_path):
    s = SqliteStateStore(tmp_path / "state.sqlite")
    assert s.get_override("306-1") is None
    s.set_override("306-1", OrderStatus.HOLD)
    assert s.get_override("306-1") is OrderStatus.HOLD
    s.set_override("306-1", None)
    assert s.get_override("306-1") is None


def test_comments_append_in_order(tmp_path):
    s = SqliteStateStore(tmp_path / "state.sqlite")
    s.add_comment("306-1", "re-engrave back side", "A. Fink")
    s.add_comment("306-1", "fixed", "A. Fink")
    texts = [c.text for c in s.comments("306-1")]
    assert texts == ["re-engrave back side", "fixed"]


def test_state_persists_across_reopen(tmp_path):
    db = tmp_path / "state.sqlite"
    SqliteStateStore(db).mark_side("306-1", "A", "Front", True)
    assert SqliteStateStore(db).engraved_sides("306-1") == {("A", "Front")}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/adapters/test_sqlite_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lbb.adapters.sqlite_state'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/lbb/adapters/state_migrations.py
STATE_SCHEMA_V1 = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS engraved_sides (
  order_number TEXT NOT NULL,
  item_id      TEXT NOT NULL,
  side_name    TEXT NOT NULL,
  engraved_at  TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (order_number, item_id, side_name)
);

CREATE TABLE IF NOT EXISTS order_overrides (
  order_number TEXT PRIMARY KEY,
  status       TEXT NOT NULL,
  updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS order_comments (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  order_number TEXT NOT NULL,
  text         TEXT NOT NULL,
  author       TEXT NOT NULL DEFAULT '',
  created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
```

```python
# src/lbb/ports/fulfillment.py
from __future__ import annotations

from typing import Protocol

from lbb.core.fulfillment import Comment, FulfillmentOrder, OrderStatus


class FulfillmentRepository(Protocol):
    def get(self, order_number: str) -> FulfillmentOrder | None: ...
    def list_all(self) -> list[FulfillmentOrder]: ...


class FulfillmentStateStore(Protocol):
    def engraved_sides(self, order_number: str) -> set[tuple[str, str]]: ...
    def mark_side(self, order_number: str, item_id: str, side_name: str, engraved: bool) -> None: ...
    def get_override(self, order_number: str) -> OrderStatus | None: ...
    def set_override(self, order_number: str, status: OrderStatus | None) -> None: ...
    def comments(self, order_number: str) -> list[Comment]: ...
    def add_comment(self, order_number: str, text: str, author: str) -> None: ...
```

```python
# src/lbb/adapters/sqlite_state.py
"""SQLite-backed FulfillmentStateStore — local operator progress.

Mirrors SqliteProfileRepository's construction pattern. Shaped so a future
sync job can push this state up to Airtable/Supabase without UI changes.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from lbb.adapters.state_migrations import STATE_SCHEMA_V1
from lbb.core.fulfillment import Comment, OrderStatus
from lbb.ports.fulfillment import FulfillmentStateStore


class SqliteStateStore(FulfillmentStateStore):
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(STATE_SCHEMA_V1)

    def engraved_sides(self, order_number: str) -> set[tuple[str, str]]:
        rows = self._conn.execute(
            "SELECT item_id, side_name FROM engraved_sides WHERE order_number = ?",
            (order_number,),
        ).fetchall()
        return {(r["item_id"], r["side_name"]) for r in rows}

    def mark_side(self, order_number: str, item_id: str, side_name: str, engraved: bool) -> None:
        with self._conn:
            if engraved:
                self._conn.execute(
                    """INSERT INTO engraved_sides (order_number, item_id, side_name)
                       VALUES (?, ?, ?)
                       ON CONFLICT(order_number, item_id, side_name) DO NOTHING""",
                    (order_number, item_id, side_name),
                )
            else:
                self._conn.execute(
                    """DELETE FROM engraved_sides
                       WHERE order_number = ? AND item_id = ? AND side_name = ?""",
                    (order_number, item_id, side_name),
                )

    def get_override(self, order_number: str) -> OrderStatus | None:
        row = self._conn.execute(
            "SELECT status FROM order_overrides WHERE order_number = ?",
            (order_number,),
        ).fetchone()
        return OrderStatus(row["status"]) if row else None

    def set_override(self, order_number: str, status: OrderStatus | None) -> None:
        with self._conn:
            if status is None:
                self._conn.execute(
                    "DELETE FROM order_overrides WHERE order_number = ?", (order_number,)
                )
            else:
                self._conn.execute(
                    """INSERT INTO order_overrides (order_number, status) VALUES (?, ?)
                       ON CONFLICT(order_number) DO UPDATE SET
                           status = excluded.status, updated_at = datetime('now')""",
                    (order_number, str(status)),
                )

    def comments(self, order_number: str) -> list[Comment]:
        rows = self._conn.execute(
            """SELECT text, author, created_at FROM order_comments
               WHERE order_number = ? ORDER BY id""",
            (order_number,),
        ).fetchall()
        return [Comment(text=r["text"], author=r["author"], created_at=r["created_at"]) for r in rows]

    def add_comment(self, order_number: str, text: str, author: str) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO order_comments (order_number, text, author) VALUES (?, ?, ?)",
                (order_number, text, author),
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/adapters/test_sqlite_state.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/lbb/adapters/sqlite_state.py src/lbb/adapters/state_migrations.py src/lbb/ports/fulfillment.py tests/unit/adapters/test_sqlite_state.py
git add src/lbb/adapters/sqlite_state.py src/lbb/adapters/state_migrations.py src/lbb/ports/fulfillment.py tests/unit/adapters/test_sqlite_state.py
git commit -m "feat(adapters): SqliteStateStore — engraved sides, overrides, comments"
```

---

## Phase 3 — Read adapter (seeded orders)

### Task 3: Seed JSON + JsonFulfillmentRepository

**Files:**
- Create: `src/lbb/web/__init__.py`, `src/lbb/web/assets/__init__.py`, `src/lbb/web/assets/seed-orders/orders.json`
- Create: `src/lbb/adapters/json_fulfillment.py`
- Test: `tests/unit/adapters/test_json_fulfillment.py`

> The seed below carries TWO orders (one multi-side gift order, one single-side
> on-hold-able order). PDFs are generated in Task 9; for this adapter test we
> only assert parsing + path resolution, so the referenced files need not exist
> yet.

- [ ] **Step 1: Create the seed data**

```json
// src/lbb/web/assets/seed-orders/orders.json
{
  "orders": {
    "306-2309613-0964321": {
      "recipient": {"name": "Sabrina Wollweber", "address": "52525 Heinsberg, DE"},
      "channel": "Amazon · DE",
      "amazon_url": "https://sellercentral-europe.amazon.com/orders-v3/order/306-2309613-0964321",
      "gift_box": true,
      "placed_at": "2026-01-03T10:00:00Z",
      "label": {"carrier": "DHL Kleinpaket · 1 kg", "pdf_path": "labels/306-2309613-0964321.pdf"},
      "products": [
        {"item_id": "A", "name": "Heart necklace", "product_type": "Necklace",
         "color": "Gold", "qty": 1, "sku": "FL-NECK-HEART-G",
         "instructions_url": "https://drive.google.com/file/d/17UCEpbZiYHLuJNULILJKsrleaEgulMev/view",
         "sides": [
           {"name": "Front", "pdf_path": "306-2309613-0964321-A-Front.pdf"},
           {"name": "Back", "pdf_path": "306-2309613-0964321-A-Back.pdf"}
         ]},
        {"item_id": "B", "name": "ID bracelet", "product_type": "Bracelet",
         "color": "Silver", "qty": 1, "sku": "FL-BRAC-ID-S",
         "sides": [{"name": "Front", "pdf_path": "306-2309613-0964321-B-Front.pdf"}]}
      ]
    },
    "304-9988776-1122334": {
      "recipient": {"name": "Nina Hofmann", "address": "70173 Stuttgart, DE"},
      "channel": "Amazon · DE",
      "amazon_url": "",
      "gift_box": false,
      "placed_at": "2026-01-01T09:00:00Z",
      "label": {"carrier": "DHL Kleinpaket · 1 kg", "pdf_path": "labels/304-9988776-1122334.pdf"},
      "products": [
        {"item_id": "A", "name": "Bangle", "product_type": "Bracelet",
         "color": "Gold", "qty": 1, "sku": "FL-BRAC-BANGLE-G",
         "sides": [{"name": "Front", "pdf_path": "304-9988776-1122334-A-Front.pdf"}]}
      ]
    }
  }
}
```

Also create empty `src/lbb/web/__init__.py` and `src/lbb/web/assets/__init__.py`.

- [ ] **Step 2: Write the failing test**

```python
# tests/unit/adapters/test_json_fulfillment.py
import json
from pathlib import Path

from lbb.adapters.json_fulfillment import JsonFulfillmentRepository

SEED = {
    "orders": {
        "306-1": {
            "recipient": {"name": "Sabrina W.", "address": "52525 Heinsberg, DE"},
            "gift_box": True,
            "placed_at": "2026-01-03T10:00:00Z",
            "label": {"carrier": "DHL · 1 kg", "pdf_path": "labels/306-1.pdf"},
            "products": [
                {"item_id": "A", "name": "Heart necklace", "product_type": "Necklace",
                 "color": "Gold", "qty": 1, "sku": "FL-NECK-HEART-G",
                 "sides": [{"name": "Front", "pdf_path": "306-1-A-Front.pdf"},
                           {"name": "Back", "pdf_path": "306-1-A-Back.pdf"}]}
            ],
        }
    }
}


def _seed_dir(tmp_path: Path) -> Path:
    d = tmp_path / "seed"
    d.mkdir()
    (d / "orders.json").write_text(json.dumps(SEED), encoding="utf-8")
    return d


def test_seeds_on_first_run(tmp_path):
    orders_dir = tmp_path / "orders"
    repo = JsonFulfillmentRepository(orders_dir, seed_dir=_seed_dir(tmp_path))
    assert (orders_dir / "orders.json").exists()
    assert repo.get("306-1") is not None


def test_parses_products_and_sides(tmp_path):
    repo = JsonFulfillmentRepository(tmp_path / "orders", seed_dir=_seed_dir(tmp_path))
    o = repo.get("306-1")
    assert o.recipient.name == "Sabrina W."
    assert o.gift_box is True
    assert o.label.carrier == "DHL · 1 kg"
    p = o.products[0]
    assert p.product_type == "Necklace"
    assert [s.name for s in p.sides] == ["Front", "Back"]


def test_resolves_side_pdf_paths_to_orders_dir(tmp_path):
    orders_dir = tmp_path / "orders"
    repo = JsonFulfillmentRepository(orders_dir, seed_dir=_seed_dir(tmp_path))
    side = repo.get("306-1").products[0].sides[0]
    assert Path(side.pdf_path).is_absolute()
    assert side.pdf_path.endswith("306-1-A-Front.pdf")
    assert str(orders_dir.resolve()) in side.pdf_path


def test_resolves_label_path_to_orders_dir(tmp_path):
    orders_dir = tmp_path / "orders"
    repo = JsonFulfillmentRepository(orders_dir, seed_dir=_seed_dir(tmp_path))
    assert Path(repo.get("306-1").label.pdf_path).is_absolute()


def test_malformed_json_yields_empty(tmp_path):
    orders_dir = tmp_path / "orders"
    orders_dir.mkdir()
    (orders_dir / "orders.json").write_text("{ not json", encoding="utf-8")
    repo = JsonFulfillmentRepository(orders_dir)
    assert repo.list_all() == []
    assert repo.get("306-1") is None


def test_list_all_sorted_by_order_number(tmp_path):
    repo = JsonFulfillmentRepository(tmp_path / "orders", seed_dir=_seed_dir(tmp_path))
    assert [o.order_number for o in repo.list_all()] == ["306-1"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/unit/adapters/test_json_fulfillment.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lbb.adapters.json_fulfillment'`

- [ ] **Step 4: Write minimal implementation**

```python
# src/lbb/adapters/json_fulfillment.py
"""JSON-backed FulfillmentRepository — directory simulation of the future
Airtable/Supabase backend. Same first-run seed-copy policy as the legacy
JsonOrderRepository: on first construction, if orders_dir is absent and a
seed_dir was given, the seed folder (orders.json + design/label PDFs) is
copied wholesale; thereafter the user-home folder is authoritative.
"""

from __future__ import annotations

import json
import shutil
import sys
import traceback
from datetime import datetime
from pathlib import Path

from lbb.core.fulfillment import (
    FulfillmentOrder,
    Label,
    Product,
    Recipient,
    Side,
)
from lbb.core.models import Sku
from lbb.ports.fulfillment import FulfillmentRepository


class JsonFulfillmentRepository(FulfillmentRepository):
    def __init__(self, orders_dir: Path, *, seed_dir: Path | None = None):
        self.orders_dir = Path(orders_dir)
        self.seed_dir = Path(seed_dir) if seed_dir is not None else None
        self._orders: dict[str, FulfillmentOrder] = {}
        self._load()

    def get(self, order_number: str) -> FulfillmentOrder | None:
        return self._orders.get(order_number)

    def list_all(self) -> list[FulfillmentOrder]:
        return sorted(self._orders.values(), key=lambda o: o.order_number)

    # ── internal ──────────────────────────────────────────────────────────
    def _load(self) -> None:
        if not self.orders_dir.exists() and self.seed_dir and self.seed_dir.exists():
            shutil.copytree(self.seed_dir, self.orders_dir)
        json_path = self.orders_dir / "orders.json"
        if not json_path.exists():
            return
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            traceback.print_exception(e, file=sys.stderr)
            return
        node = data.get("orders") if isinstance(data, dict) else None
        if not isinstance(node, dict):
            return
        for order_number, payload in node.items():
            try:
                self._orders[order_number] = self._parse(order_number, payload)
            except (TypeError, ValueError, KeyError) as e:
                traceback.print_exception(e, file=sys.stderr)

    def _parse(self, order_number: str, payload: dict) -> FulfillmentOrder:
        rec = payload.get("recipient") or {}
        products: list[Product] = []
        for raw in payload.get("products") or []:
            sides = tuple(
                Side(name=str(s["name"]), pdf_path=self._resolve(str(s.get("pdf_path", ""))))
                for s in raw.get("sides") or []
            )
            products.append(
                Product(
                    item_id=str(raw["item_id"]),
                    name=str(raw.get("name", "")),
                    product_type=str(raw.get("product_type", "")),
                    color=str(raw.get("color", "")),
                    qty=int(raw.get("qty", 1)),
                    sku=Sku(str(raw["sku"])),
                    sides=sides,
                    instructions_url=str(raw.get("instructions_url", "")),
                    customization={str(k): str(v) for k, v in (raw.get("customization") or {}).items()},
                    notes=str(raw.get("notes", "")),
                )
            )
        label_node = payload.get("label")
        label = (
            Label(carrier=str(label_node.get("carrier", "")),
                  pdf_path=self._resolve(str(label_node.get("pdf_path", ""))))
            if isinstance(label_node, dict) else None
        )
        placed_raw = payload.get("placed_at")
        placed: datetime | None = None
        if isinstance(placed_raw, str) and placed_raw:
            try:
                placed = datetime.fromisoformat(placed_raw.replace("Z", "+00:00"))
            except ValueError:
                placed = None
        return FulfillmentOrder(
            order_number=order_number,
            recipient=Recipient(name=str(rec.get("name", "")), address=str(rec.get("address", ""))),
            products=tuple(products),
            channel=str(payload.get("channel", "Amazon · DE")),
            amazon_url=str(payload.get("amazon_url", "")),
            gift_box=bool(payload.get("gift_box", False)),
            label=label,
            placed_at=placed,
            notes=str(payload.get("notes", "")),
        )

    def _resolve(self, raw: str) -> str:
        if not raw:
            return ""
        p = Path(raw)
        return str(p) if p.is_absolute() else str((self.orders_dir / raw).resolve())
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/adapters/test_json_fulfillment.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff check src/lbb/adapters/json_fulfillment.py tests/unit/adapters/test_json_fulfillment.py
git add src/lbb/web src/lbb/adapters/json_fulfillment.py tests/unit/adapters/test_json_fulfillment.py
git commit -m "feat(adapters): JsonFulfillmentRepository + seed orders.json"
```

---

## Phase 4 — Service (the brain)

### Task 4: FulfillmentService — list/get view models + status

**Files:**
- Create: `src/lbb/app/fulfillment_service.py`
- Test: `tests/integration/test_fulfillment_service.py`

> The service depends on `FulfillmentRepository`, `FulfillmentStateStore`, a
> `LightBurnPort`, and `PipelineDeps` (reused for the engrave path). Tests use
> the in-repo `LightBurnFake` (`src/lbb/adapters/lightburn_fake.py`).

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_fulfillment_service.py
import json
from pathlib import Path

import pytest

from lbb.adapters.json_fulfillment import JsonFulfillmentRepository
from lbb.adapters.lightburn_fake import LightBurnFake
from lbb.adapters.sqlite_state import SqliteStateStore
from lbb.app.fulfillment_service import FulfillmentService
from lbb.core.fulfillment import OrderStatus

SEED = {
    "orders": {
        "306-1": {
            "recipient": {"name": "Sabrina W.", "address": "52525 Heinsberg, DE"},
            "gift_box": True, "placed_at": "2026-01-03T10:00:00Z",
            "label": {"carrier": "DHL · 1 kg", "pdf_path": "labels/306-1.pdf"},
            "products": [
                {"item_id": "A", "name": "Heart necklace", "product_type": "Necklace",
                 "color": "Gold", "qty": 1, "sku": "FL-NECK-HEART-G",
                 "sides": [{"name": "Front", "pdf_path": "306-1-A-Front.pdf"},
                           {"name": "Back", "pdf_path": "306-1-A-Back.pdf"}]}
            ],
        },
        "306-2": {
            "recipient": {"name": "Nina H.", "address": "70173 Stuttgart, DE"},
            "placed_at": "2026-01-01T09:00:00Z",
            "products": [
                {"item_id": "A", "name": "Bangle", "product_type": "Bracelet",
                 "color": "Gold", "qty": 1, "sku": "FL-BRAC-BANGLE-G",
                 "sides": [{"name": "Front", "pdf_path": "306-2-A-Front.pdf"}]}
            ],
        },
    }
}


@pytest.fixture
def svc(tmp_path) -> FulfillmentService:
    orders_dir = tmp_path / "orders"
    orders_dir.mkdir()
    (orders_dir / "orders.json").write_text(json.dumps(SEED), encoding="utf-8")
    # Create the design PDFs the service will hand to LightBurn.
    for name in ("306-1-A-Front.pdf", "306-1-A-Back.pdf", "306-2-A-Front.pdf"):
        (orders_dir / name).write_bytes(b"%PDF-1.4\n%%EOF\n")
    repo = JsonFulfillmentRepository(orders_dir)
    state = SqliteStateStore(tmp_path / "state.sqlite")
    return FulfillmentService(repo=repo, state=state, lightburn=LightBurnFake())


def test_list_orders_grouped_bracelet_before_necklace(svc):
    cards = svc.list_orders(filter="all", query="")
    assert [c["order_number"] for c in cards] == ["306-2", "306-1"]
    assert cards[0]["bucket"] == "Bracelets"


def test_get_order_initial_status_received(svc):
    detail = svc.get_order("306-1")
    assert detail["status"] == "received"
    assert detail["progress"] == {"done": 0, "total": 2}
    assert detail["gift_box"] is True


def test_engrave_side_opens_pdf_and_marks_done(svc):
    res = svc.engrave_side("306-1", "A", "Front")
    assert res["ok"] is True
    assert res["status"] == "engraving"
    assert svc.lightburn.loaded[-1].name == "306-1-A-Front.pdf"


def test_engrave_all_sides_flips_to_engraved(svc):
    svc.engrave_side("306-1", "A", "Front")
    res = svc.engrave_side("306-1", "A", "Back")
    assert res["status"] == "engraved"


def test_ship_blocked_until_all_engraved(svc):
    blocked = svc.ship_order("306-1")
    assert blocked["ok"] is False
    svc.engrave_side("306-1", "A", "Front")
    svc.engrave_side("306-1", "A", "Back")
    ok = svc.ship_order("306-1")
    assert ok["ok"] is True
    assert svc.get_order("306-1")["status"] == "shipped"


def test_engrave_missing_pdf_returns_error(svc, tmp_path):
    res = svc.engrave_side("306-2", "A", "Front")  # exists → ok
    assert res["ok"] is True
    # Point at a non-existent side
    bad = svc.engrave_side("306-1", "A", "Nonexistent")
    assert bad["ok"] is False
    assert "side" in bad["error"].lower()


def test_set_status_hold_then_clear(svc):
    svc.set_status("306-1", "hold")
    assert svc.get_order("306-1")["status"] == "hold"
    svc.set_status("306-1", "received")
    assert svc.get_order("306-1")["status"] == "received"


def test_add_comment_round_trips(svc):
    svc.add_comment("306-1", "re-engrave back")
    assert svc.get_order("306-1")["comments"][0]["text"] == "re-engrave back"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_fulfillment_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lbb.app.fulfillment_service'`

- [ ] **Step 3: Write minimal implementation**

> `LightBurnFake` (`src/lbb/adapters/lightburn_fake.py`) already exposes
> `.loaded: list[Path]` (every `load_file` call) and `.is_running()`, and
> defaults to `running=True`. The assertions above use `.loaded` directly — no
> change to the fake is needed.

```python
# src/lbb/app/fulfillment_service.py
"""FulfillmentService — the order-fulfillment brain.

Merges read-only orders (FulfillmentRepository) with mutable progress
(FulfillmentStateStore), derives status, and dispatches per-side PDFs to
LightBurn via the direct-open path. Returns JSON-serialisable view models the
web bridge passes straight to the front-end. Knows nothing about pywebview.
"""

from __future__ import annotations

from pathlib import Path

from lbb.core.errors import LbbError
from lbb.core.fulfillment import (
    FulfillmentOrder,
    OrderStatus,
    all_sides,
    derive_status,
    queue_sort_key,
    type_rank,
)
from lbb.ports.fulfillment import FulfillmentRepository, FulfillmentStateStore
from lbb.ports.lightburn import LightBurnPort

_OPERATOR = "A. Fink"
_BUCKETS = {"Bracelet": "Bracelets", "Necklace": "Necklaces",
            "Keychain": "Keychains", "Flask": "Flasks"}


class FulfillmentService:
    def __init__(
        self,
        *,
        repo: FulfillmentRepository,
        state: FulfillmentStateStore,
        lightburn: LightBurnPort,
    ):
        self.repo = repo
        self.state = state
        self.lightburn = lightburn

    # ── queries ───────────────────────────────────────────────────────────
    def list_orders(self, *, filter: str = "all", query: str = "") -> list[dict]:
        q = (query or "").lower().replace(" ", "")
        orders = sorted(self.repo.list_all(), key=queue_sort_key)
        out: list[dict] = []
        for o in orders:
            status = self._status(o)
            if filter == "open" and status is OrderStatus.SHIPPED:
                continue
            if filter == "shipped" and status is not OrderStatus.SHIPPED:
                continue
            if q and q not in o.order_number.lower().replace(" ", ""):
                continue
            done, total = self._progress(o)
            primary = o.products[0].product_type if o.products else "Other"
            out.append({
                "order_number": o.order_number,
                "bucket": _BUCKETS.get(primary, "Other"),
                "primary_type": primary,
                "product_summary": self._summary(o),
                "placed_label": o.placed_at.strftime("%b %-d, %Y") if o.placed_at else "",
                "status": str(status),
                "gift_box": o.gift_box,
                "progress": {"done": done, "total": total},
            })
        return out

    def get_order(self, order_number: str) -> dict | None:
        o = self.repo.get(order_number)
        if o is None:
            return None
        engraved = self.state.engraved_sides(order_number)
        done, total = self._progress(o)
        return {
            "order_number": o.order_number,
            "recipient": {"name": o.recipient.name, "address": o.recipient.address},
            "channel": o.channel,
            "amazon_url": o.amazon_url,
            "gift_box": o.gift_box,
            "placed_label": o.placed_at.strftime("%b %-d, %Y") if o.placed_at else "",
            "label": ({"carrier": o.label.carrier, "has_pdf": bool(o.label.pdf_path)}
                      if o.label else None),
            "status": str(self._status(o)),
            "progress": {"done": done, "total": total},
            "products": [
                {
                    "item_id": p.item_id, "name": p.name, "product_type": p.product_type,
                    "color": p.color, "qty": p.qty, "sku": p.sku.value,
                    "instructions_url": p.instructions_url,
                    "sides": [
                        {"name": s.name, "engraved": (p.item_id, s.name) in engraved}
                        for s in p.sides
                    ],
                }
                for p in o.products
            ],
            "comments": [
                {"text": c.text, "author": c.author, "created_at": c.created_at}
                for c in self.state.comments(order_number)
            ],
        }

    def lightburn_status(self) -> dict:
        return {"running": self.lightburn.is_running()}

    # ── commands ──────────────────────────────────────────────────────────
    def engrave_side(self, order_number: str, item_id: str, side_name: str) -> dict:
        o = self.repo.get(order_number)
        if o is None:
            return {"ok": False, "error": "Order not found"}
        side = self._find_side(o, item_id, side_name)
        if side is None:
            return {"ok": False, "error": f"Unknown product side: {item_id}/{side_name}"}
        if not side.pdf_path or not Path(side.pdf_path).is_file():
            return {"ok": False, "error": "Design file not found for this side"}
        try:
            self.lightburn.load_file(Path(side.pdf_path))
        except LbbError as e:
            return {"ok": False, "error": str(e)}
        self.state.mark_side(order_number, item_id, side_name, True)
        done, total = self._progress(o)
        return {"ok": True, "status": str(self._status(o)), "progress": {"done": done, "total": total}}

    def set_status(self, order_number: str, status: str) -> dict:
        o = self.repo.get(order_number)
        if o is None:
            return {"ok": False, "error": "Order not found"}
        try:
            target = OrderStatus(status)
        except ValueError:
            return {"ok": False, "error": f"Unknown status: {status}"}
        if target is OrderStatus.SHIPPED:
            return self.ship_order(order_number)
        if target in (OrderStatus.HOLD,):
            self.state.set_override(order_number, OrderStatus.HOLD)
        else:
            self.state.set_override(order_number, None)  # back to derived
        return {"ok": True, "status": str(self._status(o))}

    def ship_order(self, order_number: str) -> dict:
        o = self.repo.get(order_number)
        if o is None:
            return {"ok": False, "error": "Order not found"}
        done, total = self._progress(o)
        if done != total:
            return {"ok": False, "error": "Engrave all sides first"}
        self.state.set_override(order_number, OrderStatus.SHIPPED)
        return {"ok": True, "status": str(OrderStatus.SHIPPED)}

    def add_comment(self, order_number: str, text: str) -> dict:
        if not text.strip():
            return {"ok": False, "error": "Empty comment"}
        self.state.add_comment(order_number, text.strip(), _OPERATOR)
        return {"ok": True}

    # ── helpers ───────────────────────────────────────────────────────────
    def _status(self, o: FulfillmentOrder) -> OrderStatus:
        return derive_status(o, engraved=self.state.engraved_sides(o.order_number),
                             override=self.state.get_override(o.order_number))

    def _progress(self, o: FulfillmentOrder) -> tuple[int, int]:
        total = all_sides(o)
        done = self.state.engraved_sides(o.order_number) & total
        return (len(done), len(total))

    @staticmethod
    def _find_side(o: FulfillmentOrder, item_id: str, side_name: str):
        for p in o.products:
            if p.item_id == item_id:
                for s in p.sides:
                    if s.name == side_name:
                        return s
        return None

    @staticmethod
    def _summary(o: FulfillmentOrder) -> str:
        if not o.products:
            return ""
        n = len(o.products)
        head = o.products[0].name
        return head if n == 1 else f"{head} +{n - 1}"
```

> **Windows note on `strftime("%b %-d, %Y")`:** the `%-d` (no-leading-zero day)
> flag is POSIX-only and raises on Windows. Replace with a portable helper:
> `f"{o.placed_at:%b} {o.placed_at.day}, {o.placed_at:%Y}"`. Use that form in
> both `list_orders` and `get_order`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/integration/test_fulfillment_service.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/lbb/app/fulfillment_service.py tests/integration/test_fulfillment_service.py
git add src/lbb/app/fulfillment_service.py tests/integration/test_fulfillment_service.py
git commit -m "feat(app): FulfillmentService — list/get/engrave/ship/status/comment"
```

---

## Phase 5 — Web bridge

### Task 5: JsApiBridge — thin JSON marshaller

**Files:**
- Create: `src/lbb/web/bridge.py`
- Test: `tests/web/test_bridge.py` (+ `tests/web/__init__.py`)

- [ ] **Step 1: Write the failing test**

```python
# tests/web/test_bridge.py
from lbb.web.bridge import JsApiBridge


class _StubService:
    def __init__(self):
        self.calls = []

    def list_orders(self, *, filter="all", query=""):
        self.calls.append(("list", filter, query)); return [{"order_number": "306-1"}]

    def get_order(self, order_number):
        self.calls.append(("get", order_number)); return {"order_number": order_number}

    def engrave_side(self, order_number, item_id, side_name):
        self.calls.append(("engrave", order_number, item_id, side_name)); return {"ok": True}

    def set_status(self, order_number, status):
        return {"ok": True, "status": status}

    def ship_order(self, order_number):
        return {"ok": True}

    def add_comment(self, order_number, text):
        return {"ok": True}

    def lightburn_status(self):
        return {"running": True}


def test_list_orders_delegates_with_kwargs():
    svc = _StubService()
    bridge = JsApiBridge(svc)
    assert bridge.list_orders("open", "306") == [{"order_number": "306-1"}]
    assert svc.calls[0] == ("list", "open", "306")


def test_engrave_side_delegates_positionally():
    svc = _StubService()
    bridge = JsApiBridge(svc)
    assert bridge.engrave_side("306-1", "A", "Front") == {"ok": True}
    assert svc.calls[-1] == ("engrave", "306-1", "A", "Front")


def test_open_helpers_are_safe_noops_without_handler(monkeypatch):
    bridge = JsApiBridge(_StubService())
    # open_url should not raise even if the opener is stubbed to fail
    monkeypatch.setattr(bridge, "_open_path_or_url", lambda *_: None)
    assert bridge.open_amazon("https://example.com")["ok"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_bridge.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lbb.web.bridge'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/lbb/web/bridge.py
"""JsApiBridge — exposed to JavaScript as `window.pywebview.api`.

Every public method returns a JSON-serialisable value (dict/list/scalar) and
delegates to FulfillmentService. Open/print helpers use the OS shell. This
class deliberately holds no business logic — it only marshals arguments.
"""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from pathlib import Path


class JsApiBridge:
    def __init__(self, service):
        self._svc = service

    # ── queries ──
    def list_orders(self, filter="all", query=""):  # noqa: A002 - JS-facing name
        return self._svc.list_orders(filter=filter, query=query)

    def get_order(self, order_number):
        return self._svc.get_order(order_number)

    def lightburn_status(self):
        return self._svc.lightburn_status()

    # ── commands ──
    def engrave_side(self, order_number, item_id, side_name):
        return self._svc.engrave_side(order_number, item_id, side_name)

    def set_status(self, order_number, status):
        return self._svc.set_status(order_number, status)

    def ship_order(self, order_number):
        return self._svc.ship_order(order_number)

    def add_comment(self, order_number, text):
        return self._svc.add_comment(order_number, text)

    # ── shell helpers ──
    def open_amazon(self, url):
        return self._open_path_or_url(url) or {"ok": True}

    def open_instructions(self, url):
        return self._open_path_or_url(url) or {"ok": True}

    def open_label(self, order_number):
        path = self._svc.label_path(order_number) if hasattr(self._svc, "label_path") else None
        if not path:
            return {"ok": False, "error": "No label file"}
        return self._open_path_or_url(path) or {"ok": True}

    def print_label(self, order_number):
        path = self._svc.label_path(order_number) if hasattr(self._svc, "label_path") else None
        if not path:
            return {"ok": False, "error": "No label file"}
        return self._print_path(path)

    # ── internals ──
    def _open_path_or_url(self, target: str):
        try:
            if target.startswith(("http://", "https://")):
                webbrowser.open(target)
            elif sys.platform.startswith("win"):
                os.startfile(target)  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.Popen(["open", target])
            else:
                subprocess.Popen(["xdg-open", target])
            return None
        except OSError as e:
            return {"ok": False, "error": str(e)}

    def _print_path(self, target: str):
        try:
            if sys.platform.startswith("win"):
                os.startfile(target, "print")  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.Popen(["lpr", target])
            else:
                subprocess.Popen(["lp", target])
            return {"ok": True}
        except OSError as e:
            return {"ok": False, "error": str(e)}
```

> **Add `label_path` to `FulfillmentService`** (it's referenced above). Append:
> ```python
> def label_path(self, order_number: str) -> str | None:
>     o = self.repo.get(order_number)
>     if o and o.label and o.label.pdf_path and Path(o.label.pdf_path).is_file():
>         return o.label.pdf_path
>     return None
> ```
> Add a one-line service test for it in `test_fulfillment_service.py`
> (`test_label_path_returns_existing_file` — create a `labels/` PDF in the
> fixture) before committing.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/web/test_bridge.py tests/integration/test_fulfillment_service.py -v`
Expected: PASS

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/lbb/web/bridge.py tests/web/test_bridge.py
git add src/lbb/web/bridge.py tests/web src/lbb/app/fulfillment_service.py tests/integration/test_fulfillment_service.py
git commit -m "feat(web): JsApiBridge + service.label_path"
```

---

## Phase 6 — Front-end assets (port the prototype)

### Task 6: Copy prototype → split assets

**Files:**
- Create: `src/lbb/web/assets/index.html`, `src/lbb/web/assets/app.css`, `src/lbb/web/assets/app.js`

- [ ] **Step 1: Copy + split the prototype**

```powershell
Copy-Item "C:\Users\Client\Documents\hauke\flanacom\engraving-fulfillment-tool.html" `
  "src\lbb\web\assets\index.html"
```

Then edit `index.html`:
- Move the entire contents of the `<style>…</style>` block into `app.css`; replace the block with `<link rel="stylesheet" href="app.css">`.
- Move the entire contents of the `<script>…</script>` block into `app.js`; replace the block with `<script src="bridge-client.js"></script>` immediately followed by `<script src="app.js"></script>` (bridge-client defined in Task 7, loaded first).

- [ ] **Step 2: Verify it still opens statically (manual smoke)**

Open `src/lbb/web/assets/index.html` directly in a browser. Expected: dashboard renders from the prototype's in-memory `ORDERS` array (still present in `app.js` at this point — we replace it next). This confirms the split didn't break paths.

- [ ] **Step 3: Commit**

```bash
git add src/lbb/web/assets/index.html src/lbb/web/assets/app.css src/lbb/web/assets/app.js
git commit -m "chore(web): import prototype, split into index.html/app.css/app.js"
```

### Task 7: Rewire app.js to the live bridge

**Files:**
- Create: `src/lbb/web/assets/bridge-client.js`
- Modify: `src/lbb/web/assets/app.js`

This replaces the prototype's in-memory data + `setTimeout` fakes with real `window.pywebview.api` calls. The prototype's *rendering* functions (`renderDashboard`, `renderOrder`, `statusOf`, `typeRank`, toast, modal) stay; only the **data source** and **action** functions change.

- [ ] **Step 1: Create the bridge client (with a browser fallback)**

```javascript
// src/lbb/web/assets/bridge-client.js
// Thin async wrapper over window.pywebview.api. When pywebview is absent
// (plain browser dev), falls back to a tiny in-memory mock so the UI still
// renders. The mock is dev-only and never ships behaviour the backend lacks.
const API = (() => {
  const real = () => window.pywebview && window.pywebview.api;
  const wrap = (name) => (...args) => {
    const api = real();
    if (api && api[name]) return api[name](...args);
    return Promise.resolve(MOCK[name] ? MOCK[name](...args) : null);
  };
  const MOCK = {
    list_orders: () => [],
    get_order: () => null,
    engrave_side: () => ({ ok: true, status: "engraving", progress: { done: 1, total: 1 } }),
    set_status: (_o, s) => ({ ok: true, status: s }),
    ship_order: () => ({ ok: true }),
    add_comment: () => ({ ok: true }),
    open_amazon: () => ({ ok: true }),
    open_instructions: () => ({ ok: true }),
    open_label: () => ({ ok: true }),
    print_label: () => ({ ok: true }),
    lightburn_status: () => ({ running: false }),
  };
  return {
    listOrders: wrap("list_orders"),
    getOrder: wrap("get_order"),
    engraveSide: wrap("engrave_side"),
    setStatus: wrap("set_status"),
    shipOrder: wrap("ship_order"),
    addComment: wrap("add_comment"),
    openAmazon: wrap("open_amazon"),
    openInstructions: wrap("open_instructions"),
    openLabel: wrap("open_label"),
    printLabel: wrap("print_label"),
    lightburnStatus: wrap("lightburn_status"),
  };
})();
```

- [ ] **Step 2: Replace the data + action layer in app.js**

In `app.js`:

1. **Delete** the hard-coded `const ORDERS=[…]` array and the `prod()` /
   sample-data helpers that build it. Keep `productSVG`, `DEFS`, `GIFT_SVG`,
   `TYPE_ORDER`, and all `render*` helpers.

2. **Add module state** for live data near the top:
   ```javascript
   let ORDERS = [];          // dashboard cards from the backend
   let CURRENT = null;       // full order detail for the open order
   ```

3. **Replace `renderDashboard`'s data source.** Make it async and pull cards:
   ```javascript
   async function loadDashboard(){
     const filter = document.querySelector('#filterChips .chip.active')?.dataset.f || 'all';
     const q = document.getElementById('searchInput').value || '';
     ORDERS = await API.listOrders(filter, q);
     renderDashboard();   // existing renderer, now reading the cards' fields
   }
   ```
   Update `renderDashboard` to read the card shape returned by the service
   (`order_number`, `bucket`, `product_summary`, `placed_label`, `status`,
   `gift_box`, `progress.done/total`) instead of the old object graph.
   Wire `oninput`/filter/`setFilter` to call `loadDashboard()`.

4. **Replace `openOrder`** to fetch detail:
   ```javascript
   async function openOrder(orderNumber){
     CURRENT = await API.getOrder(orderNumber);
     if(!CURRENT){ toast('Order not found','gold'); return; }
     active = firstPendingProduct(CURRENT);
     showView('order'); renderOrder();
   }
   ```
   Update `renderOrder` + `firstPendingProduct` + `tasksOf`/`doneOf`/`totOf`/
   `allEng`/`statusOf` to read `CURRENT` (fields: `products[].sides[].engraved`,
   `status`, `progress`, `recipient`, `gift_box`, `label`, `amazon_url`,
   `products[].instructions_url`). These mirror the old in-memory shape closely;
   adjust field names (`o.products` stays; `side.engraved` stays).

5. **Replace `engrave(pi, si)`** with a real call:
   ```javascript
   async function engrave(pi, si){
     if(busy) return;
     const p = CURRENT.products[pi], side = p.sides[si];
     busy = true; renderOrder();
     document.getElementById('livePillText').textContent = 'Opening LightBurn…';
     const res = await API.engraveSide(CURRENT.order_number, p.item_id, side.name);
     busy = false;
     if(!res.ok){ toast(res.error || 'Engrave failed','gold'); renderOrder(); return; }
     CURRENT = await API.getOrder(CURRENT.order_number);   // refresh truth
     const np = tasksOf(CURRENT).find(t=>!t.s.engraved); if(np) active = np.pi;
     renderOrder();
     toast(side.name + ' engraved' + (allEng(CURRENT)?' · all done':''));
   }
   ```

6. **Replace `confirmShip`, `onStatusSelect`, `sendComment`** to call
   `API.shipOrder`, `API.setStatus`, `API.addComment`, each refreshing
   `CURRENT = await API.getOrder(...)` then `renderOrder()`. Keep the
   gift-box modal (`askShip`) exactly as-is — it's UI-only; only `confirmShip`
   changes to await `API.shipOrder` before advancing the queue.

7. **Replace label/instructions/amazon links** to call
   `API.openLabel(CURRENT.order_number)`, `API.printLabel(...)`,
   `API.openInstructions(p.instructions_url)`, `API.openAmazon(CURRENT.amazon_url)`.

8. **Add the live status pill poll** at the bottom (replacing the static
   `In production` text driver):
   ```javascript
   async function pollLightBurn(){
     const { running } = await API.lightburnStatus();
     const pill = document.getElementById('livePill');
     if(pill){ pill.classList.toggle('hold', !running); }
   }
   setInterval(pollLightBurn, 3000); pollLightBurn();
   ```

9. **Replace the bootstrap** at the very bottom
   (`renderDashboard(); showView('dashboard');`) with:
   ```javascript
   window.addEventListener('pywebviewready', loadDashboard);
   document.addEventListener('DOMContentLoaded', () => { showView('dashboard'); loadDashboard(); });
   ```

- [ ] **Step 3: Manual smoke in a browser**

Open `index.html` in a browser (no pywebview). Expected: dashboard renders
empty (mock returns `[]`), no console errors. This proves the rewiring is
syntactically sound before we wrap it in the shell.

- [ ] **Step 4: Commit**

```bash
git add src/lbb/web/assets/bridge-client.js src/lbb/web/assets/app.js
git commit -m "feat(web): wire front-end to pywebview bridge API"
```

---

## Phase 7 — Shell + cutover

### Task 8: pywebview shell

**Files:**
- Create: `src/lbb/web/shell.py`
- Add dep: `pyproject.toml`

- [ ] **Step 1: Add pywebview**

```bash
uv add pywebview
```
Expected: `pyproject.toml` gains `pywebview` under `[project] dependencies`;
`uv.lock` updates.

- [ ] **Step 2: Write the shell**

```python
# src/lbb/web/shell.py
"""pywebview window host. The window is the ONLY responsibility here —
all logic lives in FulfillmentService, exposed via JsApiBridge."""

from __future__ import annotations

from importlib.resources import files

import webview

from lbb.web.bridge import JsApiBridge


def run_app(service, *, title: str = "Fulfillment Studio", debug: bool = False) -> None:
    index = files("lbb.web.assets") / "index.html"
    api = JsApiBridge(service)
    webview.create_window(title, url=str(index), js_api=api, width=1280, height=900, min_size=(960, 640))
    webview.start(debug=debug)
```

- [ ] **Step 3: Smoke-test import (no GUI in CI)**

Run: `uv run python -c "import lbb.web.shell; print('ok')"`
Expected: prints `ok` (import side-effect free).

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock src/lbb/web/shell.py
git commit -m "feat(web): pywebview shell host"
```

### Task 9: Seed PDFs via generate_fixtures

**Files:**
- Modify: `scripts/generate_fixtures.py`
- Create (generated): per-side design PDFs + `labels/*.pdf` under `src/lbb/web/assets/seed-orders/`

- [ ] **Step 1: Rewrite the existing `make_seed_orders()`** in
  `scripts/generate_fixtures.py`. It currently targets
  `src/lbb/ui/assets/seed-orders` and emits the four wallet PDFs
  (`305-A-john.pdf`, …). Repoint `seed_dir` to
  `REPO_ROOT / "src" / "lbb" / "web" / "assets" / "seed-orders"` and replace
  the `items` list so it emits **one PDF per side** referenced in the new
  `orders.json` — filenames must match the `pdf_path` values exactly:
  ```python
  items = [
      ("306-2309613-0964321-A-Front.pdf", 40.0, 60.0, "diamond"),
      ("306-2309613-0964321-A-Back.pdf",  40.0, 60.0, "three_bars"),
      ("306-2309613-0964321-B-Front.pdf", 50.0, 20.0, "circle"),
      ("304-9988776-1122334-A-Front.pdf", 50.0, 30.0, "triangle"),
  ]
  ```
  Reuse the existing `_make_engraving_pdf(out, w, h, decoration)` helper (it's
  vector-only and deterministic via the fixed `EPOCH`). Then add a sibling
  `make_seed_labels()` that writes `seed_dir / "labels" / "<order>.pdf"` for
  each order (a simple `_new_pdf` with a black-rectangle "barcode" box —
  vector only, no `pdf.text`/fonts, to keep bytes stable), and call it from
  `main()` right after `make_seed_orders()`.

- [ ] **Step 2: Generate**

Run: `uv run python scripts/generate_fixtures.py`
Expected: PDFs appear under `src/lbb/web/assets/seed-orders/` and
`…/seed-orders/labels/`; re-running produces byte-identical files.

- [ ] **Step 3: Verify the service opens them end-to-end**

Run: `uv run pytest tests/integration/test_fulfillment_service.py -v`
Expected: PASS (unchanged — uses its own tmp fixtures, but confirms no regressions).

- [ ] **Step 4: Commit**

```bash
git add scripts/generate_fixtures.py "src/lbb/web/assets/seed-orders"
git commit -m "feat(fixtures): per-side + label seed PDFs for fulfillment orders"
```

### Task 10: Cutover — wire entry point, move assets, retire Qt

**Files:**
- Modify: `src/lbb/app/container.py`, `src/lbb/__main__.py`, `.importlinter`, `packaging/lbb.spec`, `pyproject.toml`
- Move: `src/lbb/ui/assets/flanacom.ico`, `flanacom-logo.png` → `src/lbb/web/assets/`
- Delete: `src/lbb/ui/`, `src/lbb/core/order.py`, `src/lbb/ports/orders.py`, `src/lbb/adapters/json_orders.py`, and their tests

- [ ] **Step 1: Add a fulfillment composition root** in `container.py`

```python
# add to src/lbb/app/container.py
from importlib.resources import files
from pathlib import Path

from lbb.adapters.json_fulfillment import JsonFulfillmentRepository
from lbb.adapters.lightburn_shell import LightBurnShellAdapter
from lbb.adapters.sqlite_state import SqliteStateStore
from lbb.app.fulfillment_service import FulfillmentService


def build_fulfillment_service(orders_dir: Path, state_db: Path) -> FulfillmentService:
    seed_dir = Path(str(files("lbb.web.assets") / "seed-orders"))
    repo = JsonFulfillmentRepository(orders_dir, seed_dir=seed_dir)
    return FulfillmentService(
        repo=repo,
        state=SqliteStateStore(state_db),
        lightburn=LightBurnShellAdapter(),
    )
```

- [ ] **Step 2: Rewrite `__main__.py`** to launch the shell

```python
# src/lbb/__main__.py
"""Entry point: `uv run python -m lbb` or PyInstaller-built binary."""

import sys
from pathlib import Path

from lbb.app.container import build_fulfillment_service
from lbb.web.shell import run_app

_DATA_HOME = Path.home() / ".flanacom-tool"


def main() -> int:
    service = build_fulfillment_service(
        orders_dir=_DATA_HOME / "orders",
        state_db=_DATA_HOME / "state.sqlite",
    )
    run_app(service, title="Fulfillment Studio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Move brand assets + repoint**

```powershell
Move-Item src\lbb\ui\assets\flanacom.ico src\lbb\web\assets\flanacom.ico
Move-Item src\lbb\ui\assets\flanacom-logo.png src\lbb\web\assets\flanacom-logo.png
```
If `index.html` references a logo, point it at `flanacom-logo.png` (same dir).

- [ ] **Step 4: Update `.importlinter`** — replace the `ui-isolation` contract:

```ini
[importlinter:contract:web-isolation]
name = web/ cannot reach adapters directly
type = forbidden
source_modules =
    lbb.web
forbidden_modules =
    lbb.adapters
```
(Keep `core-purity` as-is. `web.bridge` imports only `app` — allowed.)

- [ ] **Step 5: Update `packaging/lbb.spec`** — set `ASSETS = SRC / "lbb" / "web" / "assets"`, bundle `index.html`, `app.css`, `app.js`, `bridge-client.js`, `flanacom.ico`, `flanacom-logo.png`, and every file under `seed-orders/` (including `labels/`) into `lbb/web/assets/...`. Add `collect_all('webview')` hiddenimports/datas (PyInstaller needs pywebview's platform backend). Keep the macOS BUNDLE block. Remove the QSS/Qt `datas` lines.

- [ ] **Step 6: Delete the Qt stack + legacy order modules + their tests**

```bash
git rm -r src/lbb/ui tests/ui
git rm src/lbb/core/order.py src/lbb/ports/orders.py src/lbb/adapters/json_orders.py
git rm tests/unit/core/test_order.py tests/unit/adapters/test_json_orders.py
```
Then remove the now-dead `orders=`/`PipelineDeps.orders` wiring and the old
`build_pipeline_deps` order branch in `container.py` (the dormant
template/pipeline tests stay). Grep for stale imports:

Run: `uv run python -c "import lbb.__main__"` and fix any ImportError.

- [ ] **Step 7: Drop the Qt runtime extra** (optional deps) from `pyproject.toml`
  if nothing dormant imports PySide6. `fpdf2`/`Pillow`/`pytest-qt` stay only if
  still referenced; otherwise remove `pytest-qt`. Re-sync: `uv sync --dev`.

- [ ] **Step 8: Full suite + lint + contracts**

Run: `uv run pytest && uv run ruff check && uv run lint-imports`
Expected: all green; no import-linter violations; no references to deleted modules.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: cutover to Fulfillment Studio web shell; retire PySide6 ui"
```

### Task 11: Windows smoke test + docs

**Files:**
- Modify: `HANDOFF.md`, `CLAUDE.md`, `README.md`

- [ ] **Step 1: Run the app from source**

Run: `uv run python -m lbb`
Expected: a 1280×900 window opens showing the Orders dashboard seeded from
`~/.flanacom-tool/orders/`. Click an order → order view renders. Click
"Engrave Front" with LightBurn installed → LightBurn opens the side's PDF;
the side flips to ✓ and persists after closing/reopening the app.

- [ ] **Step 2: Build the distributable**

Run: `uv run pyinstaller packaging/lbb.spec --clean --noconfirm`
Then run `dist\Fulfillment Studio\Fulfillment Studio.exe`.
Expected: same behaviour as from source. If the window is blank, confirm
WebView2 is present (Windows 11 ships it) and that `index.html` + assets are
in `…/_internal/lbb/web/assets/`.

- [ ] **Step 3: Update docs**

Update `HANDOFF.md` (new architecture map: web shell + service + state store;
operating guide for the dashboard flow; WebView2 note + Evergreen bootstrapper
link as fallback for older Windows; new data dir `~/.flanacom-tool/`),
`CLAUDE.md` (new data path, web layer, retired Qt note), and `README.md`
(one-line description + run command).

- [ ] **Step 4: Commit**

```bash
git add HANDOFF.md CLAUDE.md README.md
git commit -m "docs: Fulfillment Studio operating + build guide"
```

---

## Self-Review

**Spec coverage:**
- Faithful prototype render → Tasks 6–8, 10–11. ✓
- Dashboard grouping/queue/search/filters → Task 1 (sort) + Task 4 (`list_orders`) + Task 7 (rewire). ✓
- Per-side engrave via direct-open → Task 4 (`engrave_side` → `run_pipeline` path via `load_file`) + Task 7. ✓ (Note: service calls `lightburn.load_file` directly, which is exactly what `run_pipeline` does; using the port directly keeps the service dependency-light. Equivalent to direct-open.)
- Status pipeline + hold → Task 1 (`derive_status`) + Task 4 (`set_status`). ✓
- Gift-box ship confirmation → Task 7 (modal kept) + Task 4 (`ship_order` gate). ✓
- Comments → Task 2 (store) + Task 4 (`add_comment`) + Task 7. ✓
- Shipping label open/print → Task 5 (`open_label`/`print_label` + `label_path`). ✓
- Read-source vs local-state split → Tasks 2–4. ✓
- Persisted progress (supersedes in-memory) → Task 2 + Task 4 + Task 11 smoke. ✓
- Seed data (jewelry, sides, gift box, labels) → Task 3 + Task 9. ✓
- Packaging/WebView2/sharing → Tasks 8, 10, 11. ✓
- Retire Qt UI → Task 10. ✓

**Placeholder scan:** No "TBD/TODO". The web-asset rewiring (Tasks 6–7) gives concrete edits + real replacement code rather than re-pasting the 690-line prototype verbatim — the file is copied, then the named functions are replaced with the code shown.

**Type consistency:** `FulfillmentOrder.products`/`Product.item_id`/`Side.name`/`Side.pdf_path` used consistently across core, adapter, service, tests. Service view-model keys (`order_number`, `status`, `progress.done/total`, `products[].sides[].engraved`, `gift_box`, `bucket`, `product_summary`) match what the bridge returns and what Task 7's JS reads. `OrderStatus` string values (`received/engraving/engraved/shipped/hold`) match the prototype's `<select>` option values and `statusOf` keys. Engrave signature `engrave_side(order_number, item_id, side_name)` consistent in service, bridge, JS, and tests.

**Known reconciliation (flagged in-task):** POSIX `%-d` strftime is unsupported on Windows — Task 4 gives the portable replacement. `LightBurnFake` already exposes `.loaded`/`.is_running()` (verified), so no fake changes are needed.
