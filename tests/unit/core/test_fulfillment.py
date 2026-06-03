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
