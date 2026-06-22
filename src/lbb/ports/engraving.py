from __future__ import annotations

from pathlib import Path
from typing import Protocol

from lbb.core.errors import LbbError
from lbb.core.fulfillment import FulfillmentOrder, OrderStatus


class EngravingApiError(LbbError):
    """Any failure talking to the engraving API (network, 4xx, parse)."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class HttpTransport(Protocol):
    def request(
        self, method: str, url: str, *, headers: dict[str, str], body: bytes | None = None
    ) -> tuple[int, bytes]: ...


class EngravingGateway(Protocol):
    def list_orders(self) -> list[FulfillmentOrder]: ...
    def get(self, order_number: str) -> FulfillmentOrder | None: ...
    def download_file(self, order_id: str, file_key: str, dest_dir: Path) -> Path: ...
    def set_status(self, order_id: str, status: OrderStatus) -> None: ...
