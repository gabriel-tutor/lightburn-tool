"""MainWindow flow tests — search-first redesign (2026-05-26).

Operator interacts via order-number search (not drag-drop). Tests construct
a minimal `JsonOrderRepository` and drive the flow through `home.order_searched`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

from lbb.adapters.json_orders import JsonOrderRepository
from lbb.adapters.lightburn_fake import LightBurnFake
from lbb.adapters.pdfium_reader import PdfiumReader
from lbb.adapters.sqlite_repo import SqliteProfileRepository
from lbb.app.pipeline import PipelineDeps
from lbb.core.models import Material, Sku, SkuProfile, Template
from lbb.ui.main_window import MainWindow

REPO_ROOT = Path(__file__).parents[2]
PDF_DEMO = REPO_ROOT / "tests" / "fixtures" / "pdfs" / "LB-WALLET-LEATHER-S__demo.pdf"
TEMPLATE = REPO_ROOT / "templates" / "wallet-small.lbrn2"


def _seed_orders(tmp_path: Path) -> Path:
    """Build a directory-based seed: orders.json + 3 design PDFs (copies of
    PDF_DEMO, since the test only needs valid PDFs)."""
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    (seed_dir / "305-A.pdf").write_bytes(PDF_DEMO.read_bytes())
    (seed_dir / "305-B.pdf").write_bytes(PDF_DEMO.read_bytes())
    (seed_dir / "304-A.pdf").write_bytes(PDF_DEMO.read_bytes())
    (seed_dir / "orders.json").write_text(
        json.dumps(
            {
                "orders": {
                    "305-MULTI": {
                        "customer": {"name": "Jane Doe"},
                        "items": [
                            {"item_id": "A", "sku": "LB-WALLET-LEATHER-S",
                             "customization": {"engraving_text": "John 2026"},
                             "pdf_path": "305-A.pdf"},
                            {"item_id": "B", "sku": "LB-WALLET-LEATHER-S",
                             "customization": {"engraving_text": "Jane 2026"},
                             "pdf_path": "305-B.pdf"},
                        ],
                    },
                    "304-SINGLE": {
                        "customer": {"name": "Maria"},
                        "items": [
                            {"item_id": "A", "sku": "LB-WALLET-LEATHER-S",
                             "customization": {"engraving_text": "III"},
                             "pdf_path": "304-A.pdf"}
                        ],
                    },
                }
            }
        )
    )
    return seed_dir


@pytest.fixture
def deps(tmp_path):
    repo = SqliteProfileRepository(tmp_path / "p.sqlite")
    t = repo.upsert_template(
        Template(
            id=0,
            name="Wallet — Small",
            lbrn2_path=str(TEMPLATE),
            canvas_w_mm=95,
            canvas_h_mm=110,
        )
    )
    m = repo.upsert_material(
        Material(id=0, name="Leather 2mm", clb_library="default.clb", clb_entry="LeatherVT")
    )
    repo.upsert(SkuProfile(sku=Sku("LB-WALLET-LEATHER-S"), template=t, material=m, overrides={}))
    seed = _seed_orders(tmp_path)
    orders_repo = JsonOrderRepository(tmp_path / "orders", seed_dir=seed)
    return PipelineDeps(
        repo=repo,
        pdf=PdfiumReader(),
        lightburn=LightBurnFake(),
        temp_dir=tmp_path / "out",
        orders=orders_repo,
    )


# ── Home + search ──────────────────────────────────────────────────────────


def test_constructs_with_home_view_visible(qtbot, deps):
    window = MainWindow(deps)
    qtbot.addWidget(window)
    assert window.stack.currentWidget() is window.home


def test_order_search_navigates_to_order_view(qtbot, deps):
    window = MainWindow(deps)
    qtbot.addWidget(window)
    window.home.order_searched.emit("305-MULTI")
    assert window.stack.currentWidget() is window.order_view
    assert "305-MULTI" in window.order_view.order_label.text()
    assert len(window.order_view.item_rows()) == 2


def test_unknown_order_search_shows_inline_error_stays_on_home(qtbot, deps):
    window = MainWindow(deps)
    qtbot.addWidget(window)
    window.home.order_searched.emit("999-DOES-NOT-EXIST")
    assert window.stack.currentWidget() is window.home
    assert not window.home.search_error.isHidden()
    assert "999-DOES-NOT-EXIST" in window.home.search_error.text()


def test_single_item_order_still_routes_to_order_view(qtbot, deps):
    """Per design: even single-item orders go through the order view."""
    window = MainWindow(deps)
    qtbot.addWidget(window)
    window.home.order_searched.emit("304-SINGLE")
    assert window.stack.currentWidget() is window.order_view
    assert len(window.order_view.item_rows()) == 1


def test_recent_orders_card_click_routes_to_order_view(qtbot, deps):
    """Operator can click a recent-orders card instead of typing."""
    order = deps.orders.get("305-MULTI")
    window = MainWindow(deps)
    qtbot.addWidget(window)
    window.home.order_selected.emit(order)
    assert window.stack.currentWidget() is window.order_view
    assert "305-MULTI" in window.order_view.order_label.text()


# ── Order → item → preview → send ──────────────────────────────────────────


def test_engraving_an_item_marks_it_complete_and_returns_to_order_view(
    qtbot, deps, monkeypatch
):
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **kw: None)
    monkeypatch.setattr(
        MainWindow, "_confirm_close_previous", lambda self, profile: "no"
    )

    window = MainWindow(deps)
    qtbot.addWidget(window)
    window.home.order_searched.emit("305-MULTI")
    window.order_view.engrave_button_for("A").click()
    assert window.stack.currentWidget() is window.preview
    window.preview.send.click()

    assert window.stack.currentWidget() is window.order_view
    rows = {r["item_id"]: r for r in window.order_view.item_rows()}
    assert rows["A"]["completed"] is True
    assert rows["B"]["completed"] is False


def test_close_prompt_fires_between_order_items(qtbot, deps, monkeypatch):
    """After engraving A, dispatching B fires the close-previous prompt
    (commit 4d13661 behaviour, preserved in the search-first flow)."""
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **kw: None)
    confirm_calls: list = []
    monkeypatch.setattr(
        MainWindow,
        "_confirm_close_previous",
        lambda self, profile: (confirm_calls.append(profile), "no")[1],
    )

    window = MainWindow(deps)
    qtbot.addWidget(window)
    window.home.order_searched.emit("305-MULTI")
    # First item: no prompt (first ever send)
    window.order_view.engrave_button_for("A").click()
    window.preview.send.click()
    assert confirm_calls == []
    # Second item: prompt fires
    window.order_view.engrave_button_for("B").click()
    window.preview.send.click()
    assert len(confirm_calls) == 1


def test_cancel_from_preview_returns_to_order_view(qtbot, deps):
    window = MainWindow(deps)
    qtbot.addWidget(window)
    window.home.order_searched.emit("305-MULTI")
    window.order_view.engrave_button_for("A").click()
    assert window.stack.currentWidget() is window.preview
    window.preview.cancel.click()
    assert window.stack.currentWidget() is window.order_view


def test_back_from_order_view_returns_to_home(qtbot, deps):
    window = MainWindow(deps)
    qtbot.addWidget(window)
    window.home.order_searched.emit("305-MULTI")
    window.order_view.back_btn.click()
    assert window.stack.currentWidget() is window.home
