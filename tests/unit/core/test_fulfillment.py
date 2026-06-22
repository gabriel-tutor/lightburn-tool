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
