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
