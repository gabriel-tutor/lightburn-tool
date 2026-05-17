from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent, QMouseEvent
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class DropZone(QFrame):
    """The big drop target on the home screen.

    Accepts drag-and-dropped PDFs and emits `pdf_dropped(Path)`. The frame's
    `active` property flips True during a valid drag so QSS can highlight it.

    Also acts as a click target: a left-click anywhere on the zone emits
    `browse_requested` so the controller can open a file picker — the always-
    works fallback when OS-level drag-drop is finicky.
    """

    pdf_dropped = Signal(Path)
    browse_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        label = QLabel("⤓  Drop PDF here\nor click to browse\n\nfilename must contain SKU")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

    def _set_active(self, active: bool) -> None:
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if any(u.toLocalFile().lower().endswith(".pdf") for u in event.mimeData().urls()):
            event.acceptProposedAction()
            self._set_active(True)

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._set_active(False)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.browse_requested.emit()
            event.accept()
        else:
            super().mousePressEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        for u in event.mimeData().urls():
            local = u.toLocalFile()
            if local.lower().endswith(".pdf"):
                self.pdf_dropped.emit(Path(local))
                break
        self._set_active(False)
