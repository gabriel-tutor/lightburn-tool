import json

import pytest

from lbb.adapters.engraving_api import EngravingApiClient
from lbb.core.fulfillment import OrderStatus
from lbb.ports.engraving import EngravingApiError

BASE = "https://api.test/engraving-api"

ORDER = {
    "id": "uuid-1",
    "order_number": "306-0804157-6173963",
    "link_to_order": "https://sellercentral/x",
    "order_date": "2026-06-15",
    "amount": 1,
    "status": "not_done_yet",
    "comment": "With Gift Box each",
    "shipping_label_path": "shipping_label/x.pdf",
    "created_at": "2026-06-16T14:53:45+02:00",
    "updated_at": "2026-06-22T11:31:45+02:00",
    "products": [
        {
            "type": "bracelet",
            "color_band_chain": "Retro",
            "color_coin_plate": "Silver",
            "multiple_coins": False,
            "special_length": False,
            "length": None,
            "image": "product_picture/x.png",
            "coins": [{"front": "engraving/x Front.pdf", "back": "engraving/x Back.pdf"}],
        }
    ],
    "signed_urls": {
        "shipping_label/x.pdf": "https://dl/label?token=1",
        "engraving/x Front.pdf": "https://dl/front?token=1",
        "engraving/x Back.pdf": "https://dl/back?token=1",
    },
}


class FakeTransport:
    """Programmable transport. `routes` maps (method, url-substring) -> (code, bytes).
    Records every call. File downloads return raw bytes for any URL with /dl/."""

    def __init__(self, orders, *, post_code=200):
        self.orders = orders
        self.post_code = post_code
        self.calls = []
        self.get_count = 0

    def request(self, method, url, *, headers, body=None):
        self.calls.append((method, url, headers, body))
        if "/dl/" in url:
            return 200, b"%PDF-1.4 fake"
        if method == "GET":
            self.get_count += 1
            return 200, json.dumps({"orders": self.orders}).encode()
        if method == "POST":
            payload = json.loads(body)
            return self.post_code, json.dumps(
                {"ok": True, "order": {"id": payload["order_id"],
                                       "status": payload["status"]}}
            ).encode()
        return 404, b"{}"


def _client(transport, **kw):
    return EngravingApiClient(BASE, "secret-key", transport, **kw)


def test_list_orders_parses_domain():
    t = FakeTransport([ORDER])
    [o] = _client(t).list_orders()
    assert o.order_id == "uuid-1"
    assert o.order_number == "306-0804157-6173963"
    assert o.amount == 1
    assert o.status is OrderStatus.NOT_DONE
    assert o.gift_box is True
    assert o.amazon_url == "https://sellercentral/x"
    assert o.label_key == "shipping_label/x.pdf"
    assert o.placed_at.year == 2026
    [p] = o.products
    assert p.product_type == "Bracelet"
    assert p.band_color == "Retro" and p.coin_color == "Silver"
    assert [s.file_key for s in p.sides] == ["engraving/x Front.pdf", "engraving/x Back.pdf"]
    assert [s.name for s in p.sides] == ["Front", "Back"]


def test_get_sends_api_key_header():
    t = FakeTransport([ORDER])
    _client(t).list_orders()
    method, url, headers, _ = t.calls[0]
    assert method == "GET"
    assert headers["x-api-key"] == "secret-key"


def test_multiple_coins_names_are_prefixed():
    raw = json.loads(json.dumps(ORDER))
    raw["products"][0]["coins"] = [
        {"front": "f1", "back": "b1"},
        {"front": "f2", "back": "b2"},
    ]
    t = FakeTransport([raw])
    [o] = _client(t).list_orders()
    assert [s.name for s in o.products[0].sides] == [
        "Coin 1 Front", "Coin 1 Back", "Coin 2 Front", "Coin 2 Back",
    ]


def test_get_returns_cached_order_by_number():
    t = FakeTransport([ORDER])
    c = _client(t)
    c.list_orders()
    assert c.get("306-0804157-6173963").order_id == "uuid-1"
    assert c.get("nope") is None


def test_download_file_writes_bytes(tmp_path):
    t = FakeTransport([ORDER])
    c = _client(t)
    c.list_orders()
    p = c.download_file("uuid-1", "engraving/x Front.pdf", tmp_path)
    assert p.is_file()
    assert p.read_bytes().startswith(b"%PDF")


def test_download_refetches_when_stale(tmp_path):
    clock = [1000.0]
    t = FakeTransport([ORDER])
    c = _client(t, now=lambda: clock[0])
    c.list_orders()                 # get_count == 1
    clock[0] += 60 * 60             # 1 hour later -> stale
    c.download_file("uuid-1", "engraving/x Front.pdf", tmp_path)
    assert t.get_count == 2          # re-GET happened for a fresh signed URL


def test_set_status_posts_body():
    t = FakeTransport([ORDER])
    _client(t).set_status("uuid-1", OrderStatus.DONE)
    post = [c for c in t.calls if c[0] == "POST"][-1]
    body = json.loads(post[3])
    assert body == {"order_id": "uuid-1", "status": "graviert_verschickt"}
    assert post[2]["Content-Type"] == "application/json"


def test_set_status_raises_on_404():
    t = FakeTransport([ORDER], post_code=404)
    with pytest.raises(EngravingApiError) as ei:
        _client(t).set_status("ghost", OrderStatus.DONE)
    assert ei.value.status_code == 404


def test_list_orders_raises_on_401():
    class Unauth:
        def request(self, *a, **k):
            return 401, b'{"error":"unauthorized"}'
    with pytest.raises(EngravingApiError) as ei:
        _client(Unauth()).list_orders()
    assert ei.value.status_code == 401


def test_set_status_invalidates_cache():
    t = FakeTransport([ORDER])
    c = _client(t)
    c.list_orders()                 # get_count == 1
    c.set_status("uuid-1", OrderStatus.REVISION)
    c.get("306-0804157-6173963")    # cache invalidated -> must re-GET
    assert t.get_count == 2


def test_parse_captures_order_metadata():
    raw = json.loads(json.dumps(ORDER))
    raw["link_to_graphic"] = "https://graphic/x"
    raw["product_picture_path"] = "product_picture/order.png"
    raw["product_type"] = "bracelet"
    raw["color"] = "Gold"
    t = FakeTransport([raw])
    [o] = _client(t).list_orders()
    assert o.link_to_graphic == "https://graphic/x"
    assert o.order_picture_key == "product_picture/order.png"
    assert o.type_summary == "Bracelet"
    assert o.color_summary == "Gold"
    assert o.created_at is not None and o.updated_at is not None


def test_parse_tolerates_missing_metadata():
    raw = json.loads(json.dumps(ORDER))
    for k in ("link_to_graphic", "product_picture_path", "product_type", "color"):
        raw.pop(k, None)
    t = FakeTransport([raw])
    [o] = _client(t).list_orders()
    assert o.link_to_graphic == "" and o.order_picture_key == ""
    assert o.type_summary == "" and o.color_summary == ""


def test_parse_sets_coin_count():
    raw = json.loads(json.dumps(ORDER))
    raw["products"][0]["coins"] = [{"front": "f1", "back": "b1"}, {"front": "f2", "back": "b2"}]
    t = FakeTransport([raw])
    [o] = _client(t).list_orders()
    assert o.products[0].coin_count == 2


def test_download_refetches_on_expired_link_then_succeeds(tmp_path):
    """A 403 on the signed URL forces one fresh GET + retry."""
    state = {"download_calls": 0, "get_calls": 0}

    class ExpiringTransport:
        def request(self, method, url, *, headers, body=None):
            if "/dl/" in url:
                state["download_calls"] += 1
                # First download attempt: link expired (403). After a re-GET, ok.
                if state["download_calls"] == 1:
                    return 403, b"expired"
                return 200, b"%PDF-1.4 fresh"
            if method == "GET":
                state["get_calls"] += 1
                return 200, json.dumps({"orders": [ORDER]}).encode()
            return 404, b"{}"

    c = EngravingApiClient(BASE, "secret", ExpiringTransport())
    c.list_orders()                         # get_calls == 1, caches signed urls
    p = c.download_file("uuid-1", "engraving/x Front.pdf", tmp_path)
    assert p.read_bytes().startswith(b"%PDF")
    assert state["download_calls"] == 2     # first 403, retried after re-GET
    assert state["get_calls"] == 2          # one extra GET to mint fresh urls
