from pathlib import Path

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

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

        # Header row: title left, status pill right.
        header = QHBoxLayout()
        title = QLabel("◐  LightBurn Bridge")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.status = StatusPill()
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.status)
        layout.addLayout(header)

        # Main drop zone.
        self.zone = DropZone()
        self.zone.pdf_dropped.connect(self.pdf_chosen.emit)
        layout.addWidget(self.zone, stretch=1)

        # Footer nav.
        footer = QHBoxLayout()
        admin_btn = QPushButton("⚙  Admin")
        admin_btn.clicked.connect(self.open_admin.emit)
        audit_btn = QPushButton("📋  Audit")
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
