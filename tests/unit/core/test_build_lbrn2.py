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


def test_multi_subpath_string_emits_separate_shapes_no_spurious_connectors():
    """A single SVG `d` string with multiple `M` commands must produce a
    SEPARATE <Shape> per subpath — not one polyline that connects them.
    Regression for: customer PDFs whose typography uses compound paths
    (e.g. letter 'O' has outer + inner subpaths) were getting rendered as
    one giant tangled polyline because all subpaths collapsed into one
    VertList with spurious connecting lines between them."""
    # Two disjoint rectangles in a single `d` string (a compound path).
    compound = "M 0 0 L 10 0 L 10 10 L 0 10 Z M 20 20 L 30 20 L 30 30 L 20 30 Z"
    out = build_lbrn2(template_path=TEMPLATE, shapes=[(compound, 0)])
    placeholder = _placeholder(out)
    shapes = placeholder.find("Children").findall("Shape")
    # Two subpaths → two Shape elements (not one merged polyline).
    assert len(shapes) == 2, (
        f"expected 2 subpath shapes, got {len(shapes)} — compound path collapsed"
    )
    # Both share the same CutIndex (came from the same source path).
    assert all(s.get("CutIndex") == "0" for s in shapes)
    # Each has its own 4 vertices, NOT 8 jumbled vertices.
    for shape in shapes:
        verts = shape.find("VertList").text
        assert verts.count("V") == 4, f"shape has {verts.count('V')} verts, expected 4"
    # Neither vertex list bridges between the two rectangles.
    s0_verts = shapes[0].find("VertList").text
    s1_verts = shapes[1].find("VertList").text
    assert "V20" not in s0_verts, "first subpath leaked vertices from the second"
    assert "V0 0" not in s1_verts, "second subpath leaked the first subpath's start"


def test_multi_subpath_open_path_not_closed():
    """Multi-subpath strings without Z must NOT add closing primitives."""
    open_compound = "M 0 0 L 10 0 L 10 10 M 20 20 L 30 20 L 30 30"
    out = build_lbrn2(template_path=TEMPLATE, shapes=[(open_compound, 0)])
    placeholder = _placeholder(out)
    shapes = placeholder.find("Children").findall("Shape")
    assert len(shapes) == 2
    # Each subpath has 3 vertices, 2 edges, no closing edge.
    for shape in shapes:
        prim = shape.find("PrimList").text
        assert prim == "L0 1L1 2", f"open subpath got closing edge: {prim}"


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
