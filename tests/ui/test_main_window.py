from pathlib import Path

import pytest

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


def test_cancel_from_preview_returns_to_home(qtbot, deps):
    window = MainWindow(deps)
    qtbot.addWidget(window)
    window.home.pdf_chosen.emit(PDF_DEMO)
    assert window.stack.currentWidget() is window.preview
    window.preview.cancel.click()
    assert window.stack.currentWidget() is window.home
