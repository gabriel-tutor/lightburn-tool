# Live Engraving API Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the seeded JSON backend with Hauke's live Supabase `engraving-api` as the source of truth — read all orders + signed-URL files, write back the 3 canonical statuses — and fix the pywebview cross-thread SQLite crash.

**Architecture:** Hexagonal layout unchanged. One read adapter is swapped for a live HTTP gateway behind a `HttpTransport` port (stdlib `urllib`, no new dependency, fully mockable). Domain collapses to the API's 3 statuses; local SQLite tracks only engraved file-keys as an operator aid. The secret API key is loaded Python-side (env → git-ignored config file), never in the JS frontend or the repo.

**Tech Stack:** Python 3.12, `uv`, pytest/hypothesis, stdlib `urllib`, `sqlite3`, pywebview, PyInstaller, import-linter, ruff.

**Reference:** `docs/superpowers/specs/2026-06-22-live-engraving-api-design.md`

**Conventions:** run everything with `uv run`. Run a single test with `uv run pytest <path>::<name> -v`. Run the suite with `uv run pytest -q`. Commit after each task. Work from `C:\Users\Client\Documents\hauke\lightburn-tool`.

---

### Task 1: Domain remap — 3-status model, file-key sides, order_id

**Files:**
- Modify: `src/lbb/core/fulfillment.py`
- Test: `tests/unit/core/test_fulfillment.py` (rewrite)

- [ ] **Step 1: Write the failing tests**

Replace the contents of `tests/unit/core/test_fulfillment.py` with:

```python
from datetime import datetime

from lbb.core.fulfillment import (
    FulfillmentOrder,
    OrderStatus,
    Product,
    Side,
    all_sides,
    normalize_type,
    queue_sort_key,
    type_rank,
)


def _order(**kw):
    base = dict(
        order_id="uuid-1",
        order_number="306-0001",
        products=(
            Product(
                product_type="Bracelet",
                band_color="Retro",
                coin_color="Silver",
                sides=(Side("Front", "engraving/a Front.pdf"),
                       Side("Back", "engraving/a Back.pdf")),
            ),
        ),
    )
    base.update(kw)
    return FulfillmentOrder(**base)


def test_status_enum_values_match_api():
    assert OrderStatus.NOT_DONE == "not_done_yet"
    assert OrderStatus.DONE == "graviert_verschickt"
    assert OrderStatus.REVISION == "revision"


def test_normalize_type_maps_api_casing():
    assert normalize_type("bracelet") == "Bracelet"
    assert normalize_type("mini_flask") == "MiniFlask"
    assert normalize_type("lighter") == "Lighter"
    assert normalize_type("unknown") == "Unknown"


def test_all_sides_returns_file_keys():
    o = _order()
    assert all_sides(o) == {"engraving/a Front.pdf", "engraving/a Back.pdf"}


def test_gift_box_derived_from_instruction():
    assert _order(instruction="With Gift Box each").gift_box is True
    assert _order(instruction="Plain").gift_box is False


def test_type_rank_orders_known_then_unknown():
    assert type_rank("Bracelet") < type_rank("Flask")
    assert type_rank("Bracelet") < type_rank("Zzz")


def test_queue_sort_key_groups_by_type_then_date():
    early = _order(order_number="A", placed_at=datetime(2026, 6, 1))
    late = _order(order_number="B", placed_at=datetime(2026, 6, 9))
    assert queue_sort_key(early) < queue_sort_key(late)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/unit/core/test_fulfillment.py -q`
Expected: FAIL (ImportError / AttributeError — new names not defined).

- [ ] **Step 3: Rewrite `src/lbb/core/fulfillment.py`**

```python
"""Domain types for the order-fulfillment workflow.

Orders come from the live engraving API (read-only). A product has coins;
each coin has Front/Back engraving PDFs. Each engraving PDF is one LightBurn
job, identified by its signed-URL file key. Mutable progress (which keys are
engraved) lives in the FulfillmentStateStore, never on these frozen types.
Status is owned by the API (3 canonical values).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

_TYPE_ORDER = ("Bracelet", "Necklace", "Keychain", "Flask", "MiniFlask", "Lighter")
_UNKNOWN_TYPE_RANK = len(_TYPE_ORDER) + 1
_TYPE_NORMALIZE = {
    "bracelet": "Bracelet", "necklace": "Necklace", "keychain": "Keychain",
    "flask": "Flask", "mini_flask": "MiniFlask", "lighter": "Lighter",
}


class OrderStatus(StrEnum):
    NOT_DONE = "not_done_yet"
    DONE = "graviert_verschickt"
    REVISION = "revision"


def normalize_type(raw: str) -> str:
    """API product type ('bracelet', 'mini_flask') → display ('Bracelet', 'MiniFlask')."""
    key = (raw or "").strip().lower()
    if key in _TYPE_NORMALIZE:
        return _TYPE_NORMALIZE[key]
    return key.replace("_", " ").title().replace(" ", "") if key else "Unknown"


@dataclass(frozen=True, slots=True)
class Side:
    name: str       # "Front" | "Back" | "Coin 2 Front" ...
    file_key: str   # signed_urls key for this engraving PDF (one LightBurn job)


@dataclass(frozen=True, slots=True)
class Product:
    product_type: str            # normalized (title case)
    band_color: str = ""         # color_band_chain
    coin_color: str = ""         # color_coin_plate
    sides: tuple[Side, ...] = ()
    qty: int = 1
    image_key: str = ""
    multiple_coins: bool = False
    special_length: bool = False
    length: str = ""


@dataclass(frozen=True, slots=True)
class FulfillmentOrder:
    order_id: str                 # API uuid — required to write status back
    order_number: str
    products: tuple[Product, ...]
    amount: int = 0
    status: OrderStatus = OrderStatus.NOT_DONE
    instruction: str = ""         # API `comment` — read-only note from Flanacom
    amazon_url: str = ""          # link_to_order
    label_key: str = ""           # shipping_label_path (signed_urls key)
    placed_at: datetime | None = None
    channel: str = "Amazon · DE"

    @property
    def gift_box(self) -> bool:
        return "gift" in self.instruction.lower()


def all_sides(order: FulfillmentOrder) -> set[str]:
    """Every engraving file key in the order."""
    return {s.file_key for p in order.products for s in p.sides if s.file_key}


def type_rank(product_type: str) -> int:
    """Position in the workshop queue; unknown types sort last."""
    try:
        return _TYPE_ORDER.index(product_type)
    except ValueError:
        return _UNKNOWN_TYPE_RANK


def queue_sort_key(order: FulfillmentOrder) -> tuple[int, str]:
    """Group by product-type rank (first product), then oldest placed first."""
    primary = order.products[0].product_type if order.products else "Other"
    placed = order.placed_at.isoformat() if order.placed_at else ""
    return (type_rank(primary), placed)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/unit/core/test_fulfillment.py -q`
Expected: PASS (7 tests). NOTE: this breaks importers (service, json adapter) — those are fixed in later tasks; do not fix them here.

- [ ] **Step 5: Commit**

```bash
git add src/lbb/core/fulfillment.py tests/unit/core/test_fulfillment.py
git commit -m "feat(core): remap domain to live API — 3 statuses, file-key sides, order_id"
```

---

### Task 2: Thread-safe state store keyed by file-key

**Files:**
- Modify: `src/lbb/adapters/state_migrations.py`
- Modify: `src/lbb/ports/fulfillment.py`
- Modify: `src/lbb/adapters/sqlite_state.py`
- Test: `tests/unit/adapters/test_sqlite_state.py` (rewrite)

- [ ] **Step 1: Write the failing tests**

Replace `tests/unit/adapters/test_sqlite_state.py` with:

```python
import threading

from lbb.adapters.sqlite_state import SqliteStateStore


def test_mark_and_read_engraved_keys(tmp_path):
    s = SqliteStateStore(tmp_path / "state.sqlite")
    assert s.engraved_keys("306-1") == set()
    s.mark_engraved("306-1", "engraving/a Front.pdf", True)
    s.mark_engraved("306-1", "engraving/a Back.pdf", True)
    assert s.engraved_keys("306-1") == {"engraving/a Front.pdf", "engraving/a Back.pdf"}


def test_unmark_removes_key(tmp_path):
    s = SqliteStateStore(tmp_path / "state.sqlite")
    s.mark_engraved("306-1", "k1", True)
    s.mark_engraved("306-1", "k1", False)
    assert s.engraved_keys("306-1") == set()


def test_mark_is_idempotent(tmp_path):
    s = SqliteStateStore(tmp_path / "state.sqlite")
    s.mark_engraved("306-1", "k1", True)
    s.mark_engraved("306-1", "k1", True)
    assert s.engraved_keys("306-1") == {"k1"}


def test_survives_reopen(tmp_path):
    db = tmp_path / "state.sqlite"
    SqliteStateStore(db).mark_engraved("306-1", "k1", True)
    assert SqliteStateStore(db).engraved_keys("306-1") == {"k1"}


def test_usable_from_another_thread(tmp_path):
    """pywebview dispatches bridge calls on a worker thread; the connection is
    created on the main thread. This must not raise ProgrammingError."""
    s = SqliteStateStore(tmp_path / "state.sqlite")
    errors = []

    def worker():
        try:
            s.mark_engraved("306-1", "k1", True)
            s.engraved_keys("306-1")
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    assert errors == [], errors
    assert s.engraved_keys("306-1") == {"k1"}
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/unit/adapters/test_sqlite_state.py -q`
Expected: FAIL (`engraved_keys`/`mark_engraved` not defined).

- [ ] **Step 3: Replace `src/lbb/adapters/state_migrations.py`**

```python
STATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS engraved_keys (
  order_number TEXT NOT NULL,
  file_key     TEXT NOT NULL,
  engraved_at  TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (order_number, file_key)
);
"""
```

- [ ] **Step 4: Replace `src/lbb/ports/fulfillment.py`**

```python
from __future__ import annotations

from typing import Protocol


class FulfillmentStateStore(Protocol):
    def engraved_keys(self, order_number: str) -> set[str]: ...
    def mark_engraved(self, order_number: str, file_key: str, engraved: bool) -> None: ...
```

- [ ] **Step 5: Replace `src/lbb/adapters/sqlite_state.py`**

```python
"""SQLite-backed FulfillmentStateStore — local operator progress.

Tracks which engraving file-keys an operator has sent to LightBurn. Opened
with check_same_thread=False and guarded by a lock because pywebview invokes
bridge methods on a worker thread while this connection is created on the main
thread.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from lbb.adapters.state_migrations import STATE_SCHEMA
from lbb.ports.fulfillment import FulfillmentStateStore


class SqliteStateStore(FulfillmentStateStore):
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock, self._conn:
            self._conn.executescript(STATE_SCHEMA)

    def engraved_keys(self, order_number: str) -> set[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT file_key FROM engraved_keys WHERE order_number = ?",
                (order_number,),
            ).fetchall()
        return {r["file_key"] for r in rows}

    def mark_engraved(self, order_number: str, file_key: str, engraved: bool) -> None:
        with self._lock, self._conn:
            if engraved:
                self._conn.execute(
                    """INSERT INTO engraved_keys (order_number, file_key)
                       VALUES (?, ?)
                       ON CONFLICT(order_number, file_key) DO NOTHING""",
                    (order_number, file_key),
                )
            else:
                self._conn.execute(
                    "DELETE FROM engraved_keys WHERE order_number = ? AND file_key = ?",
                    (order_number, file_key),
                )
```

- [ ] **Step 6: Run to verify it passes**

Run: `uv run pytest tests/unit/adapters/test_sqlite_state.py -q`
Expected: PASS (5 tests).

- [ ] **Step 7: Commit**

```bash
git add src/lbb/adapters/state_migrations.py src/lbb/ports/fulfillment.py src/lbb/adapters/sqlite_state.py tests/unit/adapters/test_sqlite_state.py
git commit -m "fix(state): file-key progress + thread-safe SQLite (check_same_thread + lock)"
```

---

### Task 3: HttpTransport port + stdlib urllib adapter

**Files:**
- Create: `src/lbb/ports/engraving.py`
- Create: `src/lbb/adapters/http_urllib.py`
- Test: `tests/unit/adapters/test_http_urllib.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/adapters/test_http_urllib.py`:

```python
from lbb.adapters.http_urllib import UrllibTransport


class _FakeOpener:
    def __init__(self):
        self.captured = None

    def open(self, req, timeout=None):  # mimic urllib.request.urlopen
        self.captured = req

        class _Resp:
            status = 200

            def read(self_inner):
                return b'{"ok": true}'

            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

        return _Resp()


def test_request_sets_method_headers_body():
    fake = _FakeOpener()
    t = UrllibTransport(opener=fake.open)
    code, body = t.request(
        "POST", "https://x/api",
        headers={"x-api-key": "secret", "Content-Type": "application/json"},
        body=b'{"a":1}',
    )
    assert code == 200
    assert body == b'{"ok": true}'
    req = fake.captured
    assert req.get_method() == "POST"
    assert req.data == b'{"a":1}'
    assert req.get_header("X-api-key") == "secret"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/unit/adapters/test_http_urllib.py -q`
Expected: FAIL (module not found).

- [ ] **Step 3: Create `src/lbb/ports/engraving.py`**

```python
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from lbb.core.errors import LbbError
from lbb.core.fulfillment import FulfillmentOrder, OrderStatus


class EngravingApiError(LbbError):
    """Any failure talking to the engraving API (network, 4xx, parse)."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class HttpTransport(Protocol):
    def request(
        self, method: str, url: str, *, headers: dict[str, str], body: bytes | None = None
    ) -> tuple[int, bytes]: ...


class EngravingGateway(Protocol):
    def list_orders(self) -> list[FulfillmentOrder]: ...
    def get(self, order_number: str) -> FulfillmentOrder | None: ...
    def download_file(self, order_id: str, file_key: str, dest_dir: Path) -> Path: ...
    def set_status(self, order_id: str, status: OrderStatus) -> None: ...
```

- [ ] **Step 4: Create `src/lbb/adapters/http_urllib.py`**

```python
"""HttpTransport over stdlib urllib — no third-party HTTP dependency, so the
PyInstaller bundle stays small and import-clean. Injectable opener keeps it
unit-testable without network."""

from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Callable

from lbb.ports.engraving import EngravingApiError, HttpTransport

_TIMEOUT = 20.0


class UrllibTransport(HttpTransport):
    def __init__(self, *, opener: Callable | None = None, timeout: float = _TIMEOUT):
        self._open = opener or urllib.request.urlopen
        self._timeout = timeout

    def request(self, method, url, *, headers, body=None):
        req = urllib.request.Request(url, data=body, method=method)
        for k, v in headers.items():
            req.add_header(k, v)
        try:
            with self._open(req, timeout=self._timeout) as resp:
                return getattr(resp, "status", 200), resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            raise EngravingApiError(f"Network error: {e}") from e
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/unit/adapters/test_http_urllib.py -q`
Expected: PASS (1 test).

- [ ] **Step 6: Commit**

```bash
git add src/lbb/ports/engraving.py src/lbb/adapters/http_urllib.py tests/unit/adapters/test_http_urllib.py
git commit -m "feat(http): HttpTransport port + stdlib urllib adapter + EngravingGateway port"
```

---

### Task 4: EngravingApiClient (GET parse, filter, download, status write)

**Files:**
- Create: `src/lbb/adapters/engraving_api.py`
- Test: `tests/unit/adapters/test_engraving_api.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/adapters/test_engraving_api.py`:

```python
import json

import pytest

from lbb.adapters.engraving_api import EngravingApiClient
from lbb.core.fulfillment import OrderStatus
from lbb.ports.engraving import EngravingApiError

BASE = "https://api.test/engraving-api"

ORDER = {
    "id": "uuid-1",
    "order_number": "306-0804157-6173963",
    "link_to_order": "https://sellercentral/x",
    "order_date": "2026-06-15",
    "amount": 1,
    "status": "not_done_yet",
    "comment": "With Gift Box each",
    "shipping_label_path": "shipping_label/x.pdf",
    "created_at": "2026-06-16T14:53:45+02:00",
    "updated_at": "2026-06-22T11:31:45+02:00",
    "products": [
        {
            "type": "bracelet",
            "color_band_chain": "Retro",
            "color_coin_plate": "Silver",
            "multiple_coins": False,
            "special_length": False,
            "length": None,
            "image": "product_picture/x.png",
            "coins": [{"front": "engraving/x Front.pdf", "back": "engraving/x Back.pdf"}],
        }
    ],
    "signed_urls": {
        "shipping_label/x.pdf": "https://dl/label?token=1",
        "engraving/x Front.pdf": "https://dl/front?token=1",
        "engraving/x Back.pdf": "https://dl/back?token=1",
    },
}


class FakeTransport:
    """Programmable transport. `routes` maps (method, url-substring) -> (code, bytes).
    Records every call. File downloads return raw bytes for any URL with /dl/."""

    def __init__(self, orders, *, post_code=200):
        self.orders = orders
        self.post_code = post_code
        self.calls = []
        self.get_count = 0

    def request(self, method, url, *, headers, body=None):
        self.calls.append((method, url, headers, body))
        if "/dl/" in url:
            return 200, b"%PDF-1.4 fake"
        if method == "GET":
            self.get_count += 1
            return 200, json.dumps({"orders": self.orders}).encode()
        if method == "POST":
            payload = json.loads(body)
            return self.post_code, json.dumps(
                {"ok": True, "order": {"id": payload["order_id"],
                                       "status": payload["status"]}}
            ).encode()
        return 404, b"{}"


def _client(transport, **kw):
    return EngravingApiClient(BASE, "secret-key", transport, **kw)


def test_list_orders_parses_domain():
    t = FakeTransport([ORDER])
    [o] = _client(t).list_orders()
    assert o.order_id == "uuid-1"
    assert o.order_number == "306-0804157-6173963"
    assert o.amount == 1
    assert o.status is OrderStatus.NOT_DONE
    assert o.gift_box is True
    assert o.amazon_url == "https://sellercentral/x"
    assert o.label_key == "shipping_label/x.pdf"
    assert o.placed_at.year == 2026
    [p] = o.products
    assert p.product_type == "Bracelet"
    assert p.band_color == "Retro" and p.coin_color == "Silver"
    assert [s.file_key for s in p.sides] == ["engraving/x Front.pdf", "engraving/x Back.pdf"]
    assert [s.name for s in p.sides] == ["Front", "Back"]


def test_get_sends_api_key_header():
    t = FakeTransport([ORDER])
    _client(t).list_orders()
    method, url, headers, _ = t.calls[0]
    assert method == "GET"
    assert headers["x-api-key"] == "secret-key"


def test_multiple_coins_names_are_prefixed():
    raw = json.loads(json.dumps(ORDER))
    raw["products"][0]["coins"] = [
        {"front": "f1", "back": "b1"},
        {"front": "f2", "back": "b2"},
    ]
    t = FakeTransport([raw])
    [o] = _client(t).list_orders()
    assert [s.name for s in o.products[0].sides] == [
        "Coin 1 Front", "Coin 1 Back", "Coin 2 Front", "Coin 2 Back",
    ]


def test_get_returns_cached_order_by_number():
    t = FakeTransport([ORDER])
    c = _client(t)
    c.list_orders()
    assert c.get("306-0804157-6173963").order_id == "uuid-1"
    assert c.get("nope") is None


def test_download_file_writes_bytes(tmp_path):
    t = FakeTransport([ORDER])
    c = _client(t)
    c.list_orders()
    p = c.download_file("uuid-1", "engraving/x Front.pdf", tmp_path)
    assert p.is_file()
    assert p.read_bytes().startswith(b"%PDF")


def test_download_refetches_when_stale(tmp_path):
    clock = [1000.0]
    t = FakeTransport([ORDER])
    c = _client(t, now=lambda: clock[0])
    c.list_orders()                 # get_count == 1
    clock[0] += 60 * 60             # 1 hour later -> stale
    c.download_file("uuid-1", "engraving/x Front.pdf", tmp_path)
    assert t.get_count == 2          # re-GET happened for a fresh signed URL


def test_set_status_posts_body():
    t = FakeTransport([ORDER])
    _client(t).set_status("uuid-1", OrderStatus.DONE)
    post = [c for c in t.calls if c[0] == "POST"][-1]
    body = json.loads(post[3])
    assert body == {"order_id": "uuid-1", "status": "graviert_verschickt"}
    assert post[2]["Content-Type"] == "application/json"


def test_set_status_raises_on_404():
    t = FakeTransport([ORDER], post_code=404)
    with pytest.raises(EngravingApiError) as ei:
        _client(t).set_status("ghost", OrderStatus.DONE)
    assert ei.value.status_code == 404


def test_list_orders_raises_on_401():
    class Unauth:
        def request(self, *a, **k):
            return 401, b'{"error":"unauthorized"}'
    with pytest.raises(EngravingApiError) as ei:
        _client(Unauth()).list_orders()
    assert ei.value.status_code == 401
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/unit/adapters/test_engraving_api.py -q`
Expected: FAIL (module not found).

- [ ] **Step 3: Create `src/lbb/adapters/engraving_api.py`**

```python
"""EngravingApiClient — live Supabase engraving-api gateway.

GET parses orders into domain types and caches each order's signed_urls (with a
fetch timestamp). download_file guarantees a non-expired link (re-GET if stale
or key missing) before streaming the file to disk — this is the single place
"fetch fresh at processing time" is enforced. set_status POSTs only the status.
All HTTP goes through an injected HttpTransport, so behavior is unit-tested with
no network.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from lbb.core.fulfillment import (
    FulfillmentOrder,
    OrderStatus,
    Product,
    Side,
    normalize_type,
)
from lbb.ports.engraving import EngravingApiError, EngravingGateway, HttpTransport

# Re-GET if the cached signed URLs are older than this (links live 1h; refresh early).
_STALE_AFTER = 50 * 60.0


class EngravingApiClient(EngravingGateway):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        transport: HttpTransport,
        *,
        now: Callable[[], float] = time.monotonic,
    ):
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._http = transport
        self._now = now
        self._orders: dict[str, FulfillmentOrder] = {}     # by order_number
        self._signed: dict[str, dict[str, str]] = {}        # order_id -> {key: url}
        self._fetched_at: float | None = None

    # ── reads ──────────────────────────────────────────────────────────────
    def list_orders(self) -> list[FulfillmentOrder]:
        self._fetch()
        return list(self._orders.values())

    def get(self, order_number: str) -> FulfillmentOrder | None:
        if self._fetched_at is None:
            self._fetch()
        return self._orders.get(order_number)

    def download_file(self, order_id: str, file_key: str, dest_dir: Path) -> Path:
        url = self._fresh_url(order_id, file_key)
        code, data = self._http.request("GET", url, headers={})
        if code != 200:
            raise EngravingApiError(
                f"Download failed ({code}) for {file_key}", status_code=code
            )
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / _safe_name(file_key)
        dest.write_bytes(data)
        return dest

    def set_status(self, order_id: str, status: OrderStatus) -> None:
        body = json.dumps({"order_id": order_id, "status": str(status)}).encode()
        code, data = self._http.request(
            "POST", self._base,
            headers={"x-api-key": self._key, "Content-Type": "application/json"},
            body=body,
        )
        if code != 200:
            raise EngravingApiError(
                f"Status update failed ({code})", status_code=code
            )

    # ── internals ──────────────────────────────────────────────────────────
    def _fetch(self) -> None:
        code, data = self._http.request(
            "GET", self._base, headers={"x-api-key": self._key}
        )
        if code != 200:
            raise EngravingApiError(
                f"Could not load orders ({code})", status_code=code
            )
        try:
            payload = json.loads(data)
        except json.JSONDecodeError as e:
            raise EngravingApiError("Malformed response from engraving API") from e
        orders: dict[str, FulfillmentOrder] = {}
        signed: dict[str, dict[str, str]] = {}
        for raw in payload.get("orders") or []:
            order = _parse_order(raw)
            orders[order.order_number] = order
            signed[order.order_id] = dict(raw.get("signed_urls") or {})
        self._orders, self._signed = orders, signed
        self._fetched_at = self._now()

    def _fresh_url(self, order_id: str, file_key: str) -> str:
        stale = (
            self._fetched_at is None
            or (self._now() - self._fetched_at) >= _STALE_AFTER
            or file_key not in self._signed.get(order_id, {})
        )
        if stale:
            self._fetch()
        url = self._signed.get(order_id, {}).get(file_key)
        if not url:
            raise EngravingApiError(f"No download URL for {file_key}")
        return url


def _safe_name(file_key: str) -> str:
    name = file_key.replace("\\", "/").split("/")[-1] or "download"
    return re.sub(r"[^A-Za-z0-9._ -]", "_", name)


def _parse_order(raw: dict) -> FulfillmentOrder:
    products = tuple(_parse_product(p) for p in (raw.get("products") or []))
    return FulfillmentOrder(
        order_id=str(raw["id"]),
        order_number=str(raw.get("order_number", "")),
        products=products,
        amount=int(raw.get("amount") or 0),
        status=_parse_status(raw.get("status")),
        instruction=str(raw.get("comment") or ""),
        amazon_url=str(raw.get("link_to_order") or ""),
        label_key=str(raw.get("shipping_label_path") or ""),
        placed_at=_parse_date(raw.get("order_date")),
    )


def _parse_product(raw: dict) -> Product:
    coins = raw.get("coins") or []
    multi = len(coins) > 1
    sides: list[Side] = []
    for i, coin in enumerate(coins, start=1):
        prefix = f"Coin {i} " if multi else ""
        front, back = coin.get("front"), coin.get("back")
        if front:
            sides.append(Side(f"{prefix}Front", str(front)))
        if back:
            sides.append(Side(f"{prefix}Back", str(back)))
    return Product(
        product_type=normalize_type(str(raw.get("type") or "")),
        band_color=str(raw.get("color_band_chain") or ""),
        coin_color=str(raw.get("color_coin_plate") or ""),
        sides=tuple(sides),
        image_key=str(raw.get("image") or ""),
        multiple_coins=bool(raw.get("multiple_coins")),
        special_length=bool(raw.get("special_length")),
        length=str(raw.get("length") or ""),
    )


def _parse_status(raw) -> OrderStatus:
    try:
        return OrderStatus(str(raw))
    except ValueError:
        return OrderStatus.NOT_DONE


def _parse_date(raw) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/unit/adapters/test_engraving_api.py -q`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add src/lbb/adapters/engraving_api.py tests/unit/adapters/test_engraving_api.py
git commit -m "feat(adapter): EngravingApiClient — GET parse, fresh signed-URL download, status POST"
```

---

### Task 5: Config loader (env → git-ignored file)

**Files:**
- Create: `src/lbb/adapters/config.py`
- Create: `config.example.json`
- Modify: `.gitignore`
- Test: `tests/unit/adapters/test_config.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/adapters/test_config.py`:

```python
import json

from lbb.adapters.config import DEFAULT_BASE_URL, load_config


def test_env_key_takes_precedence(tmp_path):
    cfg = load_config(env={"FLANACOM_API_KEY": "envkey"}, config_path=tmp_path / "c.json")
    assert cfg.api_key == "envkey"
    assert cfg.base_url == DEFAULT_BASE_URL


def test_env_can_override_base_url(tmp_path):
    cfg = load_config(
        env={"FLANACOM_API_KEY": "k", "FLANACOM_API_URL": "https://other/api"},
        config_path=tmp_path / "c.json",
    )
    assert cfg.base_url == "https://other/api"


def test_falls_back_to_config_file(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"api_key": "filekey", "api_base_url": "https://file/api"}))
    cfg = load_config(env={}, config_path=p)
    assert cfg.api_key == "filekey"
    assert cfg.base_url == "https://file/api"


def test_returns_none_when_no_key(tmp_path):
    assert load_config(env={}, config_path=tmp_path / "missing.json") is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/unit/adapters/test_config.py -q`
Expected: FAIL (module not found).

- [ ] **Step 3: Create `src/lbb/adapters/config.py`**

```python
"""Load the engraving-API credentials Python-side. The secret key is read from
the FLANACOM_API_KEY env var, else a git-ignored config file. It is NEVER
embedded in the JS frontend or committed to the repo. The base URL is public."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

DEFAULT_BASE_URL = "https://puscgcazmnqxazietgvy.supabase.co/functions/v1/engraving-api"


@dataclass(frozen=True, slots=True)
class ApiConfig:
    base_url: str
    api_key: str


def load_config(
    *, env: Mapping[str, str] | None = None, config_path: Path
) -> ApiConfig | None:
    env = os.environ if env is None else env
    key = env.get("FLANACOM_API_KEY")
    if key:
        return ApiConfig(env.get("FLANACOM_API_URL", DEFAULT_BASE_URL), key)
    path = Path(config_path)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if data.get("api_key"):
            return ApiConfig(data.get("api_base_url", DEFAULT_BASE_URL), data["api_key"])
    return None
```

- [ ] **Step 4: Create `config.example.json`** (repo root)

```json
{
  "api_base_url": "https://puscgcazmnqxazietgvy.supabase.co/functions/v1/engraving-api",
  "api_key": "PASTE-YOUR-X-API-KEY-HERE"
}
```

- [ ] **Step 5: Append to `.gitignore`**

Add these lines:

```
# Local runtime secrets — never commit the real key
config.json
.flanacom-tool/
```

- [ ] **Step 6: Run to verify it passes**

Run: `uv run pytest tests/unit/adapters/test_config.py -q`
Expected: PASS (4 tests).

- [ ] **Step 7: Commit**

```bash
git add src/lbb/adapters/config.py config.example.json .gitignore tests/unit/adapters/test_config.py
git commit -m "feat(config): load API credentials from env or git-ignored file"
```

---

### Task 6: Rewire FulfillmentService to the gateway

**Files:**
- Modify: `src/lbb/app/fulfillment_service.py` (rewrite)
- Test: `tests/integration/test_fulfillment_service.py` (rewrite)

- [ ] **Step 1: Write the failing tests**

Replace `tests/integration/test_fulfillment_service.py` with:

```python
from datetime import datetime
from pathlib import Path

from lbb.app.fulfillment_service import FulfillmentService
from lbb.core.fulfillment import FulfillmentOrder, OrderStatus, Product, Side


def _order(status=OrderStatus.NOT_DONE):
    return FulfillmentOrder(
        order_id="uuid-1",
        order_number="306-1",
        amount=1,
        status=status,
        instruction="With Gift Box each",
        amazon_url="https://sc/x",
        label_key="shipping_label/x.pdf",
        placed_at=datetime(2026, 6, 15),
        products=(
            Product(
                product_type="Bracelet", band_color="Retro", coin_color="Silver",
                sides=(Side("Front", "engraving/x Front.pdf"),
                       Side("Back", "engraving/x Back.pdf")),
            ),
        ),
    )


class FakeGateway:
    def __init__(self, orders):
        self._orders = {o.order_number: o for o in orders}
        self.posted = []
        self.downloads = []

    def list_orders(self):
        return list(self._orders.values())

    def get(self, n):
        return self._orders.get(n)

    def download_file(self, order_id, file_key, dest_dir):
        self.downloads.append((order_id, file_key))
        p = Path(dest_dir) / "job.pdf"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"%PDF fake")
        return p

    def set_status(self, order_id, status):
        self.posted.append((order_id, status))


class FakeLightBurn:
    def __init__(self):
        self.loaded = []

    def is_running(self):
        return True

    def load_file(self, path):
        self.loaded.append(path)


class MemState:
    def __init__(self):
        self._k = {}

    def engraved_keys(self, n):
        return set(self._k.get(n, set()))

    def mark_engraved(self, n, key, engraved):
        s = self._k.setdefault(n, set())
        s.add(key) if engraved else s.discard(key)


def _svc(gw=None, tmp=Path(".")):
    gw = gw or FakeGateway([_order()])
    return FulfillmentService(gateway=gw, state=MemState(),
                              lightburn=FakeLightBurn(), cache_dir=tmp), gw


def test_list_orders_shapes_cards(tmp_path):
    svc, _ = _svc(tmp=tmp_path)
    res = svc.list_orders()
    assert res["error"] is None
    [card] = res["orders"]
    assert card["order_number"] == "306-1"
    assert card["status"] == "not_done_yet"
    assert card["gift_box"] is True
    assert card["progress"] == {"done": 0, "total": 2}


def test_engrave_downloads_then_opens_lightburn(tmp_path):
    gw = FakeGateway([_order()])
    svc = FulfillmentService(gateway=gw, state=MemState(),
                             lightburn=(lb := FakeLightBurn()), cache_dir=tmp_path)
    res = svc.engrave_side("306-1", "engraving/x Front.pdf")
    assert res["ok"] is True
    assert gw.downloads == [("uuid-1", "engraving/x Front.pdf")]
    assert lb.loaded and str(lb.loaded[0]).endswith("job.pdf")
    assert res["progress"] == {"done": 1, "total": 2}


def test_engrave_rejects_unknown_key(tmp_path):
    svc, _ = _svc(tmp=tmp_path)
    res = svc.engrave_side("306-1", "nope.pdf")
    assert res["ok"] is False


def test_ship_requires_all_engraved_then_posts_done(tmp_path):
    gw = FakeGateway([_order()])
    svc = FulfillmentService(gateway=gw, state=MemState(),
                             lightburn=FakeLightBurn(), cache_dir=tmp_path)
    assert svc.ship_order("306-1")["ok"] is False           # nothing engraved yet
    svc.engrave_side("306-1", "engraving/x Front.pdf")
    svc.engrave_side("306-1", "engraving/x Back.pdf")
    res = svc.ship_order("306-1")
    assert res["ok"] is True
    assert gw.posted == [("uuid-1", OrderStatus.DONE)]


def test_flag_revision_posts_revision(tmp_path):
    gw = FakeGateway([_order()])
    svc = FulfillmentService(gateway=gw, state=MemState(),
                             lightburn=FakeLightBurn(), cache_dir=tmp_path)
    assert svc.flag_revision("306-1")["ok"] is True
    assert gw.posted == [("uuid-1", OrderStatus.REVISION)]


def test_get_order_marks_engraved_sides(tmp_path):
    gw = FakeGateway([_order()])
    svc = FulfillmentService(gateway=gw, state=MemState(),
                             lightburn=FakeLightBurn(), cache_dir=tmp_path)
    svc.engrave_side("306-1", "engraving/x Front.pdf")
    detail = svc.get_order("306-1")
    sides = detail["products"][0]["sides"]
    assert sides[0] == {"name": "Front", "file_key": "engraving/x Front.pdf", "engraved": True}
    assert sides[1]["engraved"] is False
    assert detail["instruction"] == "With Gift Box each"


def test_list_orders_reports_gateway_error(tmp_path):
    class Boom:
        def list_orders(self):
            from lbb.ports.engraving import EngravingApiError
            raise EngravingApiError("API key rejected", status_code=401)
    svc = FulfillmentService(gateway=Boom(), state=MemState(),
                             lightburn=FakeLightBurn(), cache_dir=tmp_path)
    res = svc.list_orders()
    assert res["orders"] == []
    assert "rejected" in res["error"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/integration/test_fulfillment_service.py -q`
Expected: FAIL (constructor/method signatures differ).

- [ ] **Step 3: Rewrite `src/lbb/app/fulfillment_service.py`**

```python
"""FulfillmentService — the order-fulfillment brain.

Reads orders from the live EngravingGateway, merges local engraving progress
(FulfillmentStateStore), downloads each engraving PDF fresh and opens it in
LightBurn, and writes the 3 canonical statuses back. Returns JSON-serialisable
view models for the web bridge. Knows nothing about pywebview or HTTP.
"""

from __future__ import annotations

from pathlib import Path

from lbb.core.errors import LbbError
from lbb.core.fulfillment import (
    FulfillmentOrder,
    OrderStatus,
    all_sides,
    queue_sort_key,
)
from lbb.ports.engraving import EngravingApiError, EngravingGateway
from lbb.ports.fulfillment import FulfillmentStateStore
from lbb.ports.lightburn import LightBurnPort

_BUCKETS = {"Bracelet": "Bracelets", "Necklace": "Necklaces", "Keychain": "Keychains",
            "Flask": "Flasks", "MiniFlask": "Mini flasks", "Lighter": "Lighters"}


def _placed_label(o: FulfillmentOrder) -> str:
    if not o.placed_at:
        return ""
    return f"{o.placed_at:%b} {o.placed_at.day}, {o.placed_at:%Y}"


class FulfillmentService:
    def __init__(
        self,
        *,
        gateway: EngravingGateway,
        state: FulfillmentStateStore,
        lightburn: LightBurnPort,
        cache_dir: Path,
    ):
        self.gateway = gateway
        self.state = state
        self.lightburn = lightburn
        self.cache_dir = Path(cache_dir)

    # ── queries ───────────────────────────────────────────────────────────
    def list_orders(self, *, filter: str = "all", query: str = "") -> dict:  # noqa: A002
        try:
            orders = sorted(self.gateway.list_orders(), key=queue_sort_key)
        except EngravingApiError as e:
            return {"orders": [], "error": str(e)}
        q = (query or "").lower().replace(" ", "")
        out: list[dict] = []
        for o in orders:
            if filter == "open" and o.status is OrderStatus.DONE:
                continue
            if filter == "done" and o.status is not OrderStatus.DONE:
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
                "placed_label": _placed_label(o),
                "status": str(o.status),
                "gift_box": o.gift_box,
                "progress": {"done": done, "total": total},
            })
        return {"orders": out, "error": None}

    def get_order(self, order_number: str) -> dict | None:
        o = self.gateway.get(order_number)
        if o is None:
            return None
        engraved = self.state.engraved_keys(order_number)
        done, total = self._progress(o)
        return {
            "order_number": o.order_number,
            "amount": o.amount,
            "channel": o.channel,
            "amazon_url": o.amazon_url,
            "gift_box": o.gift_box,
            "instruction": o.instruction,
            "placed_label": _placed_label(o),
            "has_label": bool(o.label_key),
            "status": str(o.status),
            "progress": {"done": done, "total": total},
            "products": [
                {
                    "product_type": p.product_type,
                    "name": p.product_type,
                    "color": p.coin_color,
                    "band_color": p.band_color,
                    "qty": p.qty,
                    "image_key": p.image_key,
                    "sides": [
                        {"name": s.name, "file_key": s.file_key,
                         "engraved": s.file_key in engraved}
                        for s in p.sides
                    ],
                }
                for p in o.products
            ],
        }

    def lightburn_status(self) -> dict:
        return {"running": self.lightburn.is_running()}

    def label_file(self, order_number: str) -> Path | None:
        o = self.gateway.get(order_number)
        if not o or not o.label_key:
            return None
        try:
            return self.gateway.download_file(o.order_id, o.label_key, self._dir(o))
        except EngravingApiError:
            return None

    # ── commands ──────────────────────────────────────────────────────────
    def engrave_side(self, order_number: str, file_key: str) -> dict:
        o = self.gateway.get(order_number)
        if o is None:
            return {"ok": False, "error": "Order not found"}
        if file_key not in all_sides(o):
            return {"ok": False, "error": "Unknown engraving file"}
        try:
            pdf = self.gateway.download_file(o.order_id, file_key, self._dir(o))
            self.lightburn.load_file(pdf)
        except (EngravingApiError, LbbError) as e:
            return {"ok": False, "error": str(e)}
        self.state.mark_engraved(order_number, file_key, True)
        done, total = self._progress(o)
        return {"ok": True, "status": str(o.status),
                "progress": {"done": done, "total": total}}

    def ship_order(self, order_number: str) -> dict:
        o = self.gateway.get(order_number)
        if o is None:
            return {"ok": False, "error": "Order not found"}
        done, total = self._progress(o)
        if done != total or total == 0:
            return {"ok": False, "error": "Engrave all sides first"}
        try:
            self.gateway.set_status(o.order_id, OrderStatus.DONE)
        except EngravingApiError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "status": str(OrderStatus.DONE)}

    def flag_revision(self, order_number: str) -> dict:
        return self._write_status(order_number, OrderStatus.REVISION)

    def set_status(self, order_number: str, status: str) -> dict:
        if status == OrderStatus.DONE:
            return self.ship_order(order_number)
        try:
            target = OrderStatus(status)
        except ValueError:
            return {"ok": False, "error": f"Unknown status: {status}"}
        return self._write_status(order_number, target)

    # ── helpers ───────────────────────────────────────────────────────────
    def _write_status(self, order_number: str, status: OrderStatus) -> dict:
        o = self.gateway.get(order_number)
        if o is None:
            return {"ok": False, "error": "Order not found"}
        try:
            self.gateway.set_status(o.order_id, status)
        except EngravingApiError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "status": str(status)}

    def _progress(self, o: FulfillmentOrder) -> tuple[int, int]:
        total = all_sides(o)
        done = self.state.engraved_keys(o.order_number) & total
        return (len(done), len(total))

    def _dir(self, o: FulfillmentOrder) -> Path:
        return self.cache_dir / o.order_number

    @staticmethod
    def _summary(o: FulfillmentOrder) -> str:
        if not o.products:
            return ""
        head = o.products[0].product_type
        n = len(o.products)
        return head if n == 1 else f"{head} +{n - 1}"
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/integration/test_fulfillment_service.py -q`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add src/lbb/app/fulfillment_service.py tests/integration/test_fulfillment_service.py
git commit -m "feat(service): drive engraving gateway — download→LightBurn, 3-status writes"
```

---

### Task 7: Rewire the JS bridge

**Files:**
- Modify: `src/lbb/web/bridge.py` (rewrite)
- Test: `tests/web/test_bridge.py` (rewrite)

- [ ] **Step 1: Write the failing tests**

Replace `tests/web/test_bridge.py` with:

```python
from lbb.web.bridge import JsApiBridge


class FakeService:
    def __init__(self):
        self.calls = []

    def list_orders(self, *, filter="all", query=""):
        self.calls.append(("list", filter, query))
        return {"orders": [], "error": None}

    def get_order(self, n):
        self.calls.append(("get", n))
        return {"order_number": n}

    def engrave_side(self, n, file_key):
        self.calls.append(("engrave", n, file_key))
        return {"ok": True}

    def ship_order(self, n):
        self.calls.append(("ship", n))
        return {"ok": True}

    def set_status(self, n, status):
        self.calls.append(("status", n, status))
        return {"ok": True}

    def flag_revision(self, n):
        self.calls.append(("revision", n))
        return {"ok": True}

    def lightburn_status(self):
        return {"running": True}

    def label_file(self, n):
        return None


def test_bridge_delegates_queries_and_commands():
    svc = FakeService()
    b = JsApiBridge(svc)
    assert b.list_orders("open", "306") == {"orders": [], "error": None}
    assert b.get_order("306-1") == {"order_number": "306-1"}
    assert b.engrave_side("306-1", "engraving/x Front.pdf") == {"ok": True}
    assert b.ship_order("306-1") == {"ok": True}
    assert b.set_status("306-1", "revision") == {"ok": True}
    assert b.flag_revision("306-1") == {"ok": True}
    assert b.lightburn_status() == {"running": True}
    assert ("engrave", "306-1", "engraving/x Front.pdf") in svc.calls


def test_open_label_when_missing_returns_error():
    b = JsApiBridge(FakeService())
    assert b.open_label("306-1") == {"ok": False, "error": "No label file"}
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/web/test_bridge.py -q`
Expected: FAIL (`flag_revision`/`engrave_side` signature mismatch).

- [ ] **Step 3: Rewrite `src/lbb/web/bridge.py`**

```python
"""JsApiBridge — exposed to JavaScript as `window.pywebview.api`.

Every method returns a JSON-serialisable value and delegates to
FulfillmentService. No business logic — only argument marshalling and OS
open/print of downloaded files.
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
    def engrave_side(self, order_number, file_key):
        return self._svc.engrave_side(order_number, file_key)

    def ship_order(self, order_number):
        return self._svc.ship_order(order_number)

    def set_status(self, order_number, status):
        return self._svc.set_status(order_number, status)

    def flag_revision(self, order_number):
        return self._svc.flag_revision(order_number)

    # ── shell helpers ──
    def open_amazon(self, url):
        return self._open(url) or {"ok": True}

    def open_label(self, order_number):
        path = self._svc.label_file(order_number)
        if not path:
            return {"ok": False, "error": "No label file"}
        return self._open(str(path)) or {"ok": True}

    def print_label(self, order_number):
        path = self._svc.label_file(order_number)
        if not path:
            return {"ok": False, "error": "No label file"}
        return self._print(str(path))

    # ── internals ──
    def _open(self, target: str):
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

    def _print(self, target: str):
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

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/web/test_bridge.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/lbb/web/bridge.py tests/web/test_bridge.py
git commit -m "feat(web): bridge engrave-by-file-key, flag_revision, label download"
```

---

### Task 8: Front-end — 3 statuses, file-key sides, instruction, refresh

**Files:**
- Modify: `src/lbb/web/assets/app.js`
- Modify: `src/lbb/web/assets/index.html`
- Modify: `src/lbb/web/assets/app.css`

This task has no unit test (static assets); verify with `node --check` and a manual review. Keep edits surgical.

- [ ] **Step 1: Update the status selector in `index.html`**

Replace the `<select id="statusSel">` block (lines ~132-138) with:

```html
              <select id="statusSel" onchange="onStatusSelect(this.value)">
                <option value="not_done_yet">Open · not engraved</option>
                <option value="revision">Needs review / rework</option>
                <option value="graviert_verschickt">Engraved &amp; shipped</option>
              </select>
```

- [ ] **Step 2: Replace the comment card body with a read-only instruction in `index.html`**

Replace the `<label class="field-lbl" for="comment" ...>` line through the `<div class="hint">…</div>` (lines ~141-144) with:

```html
            <label class="field-lbl" style="margin-top:18px">Instruction from Flanacom</label>
            <div id="instruction" class="instruction">—</div>
            <div class="row-end"><button class="btn warn" onclick="flagRevision()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>Flag for revision</button></div>
            <div class="hint">Status is written back to Flanacom’s system.</div>
```

- [ ] **Step 3: Add a Refresh button to the dashboard header in `index.html`**

Find the dashboard sub-header element `id="dashSub"`. Immediately AFTER its containing line, add a refresh button. Locate the line containing `id="dashSub"` and add, right after the element that closes that header row:

```html
        <button class="btn ghost" id="refreshBtn" onclick="loadDashboard()" title="Reload orders from Flanacom"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 4v6h-6"/><path d="M1 20v-6h6"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>Refresh</button>
```

(If unsure of exact placement, place it inside the same fl/header container as `dashSub` so it renders in the dashboard header. Do not break existing markup.)

- [ ] **Step 4: Update `app.js` — status labels, dashboard loader, sides, actions**

Apply these edits in `src/lbb/web/assets/app.js`:

(a) Replace `statusOf` (lines ~37-42) with:

```javascript
function statusOf(o){
  const key = o.status || 'not_done_yet';
  const labels = {not_done_yet:'Open', graviert_verschickt:'Engraved & shipped', revision:'Needs review'};
  return {key, label: labels[key] || key};
}
```

(b) Replace `loadDashboard` (lines ~47-52) with:

```javascript
async function loadDashboard(){
  const filter = document.querySelector('#filterChips .chip.active')?.dataset.f || 'all';
  const q = document.getElementById('searchInput').value || '';
  const res = await API.listOrders(filter, q);
  ORDERS = (res && res.orders) || [];
  renderBanner(res && res.error);
  renderDashboard();
}
function renderBanner(error){
  let bar = document.getElementById('apiBanner');
  if(!bar){
    bar = document.createElement('div'); bar.id='apiBanner'; bar.className='api-banner';
    document.body.prepend(bar);
  }
  if(error){ bar.textContent = '⚠ '+error+' — check the API key in ~/.flanacom-tool/config.json'; bar.hidden=false; }
  else { bar.hidden = true; }
}
```

(c) In `renderDashboard` replace the status-label map (lines ~76-78) with:

```javascript
      const stKey = card.status || 'not_done_yet';
      const stLabels = {not_done_yet:'Open',graviert_verschickt:'Engraved & shipped',revision:'Needs review'};
      const stLabel = stLabels[stKey] || stKey;
```

(d) Replace `startEngraving` (lines ~102-107) — open first non-done order:

```javascript
async function startEngraving(){
  const first = ORDERS.find(c => c.status !== 'graviert_verschickt');
  if(first){ await openOrder(first.order_number); toast('Starting with '+first.order_number); }
  else toast('No open orders to engrave','gold');
}
```

(e) In `renderOrder`, replace the `isShipped` derivation (line ~183) and the live-pill block (lines ~189-197) with:

```javascript
  const isShipped = O.status==='graviert_verschickt';
```

and

```javascript
  const pill=document.getElementById('livePill'), pillTxt=document.getElementById('livePillText'), sel=document.getElementById('statusSel');
  pill.classList.remove('hold');
  const st=statusOf(O);
  if(st.key==='revision'){ pill.classList.add('hold'); pillTxt.textContent='Needs review'; }
  else if(st.key==='graviert_verschickt'){ pillTxt.textContent='Engraved & shipped'; }
  else if(isAllEng){ pillTxt.textContent='Engraved · ready to ship'; }
  else if(done>0){ pillTxt.textContent='Engraving in progress'; }
  else { pillTxt.textContent='Open · ready to engrave'; }
  sel.value=st.key;
  const instr=document.getElementById('instruction');
  if(instr){ instr.textContent = O.instruction || '—'; }
```

(Add `const isAllEng = allEng(O);` just before this block if it is not already defined above it.)

(f) Replace `engrave(pi, si)` (lines ~217-232) so it sends the file key:

```javascript
async function engrave(pi, si){
  if(busy) return;
  const p = CURRENT.products[pi], side = p.sides[si];
  if(active!==pi){ active=pi; }
  busy=true; renderOrder();
  document.getElementById('livePillText').textContent='Opening LightBurn…';
  const res = await API.engraveSide(CURRENT.order_number, side.file_key);
  busy=false;
  if(!res || !res.ok){ toast((res && res.error) || 'Engrave failed','gold'); renderOrder(); return; }
  CURRENT = await API.getOrder(CURRENT.order_number);
  if(!CURRENT){ toast('Could not refresh order','gold'); goDashboard(); return; }
  const np = tasksOf(CURRENT).find(t=>!t.s.engraved); if(np) active=np.pi;
  renderOrder();
  toast(side.name+' engraved'+(allEng(CURRENT)?' · all done':''));
}
```

(g) Replace `confirmShip` tail (lines ~256-259) to find next non-done order:

```javascript
  await loadDashboard();
  const first = ORDERS.find(c => c.status !== 'graviert_verschickt');
  if(first){ await openOrder(first.order_number); }
  else { goDashboard(); toast('All open orders done!'); }
```

(h) Replace `onStatusSelect` (lines ~262-275) with:

```javascript
async function onStatusSelect(v){
  if(busy){ renderOrder(); return; }
  if(v==='graviert_verschickt'){
    if(allEng(CURRENT)) askShip();
    else toast('Engrave all sides first','gold');
    renderOrder(); return;
  }
  const res = await API.setStatus(CURRENT.order_number, v);
  if(!res || !res.ok){ toast((res && res.error)||'Status change failed','gold'); }
  CURRENT = await API.getOrder(CURRENT.order_number);
  if(!CURRENT){ toast('Could not refresh order','gold'); goDashboard(); return; }
  renderOrder();
  if(v==='revision') toast('Flagged for revision','gold');
}
```

(i) Replace `sendComment` (lines ~277-289) with a `flagRevision` action:

```javascript
async function flagRevision(){
  if(!CURRENT) return;
  const res = await API.flagRevision(CURRENT.order_number);
  if(!res || !res.ok){ toast((res && res.error)||'Could not flag','gold'); return; }
  CURRENT = await API.getOrder(CURRENT.order_number);
  renderOrder();
  toast('Order flagged for revision','gold');
}
```

(j) The new `get_order` view-model replaces `label`/`recipient` with `has_label`,
`amount`, and `instruction`. Update the two stale references in `renderOrder`:

Replace the label block (lines ~121-128, the `if(O.label){ … } else { … }`) with:

```javascript
  document.getElementById('labelCarrier').textContent = O.has_label ? 'Shipping label' : '—';
  document.getElementById('labelFile').textContent = O.has_label ? 'label.pdf' : '(no label file)';
```

Replace the Recipient row in the `orderKv` template (the trailing
`'<div class="k">Recipient</div>…'` line, ~161) with an Items row:

```javascript
   +'<div class="k">Items</div><div class="v">'+(O.amount||O.products.length)+'</div>';
```

- [ ] **Step 5: Update `bridge-client.js` API wrapper**

In `src/lbb/web/assets/bridge-client.js`, ensure the API object exposes `engraveSide(orderNumber, fileKey)`, `flagRevision(orderNumber)`, and `setStatus(orderNumber, status)` and no longer references `addComment`. Read the file first; update the method bodies to call `window.pywebview.api.engrave_side(orderNumber, fileKey)`, `window.pywebview.api.flag_revision(orderNumber)`, and remove any `addComment` wrapper. Keep the browser-mock fallback shape returning `{ok:true}` / `{orders:[],error:null}` so the page still loads outside pywebview.

- [ ] **Step 6: Add CSS for new states in `app.css`**

Append to `src/lbb/web/assets/app.css`:

```css
/* live-API states */
.stat.not_done_yet .d{background:#9aa1ab}
.stat.graviert_verschickt .d{background:#2e9e5b}
.stat.revision .d{background:#e08a1e}
.stat.graviert_verschickt{color:#2e9e5b}
.stat.revision{color:#e08a1e}
.instruction{background:#f7f4ee;border:1px solid #ece6da;border-radius:10px;padding:10px 12px;color:#4a4640;font-size:14px;min-height:20px;white-space:pre-wrap}
.btn.warn{color:#a85b00;border-color:#e6b877}
.btn.ghost{background:transparent}
.api-banner{position:sticky;top:0;z-index:50;background:#fff4e5;color:#7a4b00;border-bottom:1px solid #f0d6a8;padding:8px 16px;font-size:14px}
.api-banner[hidden]{display:none}
```

- [ ] **Step 7: Syntax-check the JS**

Run: `node --check src/lbb/web/assets/app.js && node --check src/lbb/web/assets/bridge-client.js`
Expected: no output (exit 0).

- [ ] **Step 8: Commit**

```bash
git add src/lbb/web/assets/app.js src/lbb/web/assets/index.html src/lbb/web/assets/app.css src/lbb/web/assets/bridge-client.js
git commit -m "feat(web): 3-status UI, file-key engraving, instruction + revision, refresh, error banner"
```

---

### Task 9: Composition root + remove the seed path

**Files:**
- Modify: `src/lbb/app/container.py`
- Modify: `src/lbb/__main__.py`
- Delete: `src/lbb/adapters/json_fulfillment.py`
- Delete: `tests/unit/adapters/test_json_fulfillment.py`
- Delete: `src/lbb/web/assets/seed-orders/` (whole directory)

- [ ] **Step 1: Delete the seed adapter, its test, and seed data**

```bash
git rm src/lbb/adapters/json_fulfillment.py tests/unit/adapters/test_json_fulfillment.py
git rm -r src/lbb/web/assets/seed-orders
```

- [ ] **Step 2: Rewrite `build_fulfillment_service` in `src/lbb/app/container.py`**

Replace the imports of `JsonFulfillmentRepository` and `SqliteStateStore`/the `build_fulfillment_service` function with:

```python
from lbb.adapters.config import ApiConfig
from lbb.adapters.engraving_api import EngravingApiClient
from lbb.adapters.http_urllib import UrllibTransport
from lbb.adapters.lightburn_shell import LightBurnShellAdapter
from lbb.adapters.sqlite_state import SqliteStateStore
from lbb.app.fulfillment_service import FulfillmentService
```

```python
def build_fulfillment_service(
    config: ApiConfig, state_db: Path, cache_dir: Path
) -> FulfillmentService:
    gateway = EngravingApiClient(config.base_url, config.api_key, UrllibTransport())
    return FulfillmentService(
        gateway=gateway,
        state=SqliteStateStore(state_db),
        lightburn=LightBurnShellAdapter(),
        cache_dir=cache_dir,
    )
```

(Leave `build_pipeline_deps` and the legacy `SqliteProfileRepository`/`PdfiumReader` wiring untouched — it serves the dormant pipeline. Only remove the `JsonFulfillmentRepository` import.)

- [ ] **Step 3: Rewrite `src/lbb/__main__.py`**

```python
"""Entry point: `uv run python -m lbb` or the PyInstaller-built binary."""

from __future__ import annotations

import sys
from pathlib import Path

from lbb.adapters.config import DEFAULT_BASE_URL, ApiConfig, load_config
from lbb.app.container import build_fulfillment_service
from lbb.web.shell import run_app

_DATA_HOME = Path.home() / ".flanacom-tool"


def main() -> int:
    _DATA_HOME.mkdir(parents=True, exist_ok=True)
    example = _DATA_HOME / "config.example.json"
    if not example.exists():
        example.write_text(
            '{\n  "api_base_url": "%s",\n  "api_key": "PASTE-YOUR-X-API-KEY-HERE"\n}\n'
            % DEFAULT_BASE_URL,
            encoding="utf-8",
        )
    config = load_config(config_path=_DATA_HOME / "config.json")
    if config is None:
        # Launch anyway with an empty key so the UI shows the configuration banner.
        config = ApiConfig(DEFAULT_BASE_URL, "")
    service = build_fulfillment_service(
        config=config,
        state_db=_DATA_HOME / "state.sqlite",
        cache_dir=_DATA_HOME / "cache",
    )
    run_app(service, title="Fulfillment Studio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS. If any test still imports `json_fulfillment` or the old `OrderStatus` values, fix that test to the new API. The seed-fixture generator is handled in Task 10.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(app): wire live gateway from config; remove seeded JSON runtime path"
```

---

### Task 10: Architecture contracts, fixtures cleanup, full green

**Files:**
- Modify: `scripts/generate_fixtures.py` (remove seed-orders generation)
- Modify: `.importlinter` (allow new modules; keep purity)
- Possibly modify: any remaining test referencing removed symbols

- [ ] **Step 1: Remove seed-order fixture generation**

In `scripts/generate_fixtures.py`, delete `make_seed_orders()` and `make_seed_labels()` and any call to them in `__main__`. Keep the LightBurn/PDF golden fixtures used by other tests. If after removal the file has unused imports, remove them.

- [ ] **Step 2: Verify import-linter contracts**

Run: `uv run lint-imports`
Expected: All contracts KEPT. The `core/` purity contract must still pass (core imports only stdlib + core). `web/` must not import `adapters`. If a violation appears (e.g. `ports/engraving.py` importing `core` is fine; `core` must not import `adapters`/`ports`), fix by moving code, not by weakening the contract.

- [ ] **Step 3: Lint**

Run: `uv run ruff check src tests`
Expected: no errors. Fix any (unused imports from deletions, etc.).

- [ ] **Step 4: Full test suite**

Run: `uv run pytest -q`
Expected: all pass (the 4 host-dependent UDP tests remain skipped). Record the pass/skip counts.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: drop seed fixtures, keep import-linter contracts green"
```

---

### Task 11: Live smoke test + branded build (controller-run)

This task requires a Windows display, the real API key, and LightBurn. The controller (not a subagent) runs it with the user.

- [ ] **Step 1: Place the real key OUTSIDE the repo**

Create `C:\Users\Client\.flanacom-tool\config.json` (NOT in the git tree) with the real `api_key` from Hauke's email and the base URL. Confirm `git status` in the repo shows it untracked/ignored (it lives in the user home, not the repo).

- [ ] **Step 2: Live read smoke**

Run a one-off read against the real API to confirm credentials + parsing:

```bash
uv run python -c "from pathlib import Path; from lbb.adapters.config import load_config; from lbb.adapters.engraving_api import EngravingApiClient; from lbb.adapters.http_urllib import UrllibTransport; c=load_config(config_path=Path.home()/'.flanacom-tool'/'config.json'); g=EngravingApiClient(c.base_url,c.api_key,UrllibTransport()); o=g.list_orders(); print('orders:',len(o)); print(o[0].order_number, o[0].status, [s.file_key for p in o[0].products for s in p.sides][:2]) if o else print('no orders')"
```

Expected: prints a count and a sample order with real file keys. A 401 means the key is wrong.

- [ ] **Step 3: GUI smoke**

Run: `uv run python -m lbb`
Verify: dashboard lists live orders; open one; click "Engrave Front · LightBurn" → the real PDF downloads and opens **in LightBurn**; progress increments; "Mark engraved & shipped" (after both sides) writes status (re-open / refresh shows `graviert_verschickt`); "Flag for revision" sets `revision`. No SQLite thread error in the console.

- [ ] **Step 4: Build the branded exe**

First fix the output name in `packaging/lbb.spec`: set the `EXE(... name="Fulfillment Studio")` (and `COLLECT(... name="Fulfillment Studio")` if present). Then:

Run: `uv run pyinstaller packaging/lbb.spec --clean --noconfirm`
Expected: `dist/Fulfillment Studio/Fulfillment Studio.exe` with `_internal/lbb/web/assets/` bundled (no `seed-orders/`).

- [ ] **Step 5: Verify the built exe**

Launch `dist/Fulfillment Studio/Fulfillment Studio.exe`. Confirm it reads the `~/.flanacom-tool/config.json` key, lists live orders, and the engrave→LightBurn path works from the packaged build.

- [ ] **Step 6: Commit the spec rename + finish**

```bash
git add packaging/lbb.spec
git commit -m "build: brand the bundle as Fulfillment Studio"
```

Then use the `superpowers:finishing-a-development-branch` skill to merge `feature/fulfillment-studio` or open a PR.

---

## Notes for the executor

- **Secret hygiene:** never write the real `api_key` into any file under the repo, any test, any spec, any commit, or any log. It lives only in `~/.flanacom-tool/config.json` (env var alternative: `FLANACOM_API_KEY`).
- **No network in unit tests:** all adapter tests use a fake transport. Only Task 11 touches the live API.
- **Windows date formatting:** never use `%-d` (crashes on Windows) — the `_placed_label` helper uses `o.placed_at.day`.
- **import-linter:** `core/` may import only stdlib + `lbb.core`. `ports/engraving.py` importing `lbb.core` is allowed; ensure `core/fulfillment.py` imports nothing from `lbb.adapters`/`lbb.ports`/`lbb.app`.
