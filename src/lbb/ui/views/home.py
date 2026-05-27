"""Home screen — search-first.

The operator's primary interaction is **order lookup**: type an order number
(or pick from the recent-orders list) and the app navigates to that order's
view. PDFs aren't dragged in any more — they live in the orders folder
(simulating Supabase/Airtable) and the order data references them by path.

If `orders` is None or empty, the recent-orders area shows an empty-state
message and the search field still works (just always returns "not found").
"""

from __future__ import annotations

from importlib.resources import files

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from lbb.core.order import Order
from lbb.ports.orders import OrderRepository

_LOGO_HEIGHT = 32


class HomeView(QWidget):
    """Search + recent orders. No drop zone — see 2026-05-26 spec for why."""

    order_searched = Signal(str)        # operator typed and submitted
    order_selected = Signal(object)     # operator clicked a recent-orders card
    open_admin = Signal()
    open_audit = Signal()

    def __init__(self, orders_repo: OrderRepository | None = None) -> None:
        super().__init__()
        self._orders_repo = orders_repo

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(18)

        layout.addLayout(self._build_header())
        layout.addLayout(self._build_search_row())

        self.search_error = QLabel("")
        self.search_error.setObjectName("statusError")
        self.search_error.setVisible(False)
        layout.addWidget(self.search_error)

        layout.addSpacing(4)
        layout.addWidget(_section_label("Recent orders"))

        self.recent_box = QFrame()
        self.recent_box.setObjectName("itemsBox")
        self.recent_layout = QVBoxLayout(self.recent_box)
        self.recent_layout.setContentsMargins(0, 4, 0, 4)
        self.recent_layout.setSpacing(8)
        layout.addWidget(self.recent_box, stretch=1)
        self._recent_cards: list[_OrderCard] = []

        layout.addLayout(self._build_footer())

        self.refresh_recent()
        self.search_input.setFocus()

    # ── Public API ──────────────────────────────────────────────────────────

    def refresh_recent(self) -> None:
        for card in self._recent_cards:
            self.recent_layout.removeWidget(card)
            card.setParent(None)
        self._recent_cards.clear()

        orders: list[Order] = (
            self._orders_repo.list_all() if self._orders_repo is not None else []
        )
        if not orders:
            empty = QLabel(
                "No orders yet. Add some via your order backend, or edit\n"
                "~/.flanacom-tool/orders/orders.json"
            )
            empty.setObjectName("dim")
            empty.setStyleSheet("font-size: 12px;")
            empty.setAlignment(Qt.AlignCenter)
            self.recent_layout.addWidget(empty)
            self._recent_cards.append(empty)  # type: ignore[arg-type]
            return

        for order in orders:
            card = _OrderCard(order)
            card.clicked.connect(lambda o=order: self.order_selected.emit(o))
            self.recent_layout.addWidget(card)
            self._recent_cards.append(card)

    def show_not_found(self, order_number: str) -> None:
        self.search_error.setText(f"Order \"{order_number}\" not found.")
        self.search_error.setVisible(True)
        self.search_input.setFocus()
        self.search_input.selectAll()

    def hide_search_error(self) -> None:
        self.search_error.setVisible(False)
        self.search_error.setText("")

    def recent_order_numbers(self) -> list[str]:
        """Test seam — returns the order numbers currently rendered."""
        return [
            card.order.order_number
            for card in self._recent_cards
            if isinstance(card, _OrderCard)
        ]

    # ── Internal builders ───────────────────────────────────────────────────

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(12)

        logo_label = QLabel()
        logo_label.setObjectName("brandLogo")
        logo_pixmap = QPixmap()
        logo_bytes = (files("lbb.ui.assets") / "flanacom-logo.png").read_bytes()
        logo_pixmap.loadFromData(logo_bytes, "PNG")
        if not logo_pixmap.isNull():
            scaled = logo_pixmap.scaledToHeight(_LOGO_HEIGHT, Qt.SmoothTransformation)
            logo_label.setPixmap(scaled)
        else:
            logo_label.setText("FLANACOM")
            logo_label.setObjectName("wordmark")

        subtitle = QLabel("Engraver")
        subtitle.setObjectName("wordmarkAccent")

        header.addWidget(logo_label)
        header.addWidget(subtitle)
        header.addStretch()
        return header

    def _build_search_row(self) -> QVBoxLayout:
        container = QVBoxLayout()
        container.setSpacing(6)
        container.addWidget(_section_label("Find an order"))

        row = QHBoxLayout()
        row.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("e.g.  305-6737580-7658721")
        self.search_input.returnPressed.connect(self._emit_search)
        self.search_input.textChanged.connect(self.hide_search_error)
        row.addWidget(self.search_input, stretch=1)
        self.open_btn = QPushButton("Open")
        self.open_btn.setObjectName("sendButton")
        self.open_btn.clicked.connect(self._emit_search)
        row.addWidget(self.open_btn)
        container.addLayout(row)
        return container

    def _build_footer(self) -> QHBoxLayout:
        footer = QHBoxLayout()
        admin_btn = QPushButton("Admin")
        admin_btn.setObjectName("ghostButton")
        admin_btn.clicked.connect(self.open_admin.emit)
        audit_btn = QPushButton("Audit")
        audit_btn.setObjectName("ghostButton")
        audit_btn.clicked.connect(self.open_audit.emit)
        footer.addStretch()
        footer.addWidget(admin_btn)
        footer.addWidget(audit_btn)
        return footer

    def _emit_search(self) -> None:
        text = self.search_input.text().strip()
        if not text:
            return
        self.order_searched.emit(text)


class _OrderCard(QFrame):
    """Clickable summary row for one order in the recent-orders list."""

    clicked = Signal()

    def __init__(self, order: Order) -> None:
        super().__init__()
        self.order = order
        self.setObjectName("orderItemRow")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)

        title = QLabel(order.order_number)
        title.setObjectName("monoCode")
        title.setStyleSheet("font-size: 13px;")
        layout.addWidget(title)

        bits: list[str] = [order.customer.name or "Unknown customer"]
        n = len(order.items)
        bits.append(f"{n} item{'s' if n != 1 else ''}")
        if order.placed_at is not None:
            bits.append(order.placed_at.strftime("%b %d"))
        sub = QLabel("  ·  ".join(bits))
        sub.setObjectName("dim")
        sub.setStyleSheet("font-size: 12px;")
        layout.addWidget(sub)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 — Qt naming
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("sectionLabel")
    return lbl
