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
    Side,
    all_sides,
    derive_status,
    queue_sort_key,
)
from lbb.ports.fulfillment import FulfillmentRepository, FulfillmentStateStore
from lbb.ports.lightburn import LightBurnPort

_OPERATOR = "A. Fink"
_BUCKETS = {"Bracelet": "Bracelets", "Necklace": "Necklaces",
            "Keychain": "Keychains", "Flask": "Flasks"}


def _placed_label(o: FulfillmentOrder) -> str:
    """Human date like 'Jan 3, 2026' — portable across OSes (no %-d, which
    raises on Windows)."""
    if not o.placed_at:
        return ""
    return f"{o.placed_at:%b} {o.placed_at.day}, {o.placed_at:%Y}"


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
    def list_orders(self, *, filter: str = "all", query: str = "") -> list[dict]:  # noqa: A002
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
                "placed_label": _placed_label(o),
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
            "placed_label": _placed_label(o),
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

    def label_path(self, order_number: str) -> str | None:
        o = self.repo.get(order_number)
        if o and o.label and o.label.pdf_path and Path(o.label.pdf_path).is_file():
            return o.label.pdf_path
        return None

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
        return {
            "ok": True,
            "status": str(self._status(o)),
            "progress": {"done": done, "total": total},
        }

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
        if target is OrderStatus.HOLD:
            self.state.set_override(order_number, OrderStatus.HOLD)
        else:
            self.state.set_override(order_number, None)  # back to derived
        # status is re-derived live (override + engraved state), not echoed from the input
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
    def _find_side(o: FulfillmentOrder, item_id: str, side_name: str) -> Side | None:
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
