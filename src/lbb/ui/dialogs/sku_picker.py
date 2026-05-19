"""SKU fallback picker dialog.

Opens when the operator drops a PDF whose filename has no `<SKU>__` prefix
(e.g., a customer-order-numbered file like `304-4865183-6105121.pdf`). Lets
the operator pick the product manually; the rest of the pipeline proceeds
exactly as if the SKU had been auto-extracted from the filename.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

from lbb.core.models import SkuProfile
from lbb.ports.repository import ProfileRepository


class SkuPickerDialog(QDialog):
    """Modal SKU picker. After accept, `chosen_profile` is the selected SkuProfile
    (or remains None on cancel / empty DB)."""

    def __init__(self, repo: ProfileRepository, filename: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pick SKU")
        self.setModal(True)
        self.chosen_profile: SkuProfile | None = None

        profiles = sorted(repo.list_profiles(), key=lambda p: p.sku.value)
        self._profiles = profiles

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        header = QLabel("Couldn't detect a SKU from the filename")
        header.setStyleSheet("font-size: 14px; font-weight: 600;")
        layout.addWidget(header)

        self.filename_label = QLabel(f"File: {filename}")
        self.filename_label.setObjectName("dim")
        self.filename_label.setStyleSheet("font-size: 12px;")
        self.filename_label.setWordWrap(True)
        layout.addWidget(self.filename_label)

        self.empty_state_label = QLabel("")
        self.empty_state_label.setStyleSheet("font-size: 12px; color: #B0463E;")
        self.empty_state_label.setWordWrap(True)
        layout.addWidget(self.empty_state_label)

        layout.addSpacing(4)
        layout.addWidget(QLabel("Pick the product:"))

        self.combo = QComboBox()
        for profile in profiles:
            self.combo.addItem(
                f"{profile.sku.value} — {profile.template.name}",
                userData=profile,
            )
        layout.addWidget(self.combo)

        layout.addSpacing(8)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        self.ok_btn = buttons.button(QDialogButtonBox.Ok)
        self.ok_btn.setText("Use SKU  →")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if not profiles:
            self.empty_state_label.setText(
                "No SKUs configured. Open Admin to add a product mapping first."
            )
            self.combo.setEnabled(False)
            self.ok_btn.setEnabled(False)

        self.resize(420, self.sizeHint().height())

    def _on_accept(self) -> None:
        idx = self.combo.currentIndex()
        if idx < 0 or not self._profiles:
            self.reject()
            return
        self.chosen_profile = self.combo.itemData(idx, Qt.UserRole)
        self.accept()

    # ── Test seam ──────────────────────────────────────────────────────────
    def select_sku(self, sku_code: str) -> SkuProfile | None:
        """Pick the entry whose SKU code matches `sku_code`, accept the dialog,
        and return the chosen profile. Returns None if no match.

        Used by tests in lieu of driving the modal interactively."""
        for i in range(self.combo.count()):
            profile = self.combo.itemData(i, Qt.UserRole)
            if profile is not None and profile.sku.value == sku_code:
                self.combo.setCurrentIndex(i)
                self._on_accept()
                return self.chosen_profile
        return None
