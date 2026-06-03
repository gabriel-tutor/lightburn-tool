import json
from pathlib import Path

from lbb.adapters.json_fulfillment import JsonFulfillmentRepository

SEED = {
    "orders": {
        "306-1": {
            "recipient": {"name": "Sabrina W.", "address": "52525 Heinsberg, DE"},
            "gift_box": True,
            "placed_at": "2026-01-03T10:00:00Z",
            "label": {"carrier": "DHL · 1 kg", "pdf_path": "labels/306-1.pdf"},
            "products": [
                {"item_id": "A", "name": "Heart necklace", "product_type": "Necklace",
                 "color": "Gold", "qty": 1, "sku": "FL-NECK-HEART-G",
                 "sides": [{"name": "Front", "pdf_path": "306-1-A-Front.pdf"},
                           {"name": "Back", "pdf_path": "306-1-A-Back.pdf"}]}
            ],
        }
    }
}


def _seed_dir(tmp_path: Path) -> Path:
    d = tmp_path / "seed"
    d.mkdir()
    (d / "orders.json").write_text(json.dumps(SEED), encoding="utf-8")
    return d


def test_seeds_on_first_run(tmp_path):
    orders_dir = tmp_path / "orders"
    repo = JsonFulfillmentRepository(orders_dir, seed_dir=_seed_dir(tmp_path))
    assert (orders_dir / "orders.json").exists()
    assert repo.get("306-1") is not None


def test_parses_products_and_sides(tmp_path):
    repo = JsonFulfillmentRepository(tmp_path / "orders", seed_dir=_seed_dir(tmp_path))
    o = repo.get("306-1")
    assert o.recipient.name == "Sabrina W."
    assert o.gift_box is True
    assert o.label.carrier == "DHL · 1 kg"
    p = o.products[0]
    assert p.product_type == "Necklace"
    assert [s.name for s in p.sides] == ["Front", "Back"]


def test_resolves_side_pdf_paths_to_orders_dir(tmp_path):
    orders_dir = tmp_path / "orders"
    repo = JsonFulfillmentRepository(orders_dir, seed_dir=_seed_dir(tmp_path))
    side = repo.get("306-1").products[0].sides[0]
    assert Path(side.pdf_path).is_absolute()
    assert side.pdf_path.endswith("306-1-A-Front.pdf")
    assert str(orders_dir.resolve()) in side.pdf_path


def test_resolves_label_path_to_orders_dir(tmp_path):
    orders_dir = tmp_path / "orders"
    repo = JsonFulfillmentRepository(orders_dir, seed_dir=_seed_dir(tmp_path))
    assert Path(repo.get("306-1").label.pdf_path).is_absolute()


def test_malformed_json_yields_empty(tmp_path):
    orders_dir = tmp_path / "orders"
    orders_dir.mkdir()
    (orders_dir / "orders.json").write_text("{ not json", encoding="utf-8")
    repo = JsonFulfillmentRepository(orders_dir)
    assert repo.list_all() == []
    assert repo.get("306-1") is None


def test_list_all_sorted_by_order_number(tmp_path):
    repo = JsonFulfillmentRepository(tmp_path / "orders", seed_dir=_seed_dir(tmp_path))
    assert [o.order_number for o in repo.list_all()] == ["306-1"]
