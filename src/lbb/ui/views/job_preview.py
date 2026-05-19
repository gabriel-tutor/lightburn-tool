from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from lbb.core.models import SkuProfile
from lbb.core.preflight import PreflightResult

_THUMB_PX = 380


class JobPreviewView(QWidget):
    """Pre-send confirmation screen. Send button is gated by preflight.ok."""

    send_requested = Signal()
    cancel_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 22)
        outer.setSpacing(20)

        # ── Body: thumbnail card (left) + metadata column (right) ─────────
        body = QHBoxLayout()
        body.setSpacing(28)

        thumb_card = QFrame()
        thumb_card.setObjectName("previewThumbCard")
        thumb_layout = QVBoxLayout(thumb_card)
        thumb_layout.setContentsMargins(12, 12, 12, 12)
        self.thumb = QLabel("Loading…")
        self.thumb.setFixedSize(_THUMB_PX, _THUMB_PX)
        self.thumb.setAlignment(Qt.AlignCenter)
        self.thumb.setStyleSheet("background: transparent; border: none; color: #8A92A6;")
        thumb_layout.addWidget(self.thumb)
        body.addWidget(thumb_card)

        body.addLayout(self._build_metadata_column(), stretch=1)
        outer.addLayout(body, stretch=1)

        # ── Footer: cancel + send ─────────────────────────────────────────
        footer = QHBoxLayout()
        self.cancel = QPushButton("Cancel")
        self.cancel.setObjectName("ghostButton")
        self.cancel.clicked.connect(self.cancel_requested.emit)
        self.send = QPushButton("Open in LightBurn  →")
        self.send.setObjectName("sendButton")
        self.send.clicked.connect(self.send_requested.emit)
        footer.addStretch()
        footer.addWidget(self.cancel)
        footer.addWidget(self.send)
        outer.addLayout(footer)

    def _build_metadata_column(self) -> QVBoxLayout:
        right = QVBoxLayout()
        right.setSpacing(4)

        right.addWidget(_section_label("SKU detected"))
        self.sku_label = QLabel()
        self.sku_label.setObjectName("monoCode")
        right.addWidget(self.sku_label)

        right.addSpacing(20)
        right.addWidget(_section_label("Product template"))
        self.template_label = QLabel()
        self.template_label.setStyleSheet("font-size: 14px;")
        right.addWidget(self.template_label)
        self.template_size_label = QLabel()
        self.template_size_label.setObjectName("dim")
        self.template_size_label.setStyleSheet("font-size: 12px;")
        right.addWidget(self.template_size_label)

        right.addSpacing(20)
        right.addWidget(_section_label("Material profile"))
        self.material_label = QLabel()
        self.material_label.setStyleSheet("font-size: 14px;")
        right.addWidget(self.material_label)
        self.material_detail = QLabel()
        self.material_detail.setObjectName("dim")
        self.material_detail.setStyleSheet("font-size: 12px;")
        right.addWidget(self.material_detail)

        # ── Direct-Open instruction block (2026-05-19 pivot) ────────────────
        # LightBurn now imports the raw PDF, so the operator must manually
        # assign cut layers. This label tells them which colour maps to which
        # layer so they don't have to remember.
        right.addSpacing(20)
        right.addWidget(_section_label("Layer setup in LightBurn"))
        self.layer_setup_label = QLabel()
        self.layer_setup_label.setObjectName("layerSetup")
        self.layer_setup_label.setWordWrap(True)
        right.addWidget(self.layer_setup_label)

        right.addStretch()

        self.preflight_label = QLabel()
        self.preflight_label.setWordWrap(True)
        self.preflight_label.setStyleSheet("font-size: 13px;")
        right.addWidget(self.preflight_label)
        return right

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
            self.thumb.setText("no preview")

        self.sku_label.setText(profile.sku.value)
        self.template_label.setText(profile.template.name)
        self.template_size_label.setText(
            f"{profile.template.canvas_w_mm:.0f} × {profile.template.canvas_h_mm:.0f} mm canvas"
        )
        self.material_label.setText(profile.material.name)
        self.material_detail.setText(
            f"{profile.material.clb_library}  →  {profile.material.clb_entry}"
        )

        # Hardcoded to the wallet template's C00/C01 cut settings for MVP.
        # Future enhancement: parse profile.template.lbrn2_path's CutSetting
        # elements at populate-time so each SKU shows its own layer setup.
        self.layer_setup_label.setText(
            "After import, select shapes in LightBurn and assign:\n"
            "  •  Black strokes  →  C00 (Cut)       1000 mm/min · 20%\n"
            "  •  Blue strokes   →  C01 (Engrave)   50 mm/sec · 15%\n"
            f"Material library: {profile.material.clb_library} → {profile.material.clb_entry}"
        )

        if preflight.ok:
            self.preflight_label.setText("✓  All preflight checks passed")
            self.preflight_label.setObjectName("statusOk")
            self.send.setEnabled(True)
        else:
            bullets = "\n".join(f"  •  {r}" for r in preflight.reasons)
            self.preflight_label.setText(f"✕  Preflight failed:\n{bullets}")
            self.preflight_label.setObjectName("statusError")
            self.send.setEnabled(False)

        self.preflight_label.style().unpolish(self.preflight_label)
        self.preflight_label.style().polish(self.preflight_label)


def _section_label(text: str) -> QLabel:
    """A small, all-caps label that introduces a metadata block."""
    label = QLabel(text)
    label.setObjectName("sectionLabel")
    return label
