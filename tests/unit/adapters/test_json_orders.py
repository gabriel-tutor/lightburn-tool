import json
from pathlib import Path

from lbb.adapters.json_orders import JsonOrderRepository


def _write_seed(seed_dir: Path) -> None:
    """Build a self-contained seed dir: orders.json + dummy design PDFs."""
    seed_dir.mkdir(parents=True, exist_ok=True)
    (seed_dir / "305-A.pdf").write_bytes(b"%PDF-1.4 fake A")
    (seed_dir / "305-B.pdf").write_bytes(b"%PDF-1.4 fake B")
    (seed_dir / "304-A.pdf").write_bytes(b"%PDF-1.4 fake 304-A")
    (seed_dir / "orders.json").write_text(
        json.dumps(
            {
                "orders": {
                    "305-6737580-7658721": {
                        "customer": {"name": "Jane Doe", "email": "jane@example.com"},
                        "placed_at": "2026-05-15T14:30:00Z",
                        "items": [
                            {
                                "item_id": "A",
                                "sku": "LB-WALLET-LEATHER-S",
                                "customization": {"engraving_text": "John 2026"},
                                "pdf_path": "305-A.pdf",
                            },
                            {
                                "item_id": "B",
                                "sku": "LB-WALLET-LEATHER-S",
                                "customization": {"engraving_text": "Jane 2026"},
                                "pdf_path": "305-B.pdf",
                            },
                        ],
                    },
                    "304-4865183-6105121": {
                        "customer": {"name": "Maria Smith"},
                        "items": [
                            {
                                "item_id": "A",
                                "sku": "LB-WALLET-LEATHER-T",
                                "customization": {"engraving_text": "III.III.MMXX"},
                                "pdf_path": "304-A.pdf",
                            }
                        ],
                    },
                }
            }
        )
    )


def test_get_returns_order_when_present(tmp_path):
    seed = tmp_path / "seed"
    _write_seed(seed)
    repo = JsonOrderRepository(tmp_path / "orders", seed_dir=seed)
    order = repo.get("305-6737580-7658721")
    assert order is not None
    assert order.customer.name == "Jane Doe"
    assert len(order.items) == 2
    assert order.items[0].sku.value == "LB-WALLET-LEATHER-S"


def test_get_returns_none_when_absent(tmp_path):
    seed = tmp_path / "seed"
    _write_seed(seed)
    repo = JsonOrderRepository(tmp_path / "orders", seed_dir=seed)
    assert repo.get("999-NOT-AN-ORDER") is None


def test_seeds_orders_dir_on_first_run(tmp_path):
    """If orders_dir doesn't exist yet, the whole seed dir is copied over —
    JSON AND the design PDFs land in the user-home location."""
    seed = tmp_path / "seed"
    _write_seed(seed)
    orders_dir = tmp_path / "user_home" / "orders"
    assert not orders_dir.exists()
    JsonOrderRepository(orders_dir, seed_dir=seed)
    assert (orders_dir / "orders.json").exists()
    assert (orders_dir / "305-A.pdf").exists()
    assert (orders_dir / "304-A.pdf").exists()


def test_pdf_paths_are_resolved_relative_to_orders_dir(tmp_path):
    """Relative pdf_path in orders.json → absolute path under orders_dir on
    the returned OrderItem so callers don't need to do their own join."""
    seed = tmp_path / "seed"
    _write_seed(seed)
    orders_dir = tmp_path / "orders"
    repo = JsonOrderRepository(orders_dir, seed_dir=seed)
    order = repo.get("305-6737580-7658721")
    assert order is not None
    # Item A's pdf_path should now be an absolute path inside orders_dir.
    item_a_path = Path(order.items[0].pdf_path)
    assert item_a_path.is_absolute()
    assert item_a_path.exists()
    assert item_a_path.name == "305-A.pdf"


def test_list_all_returns_sorted_by_order_number(tmp_path):
    seed = tmp_path / "seed"
    _write_seed(seed)
    repo = JsonOrderRepository(tmp_path / "orders", seed_dir=seed)
    nums = [o.order_number for o in repo.list_all()]
    assert nums == sorted(nums)


def test_malformed_json_is_swallowed(tmp_path):
    orders_dir = tmp_path / "orders"
    orders_dir.mkdir()
    (orders_dir / "orders.json").write_text("{ this isn't json")
    repo = JsonOrderRepository(orders_dir)
    assert repo.get("anything") is None
    assert repo.list_all() == []


def test_absolute_pdf_path_preserved(tmp_path):
    """If JSON specifies an absolute pdf_path, the adapter keeps it as-is."""
    orders_dir = tmp_path / "orders"
    orders_dir.mkdir()
    abs_pdf = tmp_path / "elsewhere" / "design.pdf"
    abs_pdf.parent.mkdir()
    abs_pdf.write_bytes(b"%PDF-1.4")
    (orders_dir / "orders.json").write_text(
        json.dumps(
            {
                "orders": {
                    "X": {
                        "customer": {"name": "X"},
                        "items": [
                            {"item_id": "1", "sku": "LB-X", "pdf_path": str(abs_pdf)}
                        ],
                    }
                }
            }
        )
    )
    repo = JsonOrderRepository(orders_dir)
    order = repo.get("X")
    assert order is not None
    assert order.items[0].pdf_path == str(abs_pdf)


def test_returns_empty_when_no_orders_dir_and_no_seed(tmp_path):
    repo = JsonOrderRepository(tmp_path / "missing")
    assert repo.list_all() == []
    assert repo.get("305") is None
