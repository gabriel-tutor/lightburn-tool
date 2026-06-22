"""SQLite-backed FulfillmentStateStore — local operator progress.

Tracks which engraving file-keys an operator has sent to LightBurn. Opened
with check_same_thread=False and guarded by a lock because pywebview invokes
bridge methods on a worker thread while this connection is created on the main
thread.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from lbb.adapters.state_migrations import STATE_SCHEMA
from lbb.ports.fulfillment import FulfillmentStateStore


class SqliteStateStore(FulfillmentStateStore):
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock, self._conn:
            self._conn.executescript(STATE_SCHEMA)

    def engraved_keys(self, order_number: str) -> set[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT file_key FROM engraved_keys WHERE order_number = ?",
                (order_number,),
            ).fetchall()
        return {r["file_key"] for r in rows}

    def mark_engraved(self, order_number: str, file_key: str, engraved: bool) -> None:
        with self._lock, self._conn:
            if engraved:
                self._conn.execute(
                    """INSERT INTO engraved_keys (order_number, file_key)
                       VALUES (?, ?)
                       ON CONFLICT(order_number, file_key) DO NOTHING""",
                    (order_number, file_key),
                )
            else:
                self._conn.execute(
                    "DELETE FROM engraved_keys WHERE order_number = ? AND file_key = ?",
                    (order_number, file_key),
                )
