import pytest

from lbb.adapters.sqlite_repo import SqliteProfileRepository
from lbb.core.models import Material, Sku, SkuProfile, Template
from lbb.ui.views.admin import AdminView


@pytest.fixture
def repo(tmp_path) -> SqliteProfileRepository:
    repo = SqliteProfileRepository(tmp_path / "p.sqlite")
    t = repo.upsert_template(
        Template(id=0, name="Wallet — S", lbrn2_path="/x.lbrn2", canvas_w_mm=95, canvas_h_mm=110)
    )
    m = repo.upsert_material(
        Material(id=0, name="Leather", clb_library="default.clb", clb_entry="LeatherVT")
    )
    repo.upsert(SkuProfile(sku=Sku("LB-EXISTING"), template=t, material=m, overrides={}))
    return repo


def test_constructs(qtbot, repo):
    view = AdminView(repo)
    qtbot.addWidget(view)


def test_lists_seeded_skus(qtbot, repo):
    view = AdminView(repo)
    qtbot.addWidget(view)
    rows = view.sku_rows()
    assert any(r["sku"] == "LB-EXISTING" for r in rows)


def test_add_sku_persists_and_refreshes(qtbot, repo):
    view = AdminView(repo)
    qtbot.addWidget(view)
    # Use the public test seam, not the dialog (dialogs are modal & fiddly to drive).
    view.add_sku("LB-NEW-SKU", template_name="Wallet — S", material_name="Leather")
    rows = view.sku_rows()
    assert any(r["sku"] == "LB-NEW-SKU" for r in rows)
    # Persisted to repo too, not just the local table.
    assert repo.get(Sku("LB-NEW-SKU")) is not None


def test_back_button_emits_signal(qtbot, repo):
    view = AdminView(repo)
    qtbot.addWidget(view)
    received: list[bool] = []
    view.back_requested.connect(lambda: received.append(True))
    view.back_btn.click()
    assert received == [True]
