from __future__ import annotations

from typing import Protocol


class FulfillmentStateStore(Protocol):
    def engraved_keys(self, order_number: str) -> set[str]: ...
    def mark_engraved(self, order_number: str, file_key: str, engraved: bool) -> None: ...
