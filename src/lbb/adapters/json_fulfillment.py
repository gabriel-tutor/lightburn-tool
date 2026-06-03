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
                Side(
                    name=str(s["name"]),
                    pdf_path=self._resolve(str(s.get("pdf_path", ""))),
                )
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
                    customization={
                        str(k): str(v)
                        for k, v in (raw.get("customization") or {}).items()
                    },
                    notes=str(raw.get("notes", "")),
                )
            )
        label_node = payload.get("label")
        label = (
            Label(
                carrier=str(label_node.get("carrier", "")),
                pdf_path=self._resolve(str(label_node.get("pdf_path", ""))),
            )
            if isinstance(label_node, dict)
            else None
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
            recipient=Recipient(
                name=str(rec.get("name", "")),
                address=str(rec.get("address", "")),
            ),
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
