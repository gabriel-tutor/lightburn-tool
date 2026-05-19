"""Tests for the SKU fallback picker dialog.

This dialog opens when the operator drops a PDF whose filename doesn't carry
a `<SKU>__` prefix (e.g., customer-order-numbered files like
`304-4865183-6105121.pdf`). The operator picks the product manually; the rest
of the pipeline proceeds unchanged.
"""

import pytest

from lbb.adapters.sqlite_repo import SqliteProfileRepository
from lbb.core.models import Material, Sku, SkuProfile, Template
from lbb.ui.dialogs.sku_picker import SkuPickerDialog


@pytest.fixture
def repo_with_profiles(tmp_path) -> SqliteProfileRepository:
    repo = SqliteProfileRepository(tmp_path / "p.sqlite")
    t = repo.upsert_template(
        Template(
            id=0, name="Wallet — Small", lbrn2_path="/x.lbrn2",
            canvas_w_mm=95, canvas_h_mm=110,
        )
    )
    m = repo.upsert_material(
        Material(id=0, name="Leather 2mm", clb_library="default.clb", clb_entry="LeatherVT")
    )
    repo.upsert(SkuProfile(sku=Sku("LB-WALLET-LEATHER-S"), template=t, material=m, overrides={}))
    repo.upsert(SkuProfile(sku=Sku("LB-WALLET-LEATHER-M"), template=t, material=m, overrides={}))
    return repo


def test_picker_lists_all_registered_skus(qtbot, repo_with_profiles):
    """The combobox shows every registered SKU, sorted, with template hint."""
    dlg = SkuPickerDialog(repo_with_profiles, "304-4865183-6105121.pdf")
    qtbot.addWidget(dlg)
    items = [dlg.combo.itemText(i) for i in range(dlg.combo.count())]
    assert any("LB-WALLET-LEATHER-S" in t for t in items)
    assert any("LB-WALLET-LEATHER-M" in t for t in items)
    # Sorted
    assert items == sorted(items)


def test_picker_returns_selected_profile(qtbot, repo_with_profiles):
    """select_sku() is the test seam: choose by SKU code, accept, return profile."""
    dlg = SkuPickerDialog(repo_with_profiles, "x.pdf")
    qtbot.addWidget(dlg)
    chosen = dlg.select_sku("LB-WALLET-LEATHER-M")
    assert chosen is not None
    assert chosen.sku.value == "LB-WALLET-LEATHER-M"
    assert chosen.template.name == "Wallet — Small"


def test_picker_returns_none_on_cancel(qtbot, repo_with_profiles):
    """Rejecting the dialog leaves chosen_profile as None."""
    dlg = SkuPickerDialog(repo_with_profiles, "x.pdf")
    qtbot.addWidget(dlg)
    dlg.reject()
    assert dlg.chosen_profile is None


def test_picker_shows_dropped_filename(qtbot, repo_with_profiles):
    """The dialog tells the operator which file triggered the picker."""
    dlg = SkuPickerDialog(repo_with_profiles, "304-4865183-6105121.pdf")
    qtbot.addWidget(dlg)
    assert "304-4865183-6105121.pdf" in dlg.filename_label.text()


def test_picker_empty_state_disables_ok(qtbot, tmp_path):
    """No SKUs in DB → OK disabled, empty-state message visible."""
    repo = SqliteProfileRepository(tmp_path / "empty.sqlite")
    dlg = SkuPickerDialog(repo, "x.pdf")
    qtbot.addWidget(dlg)
    assert not dlg.ok_btn.isEnabled()
    empty = dlg.empty_state_label.text().lower()
    assert "no skus" in empty or "admin" in empty
