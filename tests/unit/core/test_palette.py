from lbb.core.palette import PALETTE, is_palette_color, layer_index_for_color


def test_palette_has_30_entries():
    assert len(PALETTE) == 30


def test_layer_zero_is_black():
    assert PALETTE[0].lower() == "#000000"


def test_layer_one_is_blue():
    assert PALETTE[1].lower() == "#0000ff"


def test_layer_two_is_red():
    assert PALETTE[2].lower() == "#ff0000"


def test_is_palette_color_case_insensitive():
    assert is_palette_color("#000000")
    assert is_palette_color("#000000".upper())
    assert is_palette_color("#FF0000")
    assert not is_palette_color("#ABCDEF")


def test_layer_index_lookup():
    assert layer_index_for_color("#0000FF") == 1
    assert layer_index_for_color("#abcdef") is None
