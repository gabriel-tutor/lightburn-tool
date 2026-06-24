from lbb.web.bridge import JsApiBridge, _as_url


def test_as_url_adds_scheme_to_bare_domain():
    assert _as_url("www.test.de") == "https://www.test.de"
    assert _as_url("sellercentral.amazon.com/x") == "https://sellercentral.amazon.com/x"


def test_as_url_passes_through_schemed_and_blank():
    assert _as_url("https://x.com") == "https://x.com"
    assert _as_url("http://x.com") == "http://x.com"
    assert _as_url("") == ""
    assert _as_url("#") == "#"


class FakeService:
    def __init__(self):
        self.calls = []

    def list_orders(self, *, filter="all", query=""):
        self.calls.append(("list", filter, query))
        return {"orders": [], "error": None}

    def get_order(self, n):
        self.calls.append(("get", n))
        return {"order_number": n}

    def engrave_side(self, n, file_key, close_previous=False):
        self.calls.append(("engrave", n, file_key, close_previous))
        return {"ok": True}

    def ship_order(self, n):
        self.calls.append(("ship", n))
        return {"ok": True}

    def set_status(self, n, status):
        self.calls.append(("status", n, status))
        return {"ok": True}

    def flag_revision(self, n):
        self.calls.append(("revision", n))
        return {"ok": True}

    def lightburn_status(self):
        return {"running": True}

    def label_file(self, n):
        return None

    def product_image(self, n, idx):
        self.calls.append(("image", n, idx))
        return {"ok": True, "data_uri": "data:image/png;base64,AAA"}


def test_bridge_delegates_queries_and_commands():
    svc = FakeService()
    b = JsApiBridge(svc)
    assert b.list_orders("open", "306") == {"orders": [], "error": None}
    assert b.get_order("306-1") == {"order_number": "306-1"}
    assert b.engrave_side("306-1", "engraving/x Front.pdf") == {"ok": True}
    assert b.ship_order("306-1") == {"ok": True}
    assert b.set_status("306-1", "revision") == {"ok": True}
    assert b.flag_revision("306-1") == {"ok": True}
    assert b.lightburn_status() == {"running": True}
    assert ("engrave", "306-1", "engraving/x Front.pdf", False) in svc.calls


def test_bridge_passes_close_previous():
    svc = FakeService()
    b = JsApiBridge(svc)
    b.engrave_side("306-1", "engraving/x Front.pdf", True)
    assert ("engrave", "306-1", "engraving/x Front.pdf", True) in svc.calls
    # default is False when omitted
    b.engrave_side("306-1", "engraving/x Front.pdf")
    assert ("engrave", "306-1", "engraving/x Front.pdf", False) in svc.calls


def test_open_label_when_missing_returns_error():
    b = JsApiBridge(FakeService())
    assert b.open_label("306-1") == {"ok": False, "error": "No label file"}


def test_bridge_product_image():
    svc = FakeService()
    b = JsApiBridge(svc)
    assert b.product_image("306-1", 0) == {"ok": True, "data_uri": "data:image/png;base64,AAA"}
    assert ("image", "306-1", 0) in svc.calls
