from datetime import datetime
from datetime import datetime as _dt
from pathlib import Path

from lbb.app.fulfillment_service import FulfillmentService
from lbb.core.fulfillment import FulfillmentOrder, OrderStatus, Product, Side
from lbb.ports.engraving import EngravingApiError


def _order(status=OrderStatus.NOT_DONE):
    return FulfillmentOrder(
        order_id="uuid-1",
        order_number="306-1",
        amount=1,
        status=status,
        instruction="With Gift Box each",
        amazon_url="https://sc/x",
        label_key="shipping_label/x.pdf",
        placed_at=datetime(2026, 6, 15),
        products=(
            Product(
                product_type="Bracelet", band_color="Retro", coin_color="Silver",
                sides=(Side("Front", "engraving/x Front.pdf"),
                       Side("Back", "engraving/x Back.pdf")),
            ),
        ),
    )


class FakeGateway:
    def __init__(self, orders):
        self._orders = {o.order_number: o for o in orders}
        self.posted = []
        self.downloads = []

    def list_orders(self):
        return list(self._orders.values())

    def get(self, n):
        return self._orders.get(n)

    def download_file(self, order_id, file_key, dest_dir):
        self.downloads.append((order_id, file_key))
        p = Path(dest_dir) / "job.pdf"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"%PDF fake")
        return p

    def set_status(self, order_id, status):
        self.posted.append((order_id, status))


class FakeLightBurn:
    def __init__(self):
        self.loaded = []

    def is_running(self):
        return True

    def load_file(self, path):
        self.loaded.append(path)


class MemState:
    def __init__(self):
        self._k = {}

    def engraved_keys(self, n):
        return set(self._k.get(n, set()))

    def mark_engraved(self, n, key, engraved):
        s = self._k.setdefault(n, set())
        s.add(key) if engraved else s.discard(key)


def _svc(gw=None, tmp=Path(".")):
    gw = gw or FakeGateway([_order()])
    return FulfillmentService(gateway=gw, state=MemState(),
                              lightburn=FakeLightBurn(), cache_dir=tmp), gw


def test_list_orders_shapes_cards(tmp_path):
    svc, _ = _svc(tmp=tmp_path)
    res = svc.list_orders()
    assert res["error"] is None
    [card] = res["orders"]
    assert card["order_number"] == "306-1"
    assert card["status"] == "not_done_yet"
    assert card["gift_box"] is True
    assert card["progress"] == {"done": 0, "total": 2}


def test_engrave_downloads_then_opens_lightburn(tmp_path):
    gw = FakeGateway([_order()])
    svc = FulfillmentService(gateway=gw, state=MemState(),
                             lightburn=(lb := FakeLightBurn()), cache_dir=tmp_path)
    res = svc.engrave_side("306-1", "engraving/x Front.pdf")
    assert res["ok"] is True
    assert gw.downloads == [("uuid-1", "engraving/x Front.pdf")]
    assert lb.loaded and str(lb.loaded[0]).endswith("job.pdf")
    assert res["progress"] == {"done": 1, "total": 2}


def test_engrave_rejects_unknown_key(tmp_path):
    svc, _ = _svc(tmp=tmp_path)
    res = svc.engrave_side("306-1", "nope.pdf")
    assert res["ok"] is False


def test_ship_requires_all_engraved_then_posts_done(tmp_path):
    gw = FakeGateway([_order()])
    svc = FulfillmentService(gateway=gw, state=MemState(),
                             lightburn=FakeLightBurn(), cache_dir=tmp_path)
    assert svc.ship_order("306-1")["ok"] is False           # nothing engraved yet
    svc.engrave_side("306-1", "engraving/x Front.pdf")
    svc.engrave_side("306-1", "engraving/x Back.pdf")
    res = svc.ship_order("306-1")
    assert res["ok"] is True
    assert gw.posted == [("uuid-1", OrderStatus.DONE)]


def test_flag_revision_posts_revision(tmp_path):
    gw = FakeGateway([_order()])
    svc = FulfillmentService(gateway=gw, state=MemState(),
                             lightburn=FakeLightBurn(), cache_dir=tmp_path)
    assert svc.flag_revision("306-1")["ok"] is True
    assert gw.posted == [("uuid-1", OrderStatus.REVISION)]


def test_get_order_marks_engraved_sides(tmp_path):
    gw = FakeGateway([_order()])
    svc = FulfillmentService(gateway=gw, state=MemState(),
                             lightburn=FakeLightBurn(), cache_dir=tmp_path)
    svc.engrave_side("306-1", "engraving/x Front.pdf")
    detail = svc.get_order("306-1")
    sides = detail["products"][0]["sides"]
    assert sides[0] == {"name": "Front", "file_key": "engraving/x Front.pdf", "engraved": True}
    assert sides[1]["engraved"] is False
    assert detail["instruction"] == "With Gift Box each"


def test_list_orders_reports_gateway_error(tmp_path):
    class Boom:
        def list_orders(self):
            raise EngravingApiError("API key rejected", status_code=401)
    svc = FulfillmentService(gateway=Boom(), state=MemState(),
                             lightburn=FakeLightBurn(), cache_dir=tmp_path)
    res = svc.list_orders()
    assert res["orders"] == []
    assert "rejected" in res["error"]


def _order_with_image():
    return FulfillmentOrder(
        order_id="uuid-img", order_number="306-IMG", amount=1,
        products=(Product(product_type="Necklace", coin_color="Silver",
                          image_key="product_picture/ref.png",
                          sides=(Side("Front", "engraving/f.pdf"),)),),
    )


def test_product_image_returns_data_uri(tmp_path):
    gw = FakeGateway([_order_with_image()])
    svc = FulfillmentService(gateway=gw, state=MemState(),
                             lightburn=FakeLightBurn(), cache_dir=tmp_path)
    res = svc.product_image("306-IMG", 0)
    assert res["ok"] is True
    assert res["data_uri"].startswith("data:image/png;base64,")
    assert gw.downloads == [("uuid-img", "product_picture/ref.png")]


def test_product_image_no_image_key(tmp_path):
    # default _order() product has no image_key
    gw = FakeGateway([_order()])
    svc = FulfillmentService(gateway=gw, state=MemState(),
                             lightburn=FakeLightBurn(), cache_dir=tmp_path)
    assert svc.product_image("306-1", 0)["ok"] is False


def test_product_image_unknown_product(tmp_path):
    gw = FakeGateway([_order_with_image()])
    svc = FulfillmentService(gateway=gw, state=MemState(),
                             lightburn=FakeLightBurn(), cache_dir=tmp_path)
    assert svc.product_image("306-IMG", 9)["ok"] is False


def test_get_order_includes_metadata_and_sides_summary(tmp_path):
    o = FulfillmentOrder(
        order_id="uuid-m", order_number="306-M", amount=2,
        instruction="With Gift Box", amazon_url="https://sc/m",
        label_key="shipping_label/the-label.pdf",
        link_to_graphic="https://graphic/m",
        created_at=_dt(2026, 6, 16), updated_at=_dt(2026, 6, 22),
        type_summary="Necklace", color_summary="Silver",
        products=(Product(product_type="Necklace", band_color="Retro",
                          coin_color="Silver", multiple_coins=True,
                          special_length=True, length="50cm", coin_count=2,
                          image_key="product_picture/ref.png",
                          sides=(Side("Coin 1 Front", "a"), Side("Coin 1 Back", "b"),
                                 Side("Coin 2 Front", "c"), Side("Coin 2 Back", "d"))),),
    )
    gw = FakeGateway([o])
    svc = FulfillmentService(gateway=gw, state=MemState(),
                             lightburn=FakeLightBurn(), cache_dir=tmp_path)
    d = svc.get_order("306-M")
    assert d["link_to_graphic"] == "https://graphic/m"
    assert d["created_label"] and d["updated_label"]
    assert d["type_summary"] == "Necklace" and d["color_summary"] == "Silver"
    assert d["label_name"] == "the-label.pdf"
    p = d["products"][0]
    assert p["band_color"] == "Retro"
    assert p["multiple_coins"] is True
    assert p["special_length"] is True and p["length"] == "50cm"
    assert p["sides_summary"] == "2 coins · Front & Back each — 4 jobs"
    assert p["has_image"] is True
    assert p["coin_count"] == 2
    assert d["has_order_picture"] is False


def test_product_image_corrupt_file_returns_not_ok(tmp_path, monkeypatch):
    gw = FakeGateway([_order_with_image()])

    # download "succeeds" but the file can't be read back
    def boom_download(order_id, file_key, dest_dir):
        # path that does not exist -> read_bytes raises OSError
        return tmp_path / "x.png"

    gw.download_file = boom_download
    svc = FulfillmentService(gateway=gw, state=MemState(),
                             lightburn=FakeLightBurn(), cache_dir=tmp_path)
    assert svc.product_image("306-IMG", 0)["ok"] is False


def test_engrave_side_lightburn_oserror_not_marked(tmp_path):
    gw = FakeGateway([_order()])

    class BoomLightBurn(FakeLightBurn):
        def load_file(self, path):
            raise OSError("LightBurn launch failed")

    state = MemState()
    svc = FulfillmentService(gateway=gw, state=state,
                             lightburn=BoomLightBurn(), cache_dir=tmp_path)
    res = svc.engrave_side("306-1", "engraving/x Front.pdf")
    assert res["ok"] is False
    assert state.engraved_keys("306-1") == set()   # NOT marked on failure


def test_get_order_has_no_qty(tmp_path):
    gw = FakeGateway([_order()])
    svc = FulfillmentService(gateway=gw, state=MemState(),
                             lightburn=FakeLightBurn(), cache_dir=tmp_path)
    d = svc.get_order("306-1")
    assert "qty" not in d["products"][0]
