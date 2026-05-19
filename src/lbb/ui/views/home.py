from importlib.resources import files
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from lbb.ui.widgets.drop_zone import DropZone

_LOGO_HEIGHT = 32  # px — header logo display size


class HomeView(QWidget):
    """The operator's primary screen — drop zone + brand header + nav.

    No status pill: the direct-open flow invokes LightBurn (launching it
    if needed), so there's nothing to "connect to" up-front and the
    status would only be noise.
    """

    pdf_chosen = Signal(Path)
    open_admin = Signal()
    open_audit = Signal()

    def __init__(self) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(20)

        # ── Header: Flanacom logo (left) + "Engraver" subtitle ────────────
        header = QHBoxLayout()
        header.setSpacing(12)

        logo_label = QLabel()
        logo_label.setObjectName("brandLogo")
        logo_pixmap = QPixmap()
        # Logo PNG bundled inside the package so importlib.resources finds
        # it in dev AND in the PyInstaller one-folder bundle.
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

    def _open_browse_dialog(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Choose a PDF",
            str(Path.home()),
            "PDF files (*.pdf)",
        )
        if path_str:
            self.pdf_chosen.emit(Path(path_str))
