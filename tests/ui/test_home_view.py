from pathlib import Path

from lbb.ui.views.home import HomeView


def test_constructs_without_crashing(qtbot):
    view = HomeView()
    qtbot.addWidget(view)


def test_relays_pdf_dropped_to_pdf_chosen(qtbot, tmp_path):
    pdf = tmp_path / "LB-X__y.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    view = HomeView()
    qtbot.addWidget(view)

    received: list[Path] = []
    view.pdf_chosen.connect(received.append)
    view.zone.pdf_dropped.emit(pdf)

    assert received == [pdf]


def test_no_status_pill_in_header(qtbot):
    """Direct-open architecture: no LightBurn connection status to display."""
    view = HomeView()
    qtbot.addWidget(view)
    # The widget that used to be `view.status` no longer exists.
    assert not hasattr(view, "status")
