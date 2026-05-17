from pathlib import Path

from lbb.adapters.lightburn_fake import LightBurnFake
from lbb.ui.views.home import HomeView


def test_constructs_without_crashing(qtbot):
    view = HomeView(LightBurnFake())
    qtbot.addWidget(view)


def test_relays_pdf_dropped_to_pdf_chosen(qtbot, tmp_path):
    pdf = tmp_path / "LB-X__y.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    view = HomeView(LightBurnFake())
    qtbot.addWidget(view)

    received: list[Path] = []
    view.pdf_chosen.connect(received.append)
    view.zone.pdf_dropped.emit(pdf)

    assert received == [pdf]


def test_status_pill_reflects_lightburn_running_state(qtbot):
    view = HomeView(LightBurnFake(running=True))
    qtbot.addWidget(view)
    view._poll()
    assert view.status.objectName() == "statusOk"

    view_down = HomeView(LightBurnFake(running=False))
    qtbot.addWidget(view_down)
    view_down._poll()
    assert view_down.status.objectName() == "statusError"
