from pathlib import Path

import pytest
from lxml import etree

from lbb.core.template_builder import (
    PLACEHOLDER_NAME,
    TemplateError,
    locate_placeholder,
)

TEMPLATE = Path(__file__).parents[3] / "templates" / "wallet-small.lbrn2"


def test_finds_placeholder_group():
    tree = etree.parse(str(TEMPLATE))
    node = locate_placeholder(tree)
    assert node.get("Name") == PLACEHOLDER_NAME
    assert node.get("Type") == "Group"


def test_placeholder_has_children_element():
    tree = etree.parse(str(TEMPLATE))
    node = locate_placeholder(tree)
    children = node.find("Children")
    assert children is not None  # required wrapper element in .lbrn2 groups


def test_raises_when_placeholder_missing(tmp_path):
    bare = tmp_path / "bare.lbrn2"
    bare.write_text('<?xml version="1.0"?><LightBurnProject FormatVersion="1"></LightBurnProject>')
    tree = etree.parse(str(bare))
    with pytest.raises(TemplateError, match="DESIGN_PLACEHOLDER"):
        locate_placeholder(tree)
