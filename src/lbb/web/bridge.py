"""JsApiBridge — exposed to JavaScript as `window.pywebview.api`.

Every public method returns a JSON-serialisable value (dict/list/scalar) and
delegates to FulfillmentService. Open/print helpers use the OS shell. This
class deliberately holds no business logic — it only marshals arguments.
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

    # ── commands ──
    def engrave_side(self, order_number, item_id, side_name):
        return self._svc.engrave_side(order_number, item_id, side_name)

    def set_status(self, order_number, status):
        return self._svc.set_status(order_number, status)

    def ship_order(self, order_number):
        return self._svc.ship_order(order_number)

    def add_comment(self, order_number, text):
        return self._svc.add_comment(order_number, text)

    # ── shell helpers ──
    def open_amazon(self, url):
        return self._open_path_or_url(url) or {"ok": True}

    def open_instructions(self, url):
        return self._open_path_or_url(url) or {"ok": True}

    def open_label(self, order_number):
        path = self._svc.label_path(order_number) if hasattr(self._svc, "label_path") else None
        if not path:
            return {"ok": False, "error": "No label file"}
        return self._open_path_or_url(path) or {"ok": True}

    def print_label(self, order_number):
        path = self._svc.label_path(order_number) if hasattr(self._svc, "label_path") else None
        if not path:
            return {"ok": False, "error": "No label file"}
        return self._print_path(path)

    # ── internals ──
    def _open_path_or_url(self, target: str):
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

    def _print_path(self, target: str):
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
