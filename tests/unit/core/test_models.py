import pytest
from lbb.core.models import Material, Sku, SkuProfile, Template


def test_sku_is_frozen():
    s = Sku("LB-WALLET-LEATHER-S")
    with pytest.raises(AttributeError):
        s.value = "OTHER"


def test_sku_rejects_blank():
    with pytest.raises(ValueError, match="SKU cannot be blank"):
        Sku("   ")


def test_sku_strips_whitespace():
    assert Sku("  LB-X  ").value == "LB-X"


def test_profile_carries_template_and_material():
    t = Template(id=1, name="Wallet S", lbrn2_path="/x.lbrn2", canvas_w_mm=95, canvas_h_mm=110)
    m = Material(id=1, name="Leather 2mm", clb_library="default.clb", clb_entry="LeatherVT")
    p = SkuProfile(sku=Sku("LB-X"), template=t, material=m, overrides={})
    assert p.template.canvas_w_mm == 95
    assert p.material.clb_entry == "LeatherVT"
