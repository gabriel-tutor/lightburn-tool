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
