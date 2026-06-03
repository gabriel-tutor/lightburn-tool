from lbb.web.bridge import JsApiBridge


class _StubService:
    def __init__(self):
        self.calls = []

    def list_orders(self, *, filter="all", query=""):
        self.calls.append(("list", filter, query)); return [{"order_number": "306-1"}]  # noqa: E702

    def get_order(self, order_number):
        self.calls.append(("get", order_number)); return {"order_number": order_number}  # noqa: E702

    def engrave_side(self, order_number, item_id, side_name):
        self.calls.append(("engrave", order_number, item_id, side_name)); return {"ok": True}  # noqa: E702

    def set_status(self, order_number, status):
        return {"ok": True, "status": status}

    def ship_order(self, order_number):
        return {"ok": True}

    def add_comment(self, order_number, text):
        return {"ok": True}

    def lightburn_status(self):
        return {"running": True}


def test_list_orders_delegates_with_kwargs():
    svc = _StubService()
    bridge = JsApiBridge(svc)
    assert bridge.list_orders("open", "306") == [{"order_number": "306-1"}]
    assert svc.calls[0] == ("list", "open", "306")


def test_engrave_side_delegates_positionally():
    svc = _StubService()
    bridge = JsApiBridge(svc)
    assert bridge.engrave_side("306-1", "A", "Front") == {"ok": True}
    assert svc.calls[-1] == ("engrave", "306-1", "A", "Front")


def test_open_helpers_are_safe_noops_without_handler(monkeypatch):
    bridge = JsApiBridge(_StubService())
    monkeypatch.setattr(bridge, "_open_path_or_url", lambda *_: None)
    assert bridge.open_amazon("https://example.com")["ok"] is True
