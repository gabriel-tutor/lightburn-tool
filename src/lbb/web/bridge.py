"""JsApiBridge — exposed to JavaScript as `window.pywebview.api`.

Every method returns a JSON-serialisable value and delegates to
FulfillmentService. No business logic — only argument marshalling and OS
open/print of downloaded files.
"""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser


class JsApiBridge:
    def __init__(self, service):
        self._svc = service

    # ── queries ──
    def list_orders(self, filter="all", query=""):  # noqa: A002 - JS-facing name
        return self._svc.list_orders(filter=filter, query=query)

    def get_order(self, order_number):
        return self._svc.get_order(order_number)

    def lightburn_status(self):
        return self._svc.lightburn_status()

    def product_image(self, order_number, product_index):
        return self._svc.product_image(order_number, product_index)

    # ── commands ──
    def engrave_side(self, order_number, file_key):
        return self._svc.engrave_side(order_number, file_key)

    def ship_order(self, order_number):
        return self._svc.ship_order(order_number)

    def set_status(self, order_number, status):
        return self._svc.set_status(order_number, status)

    def flag_revision(self, order_number):
        return self._svc.flag_revision(order_number)

    # ── shell helpers ──
    def open_amazon(self, url):
        return self._open(url) or {"ok": True}

    def open_label(self, order_number):
        path = self._svc.label_file(order_number)
        if not path:
            return {"ok": False, "error": "No label file"}
        return self._open(str(path)) or {"ok": True}

    def print_label(self, order_number):
        path = self._svc.label_file(order_number)
        if not path:
            return {"ok": False, "error": "No label file"}
        return self._print(str(path))

    # ── internals ──
    def _open(self, target: str):
        try:
            if target.startswith(("http://", "https://")):
                webbrowser.open(target)
            elif sys.platform.startswith("win"):
                os.startfile(target)  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.Popen(["open", target])
            else:
                subprocess.Popen(["xdg-open", target])
            return None
        except OSError as e:
            return {"ok": False, "error": str(e)}

    def _print(self, target: str):
        try:
            if sys.platform.startswith("win"):
                os.startfile(target, "print")  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.Popen(["lpr", target])
            else:
                subprocess.Popen(["lp", target])
            return {"ok": True}
        except OSError as e:
            return {"ok": False, "error": str(e)}
