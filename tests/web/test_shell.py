"""run_app wires the Flanacom window icon into webview.start (so the taskbar
shows the logo, not the host python.exe icon)."""

import os

from lbb.web import shell


def test_run_app_passes_existing_flanacom_window_icon(monkeypatch):
    calls = {}
    monkeypatch.setattr(shell.webview, "create_window",
                        lambda *a, **k: calls.setdefault("window", (a, k)))
    monkeypatch.setattr(shell.webview, "start",
                        lambda **k: calls.setdefault("start", k))

    shell.run_app(object())

    icon = calls["start"]["icon"]
    assert icon.endswith("flanacom.ico")
    # pywebview's Windows backend only applies the icon when os.path.isfile passes,
    # so the bundled asset must really exist on disk.
    assert os.path.isfile(icon)


def test_run_app_sets_taskbar_app_id_before_window(monkeypatch):
    """The Windows taskbar groups by AppUserModelID; without an explicit one the
    button inherits the host python.exe icon. run_app must set our app id, and do
    it before the window/taskbar button is created."""
    order = []
    monkeypatch.setattr(shell, "_set_taskbar_app_id",
                        lambda *a, **k: order.append("appid"))
    monkeypatch.setattr(shell.webview, "create_window",
                        lambda *a, **k: order.append("create"))
    monkeypatch.setattr(shell.webview, "start", lambda **k: order.append("start"))

    shell.run_app(object())

    assert order and order[0] == "appid"          # set before anything else
    assert order.index("appid") < order.index("create")
