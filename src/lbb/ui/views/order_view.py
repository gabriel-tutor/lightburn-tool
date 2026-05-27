"""Order view — lists all line items in a customer order.

Operator drops the order PDF on the home screen; MainWindow looks up the order
and routes here. Each item is rendered as a row with the SKU, customization
text, and an Engrave button that hands the item back to the controller for
the existing preview / Open-in-LightBurn flow. Completion state is
in-memory only — closing the app clears it.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from lbb.core.order import Order, OrderItem


class OrderView(QWidget):
    """Order summary + per-item engrave actions."""

    item_chosen = Signal(object)  # carries an OrderItem
    back_requested = Signal()

    def __init__(self) -> None:
        super().__init__()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 22, 28, 22)
        outer.setSpacing(14)

        # ── Header row: order number (mono) + Back ──────────────────────────
        header = QHBoxLayout()
        self.order_label = QLabel()
        self.order_label.setObjectName("monoCode")
        header.addWidget(self.order_label)
        header.addStretch()
        self.back_btn = QPushButton("← Back")
        self.back_btn.setObjectName("ghostButton")
        self.back_btn.clicked.connect(self.back_requested.emit)
        header.addWidget(self.back_btn)
        outer.addLayout(header)

        # ── Customer / placed-at line ───────────────────────────────────────
        self.customer_label = QLabel()
        self.customer_label.setObjectName("dim")
        self.customer_label.setWordWrap(True)
        outer.addWidget(self.customer_label)

        # ── Progress bar + count ────────────────────────────────────────────
        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        outer.addWidget(self.progress)

        # ── Items list (container; rows are added in populate) ──────────────
        self.items_box = QFrame()
        self.items_box.setObjectName("itemsBox")
        self.items_layout = QVBoxLayout(self.items_box)
        self.items_layout.setContentsMargins(0, 6, 0, 6)
        self.items_layout.setSpacing(8)
        outer.addWidget(self.items_box, stretch=1)

        # Track per-item widgets so we can flip completed state later.
        self._rows: dict[str, _ItemRow] = {}
        self._order: Order | None = None
        self._completed_ids: set[str] = set()

    # ── Public API ──────────────────────────────────────────────────────────

    def populate(
        self,
        order: Order,
        *,
        completed_ids: set[str],
        known_skus: set[str],
    ) -> None:
        """Render `order`. `completed_ids` toggles ✓ glyphs; `known_skus`
        decides which Engrave buttons are enabled."""
        self._order = order
        self._completed_ids = set(completed_ids)

        self.order_label.setText(f"ORDER  {order.order_number}")
        bits = [order.customer.name or "Unknown customer"]
        if order.placed_at is not None:
            bits.append(f"placed {order.placed_at.strftime('%Y-%m-%d')}")
        bits.append(f"{len(order.items)} item{'s' if len(order.items) != 1 else ''}")
        self.customer_label.setText("  •  ".join(bits))

        # Clear any previous rows
        for row in self._rows.values():
            self.items_layout.removeWidget(row)
            row.setParent(None)
        self._rows.clear()

        for item in order.items:
            row = _ItemRow(item, completed=item.item_id in completed_ids,
                            enabled=item.sku.value in known_skus)
            row.engrave_clicked.connect(lambda i=item: self.item_chosen.emit(i))
            self.items_layout.addWidget(row)
            self._rows[item.item_id] = row

        self._update_progress()

    def mark_completed(self, item_id: str) -> None:
        """Flip an item's row to ✓ and update the progress bar."""
        row = self._rows.get(item_id)
        if row is None:
            return
        row.set_completed(True)
        self._completed_ids.add(item_id)
        self._update_progress()

    # Test seam — assertable snapshot of the rendered rows.
    def item_rows(self) -> list[dict]:
        return [
            {
                "item_id": item_id,
                "completed": row.completed,
                "enabled": row.engrave_btn.isEnabled(),
                "sku": row.item.sku.value,
                "customization": dict(row.item.customization),
            }
            for item_id, row in self._rows.items()
        ]

    def engrave_button_for(self, item_id: str) -> QPushButton | None:
        row = self._rows.get(item_id)
        return row.engrave_btn if row else None

    # ── Internal ────────────────────────────────────────────────────────────

    def _update_progress(self) -> None:
        if self._order is None:
            return
        total = len(self._order.items)
        done = len(self._completed_ids & {i.item_id for i in self._order.items})
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(done)
        self.progress.setFormat(f"{done} / {total} engraved")


class _ItemRow(QFrame):
    """A single item card inside the order view."""

    engrave_clicked = Signal()

    def __init__(self, item: OrderItem, *, completed: bool, enabled: bool) -> None:
        super().__init__()
        self.setObjectName("orderItemRow")
        self.item = item
        self.completed = completed

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(12)

        # Status glyph + item id + SKU
        self.status_label = QLabel()
        self.status_label.setFixedWidth(18)
        self.status_label.setStyleSheet("font-size: 16px;")
        row.addWidget(self.status_label)

        meta = QVBoxLayout()
        meta.setSpacing(2)
        top_line = QLabel(
            f"Item {item.item_id}  ·  <span style='color:#1A1A1A;'>{item.sku.value}</span>"
        )
        top_line.setStyleSheet("font-size: 13px; font-weight: 500;")
        meta.addWidget(top_line)
        customization_text = (
            item.customization.get("engraving_text") or "(no engraving text)"
        )
        customization_lbl = QLabel(f'"{customization_text}"')
        customization_lbl.setObjectName("dim")
        customization_lbl.setStyleSheet("font-size: 12px;")
        meta.addWidget(customization_lbl)
        row.addLayout(meta, stretch=1)

        self.engrave_btn = QPushButton("Engrave  →")
        self.engrave_btn.setObjectName("sendButton")
        self.engrave_btn.clicked.connect(self.engrave_clicked.emit)
        if not enabled:
            self.engrave_btn.setEnabled(False)
            self.engrave_btn.setToolTip(
                f"SKU {item.sku.value} is not registered. Add it via Admin first."
            )
        row.addWidget(self.engrave_btn)

        self.set_completed(completed)

    def set_completed(self, value: bool) -> None:
        self.completed = value
        self.status_label.setText("✓" if value else "○")
        self.status_label.setStyleSheet(
            "font-size: 16px; color: #10B981; font-weight: 700;"
            if value
            else "font-size: 16px; color: #9CA3AF;"
        )
