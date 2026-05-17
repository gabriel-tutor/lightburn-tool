from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from lbb.core.models import SkuProfile
from lbb.core.preflight import PreflightResult

_THUMB_PX = 360


class JobPreviewView(QWidget):
    """Pre-send confirmation screen. Send button is gated by preflight.ok."""

    send_requested = Signal()
    cancel_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)

        # Body — thumbnail (left) + metadata (right).
        body = QHBoxLayout()

        self.thumb = QLabel("Loading…")
        self.thumb.setFixedSize(_THUMB_PX, _THUMB_PX)
        self.thumb.setAlignment(Qt.AlignCenter)
        self.thumb.setStyleSheet(
            "background: #141821; border: 1px solid #252A38; border-radius: 8px;"
        )
        body.addWidget(self.thumb)

        right = QVBoxLayout()
        right.addWidget(QLabel("SKU detected"))
        self.sku_label = QLabel()
        self.sku_label.setStyleSheet("font-size: 20px; font-weight: 600; color: #7DD3FC;")
        right.addWidget(self.sku_label)

        right.addSpacing(12)
        right.addWidget(QLabel("Product template"))
        self.template_label = QLabel()
        right.addWidget(self.template_label)

        right.addSpacing(12)
        right.addWidget(QLabel("Material profile"))
        self.material_label = QLabel()
        right.addWidget(self.material_label)
        self.material_detail = QLabel()
        self.material_detail.setStyleSheet("color: #94A3B8;")
        right.addWidget(self.material_detail)

        right.addStretch()
        self.preflight_label = QLabel()
        self.preflight_label.setWordWrap(True)
        right.addWidget(self.preflight_label)

        body.addLayout(right, stretch=1)
        outer.addLayout(body, stretch=1)

        # Footer — Cancel + Send.
        footer = QHBoxLayout()
        self.cancel = QPushButton("✕  Cancel")
        self.cancel.clicked.connect(self.cancel_requested.emit)
        self.send = QPushButton("⏎  Send →")
        self.send.setObjectName("sendButton")
        self.send.clicked.connect(self.send_requested.emit)
        footer.addStretch()
        footer.addWidget(self.cancel)
        footer.addWidget(self.send)
        outer.addLayout(footer)

    def populate(
        self,
        *,
        thumbnail_png: bytes,
        profile: SkuProfile,
        preflight: PreflightResult,
    ) -> None:
        pix = QPixmap()
        pix.loadFromData(thumbnail_png, "PNG")
        if not pix.isNull():
            self.thumb.setPixmap(
                pix.scaled(self.thumb.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            self.thumb.setText("(no preview)")

        self.sku_label.setText(profile.sku.value)
        self.template_label.setText(
            f"{profile.template.name}  "
            f"({profile.template.canvas_w_mm:.0f} × {profile.template.canvas_h_mm:.0f} mm)"
        )
        self.material_label.setText(profile.material.name)
        self.material_detail.setText(
            f"Library: {profile.material.clb_library}    Entry: {profile.material.clb_entry}"
        )

        if preflight.ok:
            self.preflight_label.setText("✓ All preflight checks passed")
            self.preflight_label.setObjectName("statusOk")
            self.send.setEnabled(True)
        else:
            bullets = "\n".join(f"  • {r}" for r in preflight.reasons)
            self.preflight_label.setText(f"✕ Preflight failed:\n{bullets}")
            self.preflight_label.setObjectName("statusError")
            self.send.setEnabled(False)

        # Re-apply QSS after objectName change.
        self.preflight_label.style().unpolish(self.preflight_label)
        self.preflight_label.style().polish(self.preflight_label)
