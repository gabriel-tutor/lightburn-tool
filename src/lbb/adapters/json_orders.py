"""JSON-backed `OrderRepository` — directory-based simulation of the future
Supabase/Airtable backend.

Layout:

    <orders_dir>/
    ├── orders.json
    ├── 305-A-john.pdf
    ├── 305-B-jane.pdf
    └── …

`orders.json` keys orders by order number; each item's `pdf_path` is
resolved relative to `orders_dir` (or kept as-is if absolute) and stored
back on the returned `OrderItem` so callers don't need to know about
resolution.

On first construction, if `orders_dir` doesn't exist and a `seed_dir` was
provided, the entire seed folder is copied to `orders_dir`. After that,
the user-home folder is authoritative — operators (or a future Supabase
sync job) may edit the JSON and add or remove PDFs.
"""

from __future__ import annotations

import json
import shutil
import sys
import traceback
from datetime import datetime
from pathlib import Path

from lbb.core.models import Sku
from lbb.core.order import Customer, Order, OrderItem
from lbb.ports.orders import OrderRepository


class JsonOrderRepository(OrderRepository):
    def __init__(self, orders_dir: Path, *, seed_dir: Path | None = None):
        self.orders_dir = Path(orders_dir)
        self.seed_dir = Path(seed_dir) if seed_dir is not None else None
        self._orders: dict[str, Order] = {}
        self._load()

    # ── Public API ──────────────────────────────────────────────────────────

    def get(self, order_number: str) -> Order | None:
        return self._orders.get(order_number)

    def list_all(self) -> list[Order]:
        return sorted(self._orders.values(), key=lambda o: o.order_number)

    # ── Internal ────────────────────────────────────────────────────────────

    def _load(self) -> None:
        # First-run seeding: if user-home dir doesn't exist yet, copy the
        # bundled seed wholesale (orders.json + design PDFs).
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

        orders_node = data.get("orders") if isinstance(data, dict) else None
        if not isinstance(orders_node, dict):
            return

        for order_number, payload in orders_node.items():
            try:
                self._orders[order_number] = self._parse_order(order_number, payload)
            except (TypeError, ValueError, KeyError) as e:
                traceback.print_exception(e, file=sys.stderr)

    def _parse_order(self, order_number: str, payload: dict) -> Order:
        cust_node = payload.get("customer") or {}
        customer = Customer(
            name=str(cust_node.get("name", "")),
            email=str(cust_node.get("email", "")),
        )
        items_node = payload.get("items") or []
        items: list[OrderItem] = []
        for raw in items_node:
            items.append(
                OrderItem(
                    item_id=str(raw["item_id"]),
                    sku=Sku(str(raw["sku"])),
                    customization={
                        str(k): str(v)
                        for k, v in (raw.get("customization") or {}).items()
                    },
                    pdf_path=self._resolve_pdf_path(str(raw.get("pdf_path", ""))),
                    notes=str(raw.get("notes", "")),
                )
            )

        placed_at_raw = payload.get("placed_at")
        placed_at: datetime | None
        if isinstance(placed_at_raw, str) and placed_at_raw:
            try:
                placed_at = datetime.fromisoformat(placed_at_raw.replace("Z", "+00:00"))
            except ValueError:
                placed_at = None
        else:
            placed_at = None

        return Order(
            order_number=order_number,
            customer=customer,
            items=tuple(items),
            placed_at=placed_at,
            notes=str(payload.get("notes", "")),
        )

    def _resolve_pdf_path(self, raw: str) -> str:
        if not raw:
            return ""
        p = Path(raw)
        if p.is_absolute():
            return str(p)
        return str((self.orders_dir / raw).resolve())
