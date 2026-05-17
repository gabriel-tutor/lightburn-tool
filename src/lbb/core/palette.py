# LightBurn's fixed 30-color cut-layer palette.
# Source: https://docs.lightburnsoftware.com/latest/Reference/UI/ColorPalette/
PALETTE: tuple[str, ...] = (
    "#000000", "#0000FF", "#FF0000", "#00E000", "#D0D000",
    "#FF8000", "#00E0E0", "#FF00FF", "#B4B4B4", "#5050FF",
    "#7D4000", "#509050", "#1818A0", "#A03000", "#A050A0",
    "#A0A050", "#505000", "#003030", "#A04030", "#7D6045",
    "#88BB45", "#8000A0", "#404040", "#707000", "#700070",
    "#702070", "#702000", "#207020", "#202070", "#702020",
)  # fmt: skip

_INDEX = {c.lower(): i for i, c in enumerate(PALETTE)}


def is_palette_color(hex_color: str) -> bool:
    return hex_color.lower() in _INDEX


def layer_index_for_color(hex_color: str) -> int | None:
    return _INDEX.get(hex_color.lower())
