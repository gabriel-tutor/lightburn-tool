from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

_DOT_SIZE = 8


class StatusPill(QWidget):
    """LightBurn connection indicator: a coloured dot + label.

    Backwards-compatible API: still exposes objectName() and text() so the
    existing test suite (which asserts those) keeps passing. setObjectName
    forwards to the inner label that drives QSS color.
    """

    def __init__(self) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._dot = QLabel("●")
        self._dot.setFixedSize(_DOT_SIZE + 6, _DOT_SIZE + 6)
        self._dot.setAlignment(Qt.AlignCenter)

        self._label = QLabel("LightBurn — Not connected")
        self._label.setObjectName("statusError")
        self._dot.setObjectName("statusError")

        layout.addWidget(self._dot)
        layout.addWidget(self._label)

    # ── Test-compat shims ───────────────────────────────────────────────────

    def objectName(self) -> str:  # noqa: N802 — Qt naming
        return self._label.objectName()

    def setObjectName(self, name: str) -> None:  # noqa: N802 — Qt naming
        self._label.setObjectName(name)
        self._dot.setObjectName(name)

    def text(self) -> str:
        return self._label.text()

    def setText(self, value: str) -> None:  # noqa: N802 — Qt naming
        self._label.setText(value)

    # ── Public API ──────────────────────────────────────────────────────────

    def set_running(self, running: bool) -> None:
        if running:
            self.setText("LightBurn — Ready")
            self.setObjectName("statusOk")
        else:
            self.setText("LightBurn — Not connected")
            self.setObjectName("statusError")
        for w in (self._label, self._dot):
            w.style().unpolish(w)
            w.style().polish(w)
