import pytest

from lbb.adapters.sqlite_repo import SqliteProfileRepository
from lbb.core.models import Material, Sku, SkuProfile, Template


@pytest.fixture
def repo(tmp_path):
    return SqliteProfileRepository(tmp_path / "p.sqlite")


def test_returns_none_for_unknown_sku(repo):
    assert repo.get(Sku("MISSING")) is None


def test_upsert_and_get(repo):
    t = repo.upsert_template(
        Template(id=0, name="W S", lbrn2_path="/x.lbrn2", canvas_w_mm=95, canvas_h_mm=110)
    )
    m = repo.upsert_material(Material(id=0, name="Leather", clb_library="d.clb", clb_entry="L"))
    repo.upsert(SkuProfile(sku=Sku("LB-X"), template=t, material=m, overrides={}))

    got = repo.get(Sku("LB-X"))
    assert got is not None
    assert got.template.name == "W S"
    assert got.material.name == "Leather"


def test_list_materials(repo):
    repo.upsert_material(Material(id=0, name="A", clb_library="x", clb_entry="A"))
    repo.upsert_material(Material(id=0, name="B", clb_library="x", clb_entry="B"))
    assert {m.name for m in repo.list_materials()} == {"A", "B"}


def test_list_templates(repo):
    repo.upsert_template(Template(id=0, name="T1", lbrn2_path="/1", canvas_w_mm=50, canvas_h_mm=60))
    repo.upsert_template(Template(id=0, name="T2", lbrn2_path="/2", canvas_w_mm=70, canvas_h_mm=80))
    assert {t.name for t in repo.list_templates()} == {"T1", "T2"}


def test_upsert_replaces_existing_mapping(repo):
    t1 = repo.upsert_template(
        Template(id=0, name="T1", lbrn2_path="/1", canvas_w_mm=50, canvas_h_mm=60)
    )
    t2 = repo.upsert_template(
        Template(id=0, name="T2", lbrn2_path="/2", canvas_w_mm=70, canvas_h_mm=80)
    )
    m = repo.upsert_material(Material(id=0, name="M", clb_library="x", clb_entry="M"))

    repo.upsert(SkuProfile(Sku("LB-X"), t1, m, {}))
    repo.upsert(SkuProfile(Sku("LB-X"), t2, m, {}))

    got = repo.get(Sku("LB-X"))
    assert got is not None
    assert got.template.name == "T2"


def test_list_profiles_empty_returns_empty_list(repo):
    assert repo.list_profiles() == []


def test_list_profiles_returns_all_joined_sorted_by_sku(repo):
    t = repo.upsert_template(
        Template(id=0, name="T", lbrn2_path="/x", canvas_w_mm=50, canvas_h_mm=60)
    )
    m = repo.upsert_material(Material(id=0, name="M", clb_library="x", clb_entry="M"))
    # Insert out of order — list_profiles must return sorted by SKU
    repo.upsert(SkuProfile(Sku("LB-B"), t, m, {}))
    repo.upsert(SkuProfile(Sku("LB-A"), t, m, {"speed": 200}))

    profiles = repo.list_profiles()
    assert [p.sku.value for p in profiles] == ["LB-A", "LB-B"]
    # Each profile must be fully joined (template + material populated)
    assert profiles[0].template.name == "T"
    assert profiles[0].material.name == "M"
    # Overrides JSON must round-trip
    assert profiles[0].overrides == {"speed": 200}
    assert profiles[1].overrides == {}


def test_overrides_json_roundtrip(repo):
    t = repo.upsert_template(
        Template(id=0, name="T", lbrn2_path="/x", canvas_w_mm=50, canvas_h_mm=60)
    )
    m = repo.upsert_material(Material(id=0, name="M", clb_library="x", clb_entry="M"))
    overrides = {"speed_mm_s": 200, "power_pct": 35, "notes": "fast"}
    repo.upsert(SkuProfile(Sku("LB-X"), t, m, overrides))

    got = repo.get(Sku("LB-X"))
    assert got is not None
    assert got.overrides == overrides
