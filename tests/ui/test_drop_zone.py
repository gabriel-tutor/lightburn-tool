from pathlib import Path

from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtTest import QTest

from lbb.ui.widgets.drop_zone import DropZone


def test_emits_dropped_signal_for_pdf(qtbot, tmp_path):
    pdf = tmp_path / "LB-X__demo.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    zone = DropZone()
    qtbot.addWidget(zone)

    received: list[Path] = []
    zone.pdf_dropped.connect(received.append)

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(pdf))])
    pos = QPoint(10, 10)
    zone.dragEnterEvent(QDragEnterEvent(pos, Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier))
    zone.dropEvent(QDropEvent(pos, Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier))

    assert received == [pdf]


def test_left_click_emits_browse_requested(qtbot):
    zone = DropZone()
    qtbot.addWidget(zone)
    zone.resize(400, 300)
    zone.show()

    received: list[bool] = []
    zone.browse_requested.connect(lambda: received.append(True))

    QTest.mouseClick(zone, Qt.LeftButton, pos=QPoint(50, 50))

    assert received == [True]


def test_ignores_non_pdf_drops(qtbot, tmp_path):
    txt = tmp_path / "x.txt"
    txt.write_text("nope")
    zone = DropZone()
    qtbot.addWidget(zone)

    received: list[Path] = []
    zone.pdf_dropped.connect(received.append)

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(txt))])
    pos = QPoint(10, 10)
    zone.dropEvent(QDropEvent(pos, Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier))

    assert received == []
