"""Order repository port — keyed by order number (= PDF filename stem)."""

from __future__ import annotations

from typing import Protocol

from lbb.core.order import Order


class OrderRepository(Protocol):
    def get(self, order_number: str) -> Order | None: ...

    def list_all(self) -> list[Order]: ...
