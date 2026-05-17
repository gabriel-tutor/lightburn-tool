"""Admin screen — manage SKU → template/material mappings.

Templates and materials themselves are engineering's domain (templates are
hand-authored in LightBurn; materials reference the laser engineer's existing
Material Library). The admin's job is the *mapping* between them and SKUs.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from lbb.core.models import Sku, SkuProfile
from lbb.ports.repository import ProfileRepository


class AdminView(QWidget):
    """Read-only SKU table + Add SKU dialog + Back navigation."""

    back_requested = Signal()

    def __init__(self, repo: ProfileRepository) -> None:
        super().__init__()
        self._repo = repo

        outer = QVBoxLayout(self)

        # Header row with title + Back button.
        header = QHBoxLayout()
        title = QPushButton("← Back")
        title.setFlat(True)
        title.clicked.connect(self.back_requested.emit)
        self.back_btn = title
        header.addWidget(title)
        header.addStretch()
        outer.addLayout(header)

        # SKU table.
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["SKU", "Template", "Material"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        outer.addWidget(self.table, stretch=1)

        # Action buttons.
        actions = QHBoxLayout()
        add = QPushButton("+ Add SKU")
        add.clicked.connect(self._open_add_dialog)
        actions.addStretch()
        actions.addWidget(add)
        outer.addLayout(actions)

        self._refresh()

    # ── Public test seams ───────────────────────────────────────────────────

    def sku_rows(self) -> list[dict[str, str]]:
        """Snapshot the current table state (one dict per row). For tests."""
        rows = []
        for r in range(self.table.rowCount()):
            rows.append(
                {
                    "sku": self.table.item(r, 0).text(),
                    "template": self.table.item(r, 1).text(),
                    "material": self.table.item(r, 2).text(),
                }
            )
        return rows

    def add_sku(self, sku_code: str, *, template_name: str, material_name: str) -> None:
        """Add a SKU profile by template + material name. Raises if either is missing."""
        templates = {t.name: t for t in self._repo.list_templates()}
        materials = {m.name: m for m in self._repo.list_materials()}
        if template_name not in templates:
            raise ValueError(f"unknown template: {template_name}")
        if material_name not in materials:
            raise ValueError(f"unknown material: {material_name}")
        self._repo.upsert(
            SkuProfile(
                sku=Sku(sku_code),
                template=templates[template_name],
                material=materials[material_name],
                overrides={},
            )
        )
        self._refresh()

    # ── Internal ────────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        self.table.setRowCount(0)
        # The repo doesn't expose a list_skus() — for MVP we iterate via list_templates()
        # is wrong. We need to add list_skus to the Protocol. For now, query the DB
        # directly through the repo's connection — see _list_skus.
        for sku, template_name, material_name in self._list_skus():
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(sku))
            self.table.setItem(r, 1, QTableWidgetItem(template_name))
            self.table.setItem(r, 2, QTableWidgetItem(material_name))

    def _list_skus(self) -> list[tuple[str, str, str]]:
        """Inline SKU listing — TODO move to ProfileRepository.list_skus()."""
        # Best-effort: use the SQLite connection directly. The Protocol-shaped
        # repo doesn't expose this yet; production uses SqliteProfileRepository
        # which has _conn. Fall back to empty list for unknown impls.
        conn = getattr(self._repo, "_conn", None)
        if conn is None:
            return []
        return [
            (row["sku"], row["tname"], row["mname"])
            for row in conn.execute(
                """
                SELECT sp.sku, t.name AS tname, m.name AS mname
                FROM sku_profiles sp
                JOIN templates t ON t.id = sp.template_id
                JOIN materials m ON m.id = sp.material_id
                ORDER BY sp.sku
                """
            )
        ]

    def _open_add_dialog(self) -> None:
        dlg = _AddSkuDialog(
            self,
            template_names=[t.name for t in self._repo.list_templates()],
            material_names=[m.name for m in self._repo.list_materials()],
        )
        if dlg.exec() != QDialog.Accepted:
            return
        try:
            self.add_sku(
                dlg.sku_code,
                template_name=dlg.template_name,
                material_name=dlg.material_name,
            )
        except ValueError as e:
            QMessageBox.warning(self, "Couldn't add SKU", str(e))


class _AddSkuDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        *,
        template_names: list[str],
        material_names: list[str],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add SKU")
        layout = QFormLayout(self)
        self._sku_edit = QLineEdit()
        self._sku_edit.setPlaceholderText("e.g. LB-WALLET-LEATHER-S")
        layout.addRow("SKU code", self._sku_edit)
        self._template_combo = QComboBox()
        self._template_combo.addItems(template_names)
        layout.addRow("Template", self._template_combo)
        self._material_combo = QComboBox()
        self._material_combo.addItems(material_names)
        layout.addRow("Material", self._material_combo)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        # Place focus on the SKU code field.
        self._sku_edit.setFocus(Qt.OtherFocusReason)

    @property
    def sku_code(self) -> str:
        return self._sku_edit.text().strip()

    @property
    def template_name(self) -> str:
        return self._template_combo.currentText()

    @property
    def material_name(self) -> str:
        return self._material_combo.currentText()
