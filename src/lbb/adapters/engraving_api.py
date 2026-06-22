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
_HTTP_OK = 200


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
        if code != _HTTP_OK:
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
        if code != _HTTP_OK:
            raise EngravingApiError(
                f"Status update failed ({code})", status_code=code
            )
        self._fetched_at = None

    # ── internals ──────────────────────────────────────────────────────────
    def _fetch(self) -> None:
        code, data = self._http.request(
            "GET", self._base, headers={"x-api-key": self._key}
        )
        if code != _HTTP_OK:
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
    if name in (".", ".."):
        name = "download"
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
        link_to_graphic=str(raw.get("link_to_graphic") or ""),
        created_at=_parse_date(raw.get("created_at")),
        updated_at=_parse_date(raw.get("updated_at")),
        order_picture_key=str(raw.get("product_picture_path") or ""),
        type_summary=normalize_type(str(raw["product_type"])) if raw.get("product_type") else "",
        color_summary=str(raw.get("color") or ""),
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
        coin_count=len(coins),
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
