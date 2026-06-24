"""FulfillmentService — the order-fulfillment brain.

Reads orders from the live EngravingGateway, merges local engraving progress
(FulfillmentStateStore), downloads each engraving PDF fresh and opens it in
LightBurn, and writes the 3 canonical statuses back. Returns JSON-serialisable
view models for the web bridge. Knows nothing about pywebview or HTTP.
"""

from __future__ import annotations

import base64
from pathlib import Path

from lbb.core.errors import LbbError
from lbb.core.fulfillment import (
    FulfillmentOrder,
    OrderStatus,
    all_sides,
    queue_sort_key,
    sides_summary,
)
from lbb.ports.engraving import EngravingApiError, EngravingGateway
from lbb.ports.fulfillment import FulfillmentStateStore
from lbb.ports.lightburn import LightBurnPort

_BUCKETS = {"Bracelet": "Bracelets", "Necklace": "Necklaces", "Keychain": "Keychains",
            "Flask": "Flasks", "MiniFlask": "Mini flasks", "Lighter": "Lighters"}
_IMAGE_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".webp": "image/webp", ".gif": "image/gif"}


def _date_label(dt) -> str:
    return f"{dt:%b} {dt.day}, {dt:%Y}" if dt else ""


def _placed_label(o: FulfillmentOrder) -> str:
    return _date_label(o.placed_at)


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
            "link_to_graphic": o.link_to_graphic,
            "created_label": _date_label(o.created_at),
            "updated_label": _date_label(o.updated_at),
            "type_summary": o.type_summary,
            "color_summary": o.color_summary,
            "has_order_picture": bool(o.order_picture_key),
            "label_name": Path(o.label_key).name if o.label_key else "",
            "products": [
                {
                    "product_type": p.product_type,
                    "name": p.product_type,
                    "color": p.coin_color,
                    "band_color": p.band_color,
                    "image_key": p.image_key,
                    "multiple_coins": p.multiple_coins,
                    "special_length": p.special_length,
                    "length": p.length,
                    "coin_count": p.coin_count,
                    "sides_summary": sides_summary(p),
                    "has_image": bool(p.image_key),
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

    def product_image(self, order_number: str, product_index: int) -> dict:
        o = self.gateway.get(order_number)
        if o is None:
            return {"ok": False, "error": "Order not found"}
        try:
            p = o.products[int(product_index)]
        except (IndexError, ValueError, TypeError):
            return {"ok": False, "error": "Unknown product"}
        if not p.image_key:
            return {"ok": False}
        try:
            path = self.gateway.download_file(o.order_id, p.image_key, self._dir(o))
            data = path.read_bytes()
        except (EngravingApiError, OSError) as e:
            return {"ok": False, "error": str(e)}
        mime = _IMAGE_MIME.get(Path(p.image_key).suffix.lower(), "application/octet-stream")
        b64 = base64.b64encode(data).decode("ascii")
        return {"ok": True, "data_uri": f"data:{mime};base64,{b64}"}

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
        except (EngravingApiError, LbbError, OSError) as e:
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
