from lbb.ui.widgets.status_pill import StatusPill


def test_starts_disconnected(qtbot):
    p = StatusPill()
    qtbot.addWidget(p)
    assert p.objectName() == "statusError"
    assert "Not connected" in p.text()


def test_set_running_transitions_to_ready(qtbot):
    p = StatusPill()
    qtbot.addWidget(p)
    p.set_running(True)
    assert p.objectName() == "statusOk"
    assert "Ready" in p.text()


def test_set_running_back_to_false_returns_to_error(qtbot):
    p = StatusPill()
    qtbot.addWidget(p)
    p.set_running(True)
    p.set_running(False)
    assert p.objectName() == "statusError"
