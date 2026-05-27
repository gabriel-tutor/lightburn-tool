from datetime import UTC, datetime

from lbb.core.models import Sku
from lbb.core.order import Customer, Order, OrderItem


def test_order_item_construction():
    item = OrderItem(
        item_id="A",
        sku=Sku("LB-WALLET-LEATHER-S"),
        customization={"engraving_text": "John 2026"},
        pdf_path="305.pdf",
    )
    assert item.item_id == "A"
    assert item.sku.value == "LB-WALLET-LEATHER-S"
    assert item.customization["engraving_text"] == "John 2026"
    assert item.notes == ""


def test_order_with_multiple_items_equality():
    items = (
        OrderItem(item_id="A", sku=Sku("S")),
        OrderItem(item_id="B", sku=Sku("S")),
    )
    o1 = Order(
        order_number="305",
        customer=Customer(name="Jane"),
        items=items,
        placed_at=datetime(2026, 5, 15, tzinfo=UTC),
    )
    o2 = Order(
        order_number="305",
        customer=Customer(name="Jane"),
        items=items,
        placed_at=datetime(2026, 5, 15, tzinfo=UTC),
    )
    assert o1 == o2


def test_order_item_default_customization_is_empty_dict():
    item = OrderItem(item_id="A", sku=Sku("S"))
    assert item.customization == {}
