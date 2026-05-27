"""Tests for the search-first HomeView (2026-05-26 redesign)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from PySide6.QtCore import Qt

from lbb.core.models import Sku
from lbb.core.order import Customer, Order, OrderItem
from lbb.ports.orders import OrderRepository
from lbb.ui.views.home import HomeView


class _InMemoryOrders(OrderRepository):
    def __init__(self, orders: list[Order]) -> None:
        self._orders = {o.order_number: o for o in orders}

    def get(self, order_number: str) -> Order | None:
        return self._orders.get(order_number)

    def list_all(self) -> list[Order]:
        return sorted(self._orders.values(), key=lambda o: o.order_number)


def _make_order(num: str, customer: str, n_items: int) -> Order:
    items = tuple(
        OrderItem(item_id=chr(ord("A") + i), sku=Sku("LB-SKU"))
        for i in range(n_items)
    )
    return Order(
        order_number=num,
        customer=Customer(name=customer),
        items=items,
        placed_at=datetime(2026, 5, 15, tzinfo=UTC),
    )


@pytest.fixture
def orders_repo() -> _InMemoryOrders:
    return _InMemoryOrders(
        [
            _make_order("305-6737580-7658721", "Jane & John Doe", 3),
            _make_order("304-4865183-6105121", "Maria Smith", 1),
        ]
    )


def test_constructs_with_search_input_visible(qtbot, orders_repo):
    view = HomeView(orders_repo)
    qtbot.addWidget(view)
    assert view.search_input is not None
    assert view.open_btn is not None


def test_recent_orders_list_renders_one_card_per_order(qtbot, orders_repo):
    view = HomeView(orders_repo)
    qtbot.addWidget(view)
    nums = view.recent_order_numbers()
    assert set(nums) == {"305-6737580-7658721", "304-4865183-6105121"}


def test_empty_orders_repo_shows_empty_state(qtbot):
    view = HomeView(_InMemoryOrders([]))
    qtbot.addWidget(view)
    assert view.recent_order_numbers() == []


def test_open_button_emits_order_searched_with_input_text(qtbot, orders_repo):
    view = HomeView(orders_repo)
    qtbot.addWidget(view)
    received: list[str] = []
    view.order_searched.connect(received.append)
    view.search_input.setText("305-6737580-7658721")
    view.open_btn.click()
    assert received == ["305-6737580-7658721"]


def test_enter_in_search_input_emits_order_searched(qtbot, orders_repo):
    view = HomeView(orders_repo)
    qtbot.addWidget(view)
    received: list[str] = []
    view.order_searched.connect(received.append)
    view.search_input.setText("305")
    qtbot.keyClick(view.search_input, Qt.Key_Return)
    assert received == ["305"]


def test_empty_search_does_not_emit(qtbot, orders_repo):
    view = HomeView(orders_repo)
    qtbot.addWidget(view)
    received: list[str] = []
    view.order_searched.connect(received.append)
    view.open_btn.click()
    assert received == []


def test_show_not_found_displays_inline_error(qtbot, orders_repo):
    view = HomeView(orders_repo)
    qtbot.addWidget(view)
    assert view.search_error.isHidden()
    view.show_not_found("999")
    assert (not view.search_error.isHidden())
    assert "999" in view.search_error.text()


def test_typing_after_not_found_hides_the_error(qtbot, orders_repo):
    view = HomeView(orders_repo)
    qtbot.addWidget(view)
    view.show_not_found("999")
    view.search_input.setText("3")
    assert view.search_error.isHidden()
