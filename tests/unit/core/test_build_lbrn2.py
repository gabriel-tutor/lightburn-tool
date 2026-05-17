from pathlib import Path

from lxml import etree

from lbb.core.template_builder import build_lbrn2, locate_placeholder

TEMPLATE = Path(__file__).parents[3] / "templates" / "wallet-small.lbrn2"
GOLDEN = Path(__file__).parents[2] / "golden" / "wallet-small-rect.lbrn2"

RECT_PATH = "M 10 10 L 60 10 L 60 50 L 10 50 Z"


def _placeholder(out_bytes: bytes) -> etree._Element:
    return locate_placeholder(etree.ElementTree(etree.fromstring(out_bytes)))


# ── Semantic tests (drive the implementation) ────────────────────────────────


def test_replaces_placeholder_with_new_shape():
    out = build_lbrn2(template_path=TEMPLATE, shapes=[(RECT_PATH, 0)])
    placeholder = _placeholder(out)
    children = placeholder.find("Children")
    new_shape = children.find("Shape")
    assert new_shape.get("Type") == "Path"
    assert new_shape.get("CutIndex") == "0"


def test_encodes_vertices_in_lbrn2_string_format():
    out = build_lbrn2(template_path=TEMPLATE, shapes=[(RECT_PATH, 0)])
    placeholder = _placeholder(out)
    vert_list = placeholder.find("Children/Shape/VertList").text
    assert vert_list == ("V10 10c0x1c1x1V60 10c0x1c1x1V60 50c0x1c1x1V10 50c0x1c1x1")


def test_encodes_closing_primitive_as_line_to_start():
    out = build_lbrn2(template_path=TEMPLATE, shapes=[(RECT_PATH, 0)])
    placeholder = _placeholder(out)
    prim_list = placeholder.find("Children/Shape/PrimList").text
    assert prim_list == "L0 1L1 2L2 3L3 0"


def test_open_path_has_no_closing_primitive():
    # Same rectangle but without Z — should not close back to vertex 0
    open_path = "M 10 10 L 60 10 L 60 50 L 10 50"
    out = build_lbrn2(template_path=TEMPLATE, shapes=[(open_path, 0)])
    placeholder = _placeholder(out)
    prim_list = placeholder.find("Children/Shape/PrimList").text
    assert prim_list == "L0 1L1 2L2 3"


def test_preserves_cut_setting_from_template():
    out = build_lbrn2(template_path=TEMPLATE, shapes=[(RECT_PATH, 0)])
    tree = etree.fromstring(out)
    cut_setting = tree.find("CutSetting")
    assert cut_setting.get("type") == "Cut"
    assert cut_setting.find("name").get("Value") == "C00"
    assert cut_setting.find("speed").get("Value") == "16.6667"


def test_multiple_shapes_become_separate_path_elements():
    out = build_lbrn2(
        template_path=TEMPLATE,
        shapes=[("M 0 0 L 10 0 Z", 0), ("M 20 20 L 30 20 Z", 1)],
    )
    placeholder = _placeholder(out)
    shapes = placeholder.find("Children").findall("Shape")
    assert len(shapes) == 2
    assert shapes[0].get("CutIndex") == "0"
    assert shapes[1].get("CutIndex") == "1"


def test_clears_previous_placeholder_children():
    out = build_lbrn2(template_path=TEMPLATE, shapes=[(RECT_PATH, 0)])
    placeholder = _placeholder(out)
    # Template had 1 placeholder rect. After build, only our 1 new shape.
    assert len(placeholder.find("Children").findall("Shape")) == 1


# ── Golden file (schema-drift detector) ─────────────────────────────────────


def test_byte_stable_against_golden():
    """Locks exact byte output for a known input. If this fails, either:
      (a) the template fixture changed — review and regenerate the golden, OR
      (b) the builder logic changed — review and regenerate the golden, OR
      (c) lxml's output format changed — investigate before regenerating.
    Regenerate via: uv run python scripts/regenerate_goldens.py
    """
    out = build_lbrn2(template_path=TEMPLATE, shapes=[(RECT_PATH, 0)])
    assert out == GOLDEN.read_bytes()
