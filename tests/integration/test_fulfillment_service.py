import json

import pytest

from lbb.adapters.json_fulfillment import JsonFulfillmentRepository
from lbb.adapters.lightburn_fake import LightBurnFake
from lbb.adapters.sqlite_state import SqliteStateStore
from lbb.app.fulfillment_service import FulfillmentService

SEED = {
    "orders": {
        "306-1": {
            "recipient": {"name": "Sabrina W.", "address": "52525 Heinsberg, DE"},
            "gift_box": True, "placed_at": "2026-01-03T10:00:00Z",
            "label": {"carrier": "DHL · 1 kg", "pdf_path": "labels/306-1.pdf"},
            "products": [
                {"item_id": "A", "name": "Heart necklace", "product_type": "Necklace",
                 "color": "Gold", "qty": 1, "sku": "FL-NECK-HEART-G",
                 "sides": [{"name": "Front", "pdf_path": "306-1-A-Front.pdf"},
                           {"name": "Back", "pdf_path": "306-1-A-Back.pdf"}]}
            ],
        },
        "306-2": {
            "recipient": {"name": "Nina H.", "address": "70173 Stuttgart, DE"},
            "placed_at": "2026-01-01T09:00:00Z",
            "products": [
                {"item_id": "A", "name": "Bangle", "product_type": "Bracelet",
                 "color": "Gold", "qty": 1, "sku": "FL-BRAC-BANGLE-G",
                 "sides": [{"name": "Front", "pdf_path": "306-2-A-Front.pdf"}]}
            ],
        },
    }
}


@pytest.fixture
def svc(tmp_path) -> FulfillmentService:
    orders_dir = tmp_path / "orders"
    orders_dir.mkdir()
    (orders_dir / "orders.json").write_text(json.dumps(SEED), encoding="utf-8")
    for name in ("306-1-A-Front.pdf", "306-1-A-Back.pdf", "306-2-A-Front.pdf"):
        (orders_dir / name).write_bytes(b"%PDF-1.4\n%%EOF\n")
    repo = JsonFulfillmentRepository(orders_dir)
    state = SqliteStateStore(tmp_path / "state.sqlite")
    return FulfillmentService(repo=repo, state=state, lightburn=LightBurnFake())


def test_list_orders_grouped_bracelet_before_necklace(svc):
    cards = svc.list_orders(filter="all", query="")
    assert [c["order_number"] for c in cards] == ["306-2", "306-1"]
    assert cards[0]["bucket"] == "Bracelets"


def test_get_order_initial_status_received(svc):
    detail = svc.get_order("306-1")
    assert detail["status"] == "received"
    assert detail["progress"] == {"done": 0, "total": 2}
    assert detail["gift_box"] is True


def test_engrave_side_opens_pdf_and_marks_done(svc):
    res = svc.engrave_side("306-1", "A", "Front")
    assert res["ok"] is True
    assert res["status"] == "engraving"
    assert svc.lightburn.loaded[-1].name == "306-1-A-Front.pdf"


def test_engrave_all_sides_flips_to_engraved(svc):
    svc.engrave_side("306-1", "A", "Front")
    res = svc.engrave_side("306-1", "A", "Back")
    assert res["status"] == "engraved"


def test_ship_blocked_until_all_engraved(svc):
    blocked = svc.ship_order("306-1")
    assert blocked["ok"] is False
    svc.engrave_side("306-1", "A", "Front")
    svc.engrave_side("306-1", "A", "Back")
    ok = svc.ship_order("306-1")
    assert ok["ok"] is True
    assert svc.get_order("306-1")["status"] == "shipped"


def test_engrave_missing_pdf_returns_error(svc):
    res = svc.engrave_side("306-2", "A", "Front")
    assert res["ok"] is True
    bad = svc.engrave_side("306-1", "A", "Nonexistent")
    assert bad["ok"] is False
    assert "side" in bad["error"].lower()


def test_set_status_hold_then_clear(svc):
    svc.set_status("306-1", "hold")
    assert svc.get_order("306-1")["status"] == "hold"
    svc.set_status("306-1", "received")
    assert svc.get_order("306-1")["status"] == "received"


def test_add_comment_round_trips(svc):
    svc.add_comment("306-1", "re-engrave back")
    assert svc.get_order("306-1")["comments"][0]["text"] == "re-engrave back"


def test_label_path_returns_existing_file(svc, tmp_path):
    label = tmp_path / "orders" / "labels" / "306-1.pdf"
    label.parent.mkdir(parents=True, exist_ok=True)
    label.write_bytes(b"%PDF-1.4\n%%EOF\n")
    got = svc.label_path("306-1")
    assert got is not None and got.endswith("306-1.pdf")
    assert svc.label_path("306-2") is None  # 306-2 has no label


def test_list_filters_open_and_shipped(svc):
    # Ship 306-2 (single side) so it leaves the open queue.
    svc.engrave_side("306-2", "A", "Front")
    svc.ship_order("306-2")
    open_nums = [c["order_number"] for c in svc.list_orders(filter="open", query="")]
    shipped_nums = [c["order_number"] for c in svc.list_orders(filter="shipped", query="")]
    assert "306-2" not in open_nums
    assert open_nums == ["306-1"]
    assert shipped_nums == ["306-2"]
