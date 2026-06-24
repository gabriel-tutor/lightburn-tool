"""pywebview window host. The window is the ONLY responsibility here —
all logic lives in FulfillmentService, exposed via JsApiBridge."""

from __future__ import annotations

import contextlib
import ctypes
import sys
from importlib.resources import files

import webview

from lbb.web.bridge import JsApiBridge

_APP_USER_MODEL_ID = "Flanacom.FulfillmentStudio"


def _set_taskbar_app_id(app_id: str = _APP_USER_MODEL_ID) -> None:
    """Give the app its own Windows taskbar identity. The taskbar button groups by
    AppUserModelID; without an explicit one Windows inherits the host process's
    icon (python.exe in source, which is why only the title bar showed the logo).
    Setting our own id makes the taskbar use the window's Flanacom icon. Must run
    before the window is created. No-op off Windows; failures are cosmetic-only."""
    if not sys.platform.startswith("win"):
        return
    with contextlib.suppress(Exception):
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)


def run_app(service, *, title: str = "Fulfillment Studio", debug: bool = False) -> None:
    _set_taskbar_app_id()
    assets = files("lbb.web.assets")
    index = assets / "index.html"
    icon = assets / "flanacom.ico"
    api = JsApiBridge(service)
    webview.create_window(
        title, url=str(index), js_api=api, width=1280, height=900, min_size=(960, 640)
    )
    # Explicit window icon → the taskbar/title-bar shows the Flanacom logo. Without
    # it, pywebview's Windows backend falls back to the host exe's icon (python.exe
    # when run from source), which is why it looked like a "Python" app.
    webview.start(icon=str(icon), debug=debug)
