from datetime import UTC, datetime

import pytest

from lbb.core.models import Sku
from lbb.core.order import Customer, Order, OrderItem
from lbb.ui.views.order_view import OrderView


@pytest.fixture
def sample_order() -> Order:
    return Order(
        order_number="305-6737580-7658721",
        customer=Customer(name="Jane & John Doe"),
        items=(
            OrderItem(
                item_id="A",
                sku=Sku("LB-WALLET-LEATHER-S"),
                customization={"engraving_text": "John 2026"},
            ),
            OrderItem(
                item_id="B",
                sku=Sku("LB-WALLET-LEATHER-S"),
                customization={"engraving_text": "Jane 2026"},
            ),
            OrderItem(
                item_id="C",
                sku=Sku("LB-MISSING-PROFILE"),
                customization={"engraving_text": "Gift card 2026"},
            ),
        ),
        placed_at=datetime(2026, 5, 15, tzinfo=UTC),
    )


def test_renders_order_header_and_customer(qtbot, sample_order):
    view = OrderView()
    qtbot.addWidget(view)
    view.populate(
        sample_order,
        completed_ids=set(),
        known_skus={"LB-WALLET-LEATHER-S"},
    )
    assert "305-6737580-7658721" in view.order_label.text()
    assert "Jane & John Doe" in view.customer_label.text()
    assert "3 items" in view.customer_label.text()


def test_renders_all_items_with_customization_text(qtbot, sample_order):
    view = OrderView()
    qtbot.addWidget(view)
    view.populate(
        sample_order,
        completed_ids=set(),
        known_skus={"LB-WALLET-LEATHER-S"},
    )
    rows = view.item_rows()
    assert [r["item_id"] for r in rows] == ["A", "B", "C"]
    assert rows[0]["customization"]["engraving_text"] == "John 2026"


def test_engrave_button_disabled_when_sku_not_in_known(qtbot, sample_order):
    view = OrderView()
    qtbot.addWidget(view)
    view.populate(
        sample_order,
        completed_ids=set(),
        known_skus={"LB-WALLET-LEATHER-S"},  # 'LB-MISSING-PROFILE' is NOT here
    )
    rows = view.item_rows()
    assert rows[0]["enabled"] is True
    assert rows[1]["enabled"] is True
    assert rows[2]["enabled"] is False  # the missing-SKU item


def test_engrave_button_click_emits_item_chosen(qtbot, sample_order):
    view = OrderView()
    qtbot.addWidget(view)
    view.populate(
        sample_order,
        completed_ids=set(),
        known_skus={"LB-WALLET-LEATHER-S"},
    )
    received: list = []
    view.item_chosen.connect(received.append)
    view.engrave_button_for("B").click()
    assert len(received) == 1
    assert received[0].item_id == "B"


def test_mark_completed_updates_row_and_progress(qtbot, sample_order):
    view = OrderView()
    qtbot.addWidget(view)
    view.populate(
        sample_order,
        completed_ids=set(),
        known_skus={"LB-WALLET-LEATHER-S"},
    )
    assert view.progress.value() == 0
    view.mark_completed("A")
    rows = {r["item_id"]: r for r in view.item_rows()}
    assert rows["A"]["completed"] is True
    assert rows["B"]["completed"] is False
    assert view.progress.value() == 1


def test_back_button_emits_back_requested(qtbot, sample_order):
    view = OrderView()
    qtbot.addWidget(view)
    view.populate(sample_order, completed_ids=set(), known_skus=set())
    received: list[bool] = []
    view.back_requested.connect(lambda: received.append(True))
    view.back_btn.click()
    assert received == [True]
