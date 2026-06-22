"""pywebview window host. The window is the ONLY responsibility here —
all logic lives in FulfillmentService, exposed via JsApiBridge."""

from __future__ import annotations

from importlib.resources import files

import webview

from lbb.web.bridge import JsApiBridge


def run_app(service, *, title: str = "Fulfillment Studio", debug: bool = False) -> None:
    index = files("lbb.web.assets") / "index.html"
    api = JsApiBridge(service)
    webview.create_window(
        title, url=str(index), js_api=api, width=1280, height=900, min_size=(960, 640)
    )
    webview.start(debug=debug)
