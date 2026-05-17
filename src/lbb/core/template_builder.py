"""Build a `.lbrn2` file by injecting design geometry into a base template.

Schema reference: nuCarve + forum.lightburnsoftware.com + community samples.
Key encoding quirks:
  • <VertList> is a STRING (not nested XML): "V<x> <y>c0x1c1x1..."
  • <PrimList> is a STRING: "L<i> <j>L<j> <k>..."
  • Groups wrap children in <Children>...</Children>
  • A closed path emits a final "L<last> 0" primitive (no special close token)
"""

from __future__ import annotations

import re
from pathlib import Path

from lxml import etree

PLACEHOLDER_NAME = "DESIGN_PLACEHOLDER"

# A path needs at least two vertices to have a closing edge between them.
_MIN_VERTS_FOR_CLOSE = 2


class TemplateError(Exception):
    """A `.lbrn2` template did not conform to LightBurn Bridge's contract."""


def locate_placeholder(tree: etree._ElementTree) -> etree._Element:
    """Return the <Shape Type="Group" Name="DESIGN_PLACEHOLDER"> element.

    Raises TemplateError if the template doesn't contain it.
    """
    for el in tree.iter():
        if el.tag == "Shape" and el.get("Type") == "Group" and el.get("Name") == PLACEHOLDER_NAME:
            return el
    raise TemplateError(
        f"Template missing required group with Name='{PLACEHOLDER_NAME}' (Type='Group')"
    )


def build_lbrn2(*, template_path: Path, shapes: list[tuple[str, int]]) -> bytes:
    """Generate a `.lbrn2` by stamping SVG-path shapes into the template's placeholder.

    Args:
        template_path: Path to a base .lbrn2 template containing a
            DESIGN_PLACEHOLDER group.
        shapes: List of (svg_path_d, cut_index) tuples. svg_path_d supports
            M, L, Z commands only for MVP. cut_index references a <CutSetting>
            <index> in the template (0–29).

    Returns:
        Bytes of the rewritten .lbrn2 file, ready to write to disk.
    """
    tree = etree.parse(str(template_path))
    placeholder = locate_placeholder(tree)
    children_el = placeholder.find("Children")
    if children_el is None:
        raise TemplateError("Placeholder group is missing its <Children> wrapper element")

    # Clear out anything the template had inside the placeholder.
    for child in list(children_el):
        children_el.remove(child)

    # Stamp new shapes.
    for d, cut_index in shapes:
        verts, closed = _parse_svg_path(d)
        shape = etree.SubElement(
            children_el,
            "Shape",
            {"Type": "Path", "CutIndex": str(cut_index)},
        )
        xform = etree.SubElement(shape, "XForm")
        xform.text = "1 0 0 1 0 0"
        vert_list = etree.SubElement(shape, "VertList")
        vert_list.text = "".join(_format_vertex(x, y) for x, y in verts)
        prim_list = etree.SubElement(shape, "PrimList")
        prim_list.text = _format_primitives(len(verts), closed=closed)

    return etree.tostring(tree, xml_declaration=True, encoding="UTF-8", pretty_print=True)


# ── SVG path parsing (M, L, Z only — MVP) ───────────────────────────────────


_SVG_TOKEN_RE = re.compile(r"([MLZmlz])\s*([0-9.\-\s,]*)")


def _parse_svg_path(d: str) -> tuple[list[tuple[float, float]], bool]:
    """Return (vertex list, closed flag) from an SVG path 'd' string.

    Supports absolute M/L and Z only. Relative variants (m/l) and curves
    (C/Q/etc.) are out of scope for MVP — Phase 1.5 enhancement.
    """
    verts: list[tuple[float, float]] = []
    closed = False
    for cmd, args in _SVG_TOKEN_RE.findall(d):
        nums = [float(n) for n in args.replace(",", " ").split()] if args.strip() else []
        if cmd in ("M", "m", "L", "l"):
            for i in range(0, len(nums), 2):
                verts.append((nums[i], nums[i + 1]))
        elif cmd in ("Z", "z"):
            closed = True
    return verts, closed


# ── LightBurn-format emitters ───────────────────────────────────────────────


def _format_vertex(x: float, y: float) -> str:
    """`V<x> <y>c0x1c1x1` — c0x1c1x1 marks 'no Bezier handles' (line vertex)."""
    return f"V{_fmt_num(x)} {_fmt_num(y)}c0x1c1x1"


def _format_primitives(n_verts: int, *, closed: bool) -> str:
    """Connect verts 0→1→2→…→n-1, plus closing edge n-1→0 if closed=True."""
    edges = [f"L{i} {i + 1}" for i in range(n_verts - 1)]
    if closed and n_verts >= _MIN_VERTS_FOR_CLOSE:
        edges.append(f"L{n_verts - 1} 0")
    return "".join(edges)


def _fmt_num(n: float) -> str:
    """Integers as integers, decimals trimmed of trailing zeros."""
    if n == int(n):
        return str(int(n))
    return f"{n:.4f}".rstrip("0").rstrip(".")
