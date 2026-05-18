from pathlib import Path

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from lbb.ports.lightburn import LightBurnPort
from lbb.ui.widgets.drop_zone import DropZone
from lbb.ui.widgets.status_pill import StatusPill

_POLL_INTERVAL_MS = 2000


class HomeView(QWidget):
    """The operator's primary screen — drop zone + status pill + nav."""

    pdf_chosen = Signal(Path)
    open_admin = Signal()
    open_audit = Signal()

    def __init__(self, lightburn: LightBurnPort) -> None:
        super().__init__()
        self._lb = lightburn

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(20)

        # ── Header: two-tone wordmark (left) + status pill (right) ────────
        header = QHBoxLayout()
        header.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        brand = QLabel("LightBurn")
        brand.setObjectName("wordmark")
        sub = QLabel("Bridge")
        sub.setObjectName("wordmarkAccent")
        title_row.addWidget(brand)
        title_row.addWidget(sub)

        header.addLayout(title_row)
        header.addStretch()
        self.status = StatusPill()
        header.addWidget(self.status)
        layout.addLayout(header)

        # ── Drop zone fills the rest of the screen ────────────────────────
        self.zone = DropZone()
        self.zone.pdf_dropped.connect(self.pdf_chosen.emit)
        self.zone.browse_requested.connect(self._open_browse_dialog)
        layout.addWidget(self.zone, stretch=1)

        # ── Footer nav — ghost-style, right-aligned ───────────────────────
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
        layout.addLayout(footer)

        # PING poll: keep the status pill honest about LightBurn's state.
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(_POLL_INTERVAL_MS)
        self._poll()

    def _poll(self) -> None:
        self.status.set_running(self._lb.is_running())

    def _open_browse_dialog(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Choose a PDF",
            str(Path.home()),
            "PDF files (*.pdf)",
        )
        if path_str:
            self.pdf_chosen.emit(Path(path_str))
