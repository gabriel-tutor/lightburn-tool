from lxml import etree

PLACEHOLDER_NAME = "DESIGN_PLACEHOLDER"


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
