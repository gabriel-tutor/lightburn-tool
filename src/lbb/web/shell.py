"""pywebview window host. The window is the ONLY responsibility here —
all logic lives in FulfillmentService, exposed via JsApiBridge."""

from __future__ import annotations

from importlib.resources import files

import webview

from lbb.web.bridge import JsApiBridge


def run_app(service, *, title: str = "Fulfillment Studio", debug: bool = False) -> None:
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
