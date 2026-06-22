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
_SIDES_PER_COIN = 2  # Front + Back
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
    coin_count: int = 1          # number of coins/plates on this item
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
    link_to_graphic: str = ""     # order-level link_to_graphic (often null)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    order_picture_key: str = ""   # order-level product_picture_path (often null)
    type_summary: str = ""        # order-level product_type (normalized)
    color_summary: str = ""       # order-level color
    channel: str = "Amazon · DE"

    @property
    def gift_box(self) -> bool:
        return "gift" in self.instruction.lower()


def all_sides(order: FulfillmentOrder) -> set[str]:
    """Every engraving file key in the order."""
    return {s.file_key for p in order.products for s in p.sides if s.file_key}


def sides_summary(product: Product) -> str:
    """Human description of a product's engraving jobs."""
    n = len(product.sides)
    if n == 0:
        return "No engraving files"
    coins = max(product.coin_count, 1)
    if coins == 1:
        if n == _SIDES_PER_COIN:
            return "Front & Back"
        return "Front only" if n == 1 else f"{n} engraving jobs"
    if n == coins * _SIDES_PER_COIN:
        return f"{coins} coins · Front & Back each — {n} jobs"
    if n == coins:
        return f"{coins} coins · Front only — {n} jobs"
    return f"{coins} coins · {n} engraving jobs"


def type_rank(product_type: str) -> int:
    """Position in the workshop queue; unknown types sort last."""
    try:
        return _TYPE_ORDER.index(product_type)
    except ValueError:
        return _UNKNOWN_TYPE_RANK


def queue_sort_key(order: FulfillmentOrder) -> tuple[int, str]:
    """Group by product-type rank (first product), then oldest placed first."""
    primary = order.products[0].product_type if order.products else (order.type_summary or "Other")
    placed = order.placed_at.isoformat() if order.placed_at else ""
    return (type_rank(primary), placed)
