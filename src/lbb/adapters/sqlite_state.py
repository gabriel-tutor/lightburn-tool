"""SQLite-backed FulfillmentStateStore — local operator progress.

Mirrors SqliteProfileRepository's construction pattern. Shaped so a future
sync job can push this state up to Airtable/Supabase without UI changes.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from lbb.adapters.state_migrations import STATE_SCHEMA_V1
from lbb.core.fulfillment import Comment, OrderStatus
from lbb.ports.fulfillment import FulfillmentStateStore


class SqliteStateStore(FulfillmentStateStore):
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(STATE_SCHEMA_V1)

    def engraved_sides(self, order_number: str) -> set[tuple[str, str]]:
        rows = self._conn.execute(
            "SELECT item_id, side_name FROM engraved_sides WHERE order_number = ?",
            (order_number,),
        ).fetchall()
        return {(r["item_id"], r["side_name"]) for r in rows}

    def mark_side(self, order_number: str, item_id: str, side_name: str, engraved: bool) -> None:
        with self._conn:
            if engraved:
                self._conn.execute(
                    """INSERT INTO engraved_sides (order_number, item_id, side_name)
                       VALUES (?, ?, ?)
                       ON CONFLICT(order_number, item_id, side_name) DO NOTHING""",
                    (order_number, item_id, side_name),
                )
            else:
                self._conn.execute(
                    """DELETE FROM engraved_sides
                       WHERE order_number = ? AND item_id = ? AND side_name = ?""",
                    (order_number, item_id, side_name),
                )

    def get_override(self, order_number: str) -> OrderStatus | None:
        row = self._conn.execute(
            "SELECT status FROM order_overrides WHERE order_number = ?",
            (order_number,),
        ).fetchone()
        return OrderStatus(row["status"]) if row else None

    def set_override(self, order_number: str, status: OrderStatus | None) -> None:
        with self._conn:
            if status is None:
                self._conn.execute(
                    "DELETE FROM order_overrides WHERE order_number = ?", (order_number,)
                )
            else:
                self._conn.execute(
                    """INSERT INTO order_overrides (order_number, status) VALUES (?, ?)
                       ON CONFLICT(order_number) DO UPDATE SET
                           status = excluded.status, updated_at = datetime('now')""",
                    (order_number, str(status)),
                )

    def comments(self, order_number: str) -> list[Comment]:
        rows = self._conn.execute(
            """SELECT text, author, created_at FROM order_comments
               WHERE order_number = ? ORDER BY id""",
            (order_number,),
        ).fetchall()
        return [
            Comment(text=r["text"], author=r["author"], created_at=r["created_at"])
            for r in rows
        ]

    def add_comment(self, order_number: str, text: str, author: str) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO order_comments (order_number, text, author) VALUES (?, ?, ?)",
                (order_number, text, author),
            )
