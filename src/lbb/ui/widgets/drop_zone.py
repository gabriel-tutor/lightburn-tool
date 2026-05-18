from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent, QMouseEvent
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class DropZone(QFrame):
    """The marquee surface of the home screen: drop PDF or click to browse.

    Layout:
        ┌──────────────────────────────────┐
        │                                  │
        │              [↓]                 │   ← oversize chevron-down
        │                                  │
        │       Drop a PDF here            │   ← display-weight heading
        │       or click to browse         │   ← muted subtitle
        │                                  │
        │    LB-SKU-CODE__name.pdf         │   ← mono helper
        │                                  │
        └──────────────────────────────────┘
    """

    pdf_dropped = Signal(Path)
    browse_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(14)

        # Large iconographic glyph. Unicode chevron is consistent across
        # platforms once font weight is set; SVG would be cleaner but adds
        # a packaging step.
        icon = QLabel("⌄")
        icon.setObjectName("dropIcon")
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedHeight(72)

        title = QLabel("Drop a PDF here")
        title.setObjectName("dropTitle")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("or click to browse")
        subtitle.setObjectName("dropSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)

        # Two-line block: helper hint + filename example. Spacers between
        # the heading and the helper give the zone its sense of generosity.
        helper = QLabel("filename must include SKU, e.g.")
        helper.setObjectName("dropHelper")
        helper.setAlignment(Qt.AlignCenter)

        example = QLabel("LB-WALLET-LEATHER-S__name.pdf")
        example.setObjectName("dropHelper")
        example.setAlignment(Qt.AlignCenter)
        example.setStyleSheet("color: #7DD3FC;")

        layout.addStretch()
        layout.addWidget(icon)
        layout.addSpacing(2)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(24)
        layout.addWidget(helper)
        layout.addWidget(example)
        layout.addStretch()

    def _set_active(self, active: bool) -> None:
        self.setProperty("active", active)
        # Re-apply QSS so the [active="true"] selector takes effect.
        self.style().unpolish(self)
        self.style().polish(self)
        # Children inherit the property selector, so re-polish them too.
        for child in self.findChildren(QLabel):
            child.style().unpolish(child)
            child.style().polish(child)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.browse_requested.emit()
            event.accept()
        else:
            super().mousePressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if any(u.toLocalFile().lower().endswith(".pdf") for u in event.mimeData().urls()):
            event.acceptProposedAction()
            self._set_active(True)

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._set_active(False)

    def dropEvent(self, event: QDropEvent) -> None:
        for u in event.mimeData().urls():
            local = u.toLocalFile()
            if local.lower().endswith(".pdf"):
                self.pdf_dropped.emit(Path(local))
                break
        self._set_active(False)
