from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

from lbb.adapters.lightburn_fake import LightBurnFake
from lbb.adapters.pdfium_reader import PdfiumReader
from lbb.adapters.sqlite_repo import SqliteProfileRepository
from lbb.app.pipeline import PipelineDeps
from lbb.core.models import Material, Sku, SkuProfile, Template
from lbb.ui.main_window import MainWindow

REPO_ROOT = Path(__file__).parents[2]
PDF_DEMO = REPO_ROOT / "tests" / "fixtures" / "pdfs" / "LB-WALLET-LEATHER-S__demo.pdf"
TEMPLATE = REPO_ROOT / "templates" / "wallet-small.lbrn2"


@pytest.fixture
def deps(tmp_path):
    repo = SqliteProfileRepository(tmp_path / "p.sqlite")
    t = repo.upsert_template(
        Template(
            id=0, name="Wallet — Small", lbrn2_path=str(TEMPLATE), canvas_w_mm=95, canvas_h_mm=110
        )
    )
    m = repo.upsert_material(
        Material(id=0, name="Leather 2mm", clb_library="default.clb", clb_entry="LeatherVT")
    )
    repo.upsert(SkuProfile(sku=Sku("LB-WALLET-LEATHER-S"), template=t, material=m, overrides={}))
    return PipelineDeps(
        repo=repo,
        pdf=PdfiumReader(),
        lightburn=LightBurnFake(),
        temp_dir=tmp_path / "out",
    )


def test_constructs_with_home_view_visible(qtbot, deps):
    window = MainWindow(deps)
    qtbot.addWidget(window)
    assert window.stack.currentWidget() is window.home


def test_dropping_known_sku_switches_to_preview(qtbot, deps):
    window = MainWindow(deps)
    qtbot.addWidget(window)
    window.home.pdf_chosen.emit(PDF_DEMO)
    assert window.stack.currentWidget() is window.preview
    assert window.preview.send.isEnabled()
    assert "LB-WALLET-LEATHER-S" in window.preview.sku_label.text()


def test_filename_stem_matches_registered_sku_skips_picker(qtbot, deps, tmp_path, monkeypatch):
    """When the filename stem itself is a registered SKU (no `__` delimiter),
    drop should auto-flow to preview without invoking the picker. Covers the
    case where customer order IDs are registered directly as SKUs in the DB."""
    auto_pdf = tmp_path / "LB-WALLET-LEATHER-S.pdf"  # stem matches seeded SKU
    auto_pdf.write_bytes(PDF_DEMO.read_bytes())

    # Track whether the picker was invoked. If lenient lookup works, it must
    # not be called.
    picker_calls: list = []

    def fake_picker(self, path):
        picker_calls.append(path)

    monkeypatch.setattr(MainWindow, "_prompt_for_sku", fake_picker)

    window = MainWindow(deps)
    qtbot.addWidget(window)
    window.home.pdf_chosen.emit(auto_pdf)

    assert picker_calls == [], "picker must not be invoked when stem is a registered SKU"
    assert window.stack.currentWidget() is window.preview
    assert "LB-WALLET-LEATHER-S" in window.preview.sku_label.text()


def test_no_sku_in_filename_invokes_picker_and_flows_to_preview(qtbot, deps, tmp_path, monkeypatch):
    """A PDF without `<SKU>__` in the filename must route through the SKU picker
    (mocked here) and then continue to the preview screen with the chosen profile."""
    # Copy demo PDF to a filename without the `__` delimiter (mimics a real
    # customer-order-numbered file like 304-4865183-6105121.pdf).
    no_sku_pdf = tmp_path / "client-order-12345.pdf"
    no_sku_pdf.write_bytes(PDF_DEMO.read_bytes())

    window = MainWindow(deps)
    qtbot.addWidget(window)

    chosen = deps.repo.get(Sku("LB-WALLET-LEATHER-S"))
    monkeypatch.setattr(MainWindow, "_prompt_for_sku", lambda self, path: chosen)

    window.home.pdf_chosen.emit(no_sku_pdf)
    assert window.stack.currentWidget() is window.preview
    assert "LB-WALLET-LEATHER-S" in window.preview.sku_label.text()


def test_send_after_picker_dispatches_to_lightburn(qtbot, deps, tmp_path, monkeypatch):
    """End-to-end: dropping a no-SKU PDF → picker → Send must successfully
    dispatch to LightBurn. Regression for: picker resolves the profile but
    Send re-extracts from filename and fails."""
    no_sku_pdf = tmp_path / "client-order-77.pdf"
    no_sku_pdf.write_bytes(PDF_DEMO.read_bytes())

    window = MainWindow(deps)
    qtbot.addWidget(window)
    chosen = deps.repo.get(Sku("LB-WALLET-LEATHER-S"))
    monkeypatch.setattr(MainWindow, "_prompt_for_sku", lambda self, path: chosen)
    # Suppress the post-Send success dialog so the test doesn't block.
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **kw: None)

    window.home.pdf_chosen.emit(no_sku_pdf)
    assert window.stack.currentWidget() is window.preview
    assert window.preview.send.isEnabled()

    window.preview.send.click()
    # After the direct-open pivot, the source PDF itself is what was loaded
    # into LightBurn (not a generated .lbrn2).
    assert deps.lightburn.loaded == [no_sku_pdf]


def test_no_sku_in_filename_picker_cancel_stays_on_home(
    qtbot, deps, tmp_path, monkeypatch
):
    """Cancelling the SKU picker leaves the operator on the home screen — no preview."""
    no_sku_pdf = tmp_path / "order-99.pdf"
    no_sku_pdf.write_bytes(PDF_DEMO.read_bytes())

    window = MainWindow(deps)
    qtbot.addWidget(window)

    monkeypatch.setattr(MainWindow, "_prompt_for_sku", lambda self, path: None)
    window.home.pdf_chosen.emit(no_sku_pdf)
    assert window.stack.currentWidget() is window.home


def test_cancel_from_preview_returns_to_home(qtbot, deps):
    window = MainWindow(deps)
    qtbot.addWidget(window)
    window.home.pdf_chosen.emit(PDF_DEMO)
    assert window.stack.currentWidget() is window.preview
    window.preview.cancel.click()
    assert window.stack.currentWidget() is window.home
