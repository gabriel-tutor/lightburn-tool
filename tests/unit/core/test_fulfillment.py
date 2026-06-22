from datetime import datetime

from lbb.core.fulfillment import (
    FulfillmentOrder,
    OrderStatus,
    Product,
    Side,
    all_sides,
    normalize_type,
    queue_sort_key,
    sides_summary,
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


def test_sides_summary_single_coin():
    p = Product(product_type="Necklace",
                sides=(Side("Front", "a"), Side("Back", "b")), coin_count=1)
    assert sides_summary(p) == "Front & Back"


def test_sides_summary_front_only():
    p = Product(product_type="Keychain", sides=(Side("Front", "a"),), coin_count=1)
    assert sides_summary(p) == "Front only"


def test_sides_summary_multiple_coins():
    p = Product(product_type="Necklace",
                sides=(Side("Coin 1 Front", "a"), Side("Coin 1 Back", "b"),
                       Side("Coin 2 Front", "c"), Side("Coin 2 Back", "d")),
                coin_count=2)
    assert sides_summary(p) == "2 coins · Front & Back each — 4 jobs"


def test_sides_summary_no_sides():
    p = Product(product_type="Necklace", sides=(), coin_count=0)
    assert sides_summary(p) == "No engraving files"


def test_new_order_fields_default_empty():
    o = _order()
    assert o.link_to_graphic == ""
    assert o.created_at is None and o.updated_at is None
    assert o.order_picture_key == "" and o.type_summary == "" and o.color_summary == ""


def test_queue_sort_falls_back_to_type_summary_when_no_products():
    o = FulfillmentOrder(order_id="x", order_number="A", products=(), type_summary="Flask")
    assert queue_sort_key(o)[0] == type_rank("Flask")
