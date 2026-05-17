from pathlib import Path

from lbb.adapters.pdfium_reader import PdfiumReader

FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "pdfs"
SAMPLE = FIXTURE_DIR / "sample-vector.pdf"
WALLET = FIXTURE_DIR / "LB-WALLET-LEATHER-S__demo.pdf"


def test_returns_one_path_from_rectangle_pdf():
    paths = PdfiumReader().extract_paths(SAMPLE)
    assert len(paths) == 1


def test_returns_svg_d_string_and_color():
    paths = PdfiumReader().extract_paths(SAMPLE)
    d, color = paths[0]
    assert d.startswith("M ")
    assert color.upper() == "#000000"


def test_closes_with_z_when_pdf_path_is_closed():
    paths = PdfiumReader().extract_paths(SAMPLE)
    d, _ = paths[0]
    assert d.endswith(" Z")


def test_coords_are_mm_top_left_origin():
    """Sample PDF is a 40×50mm rect at (5, 5) on a 50×60mm canvas.
    After PDF→mm conversion + Y-flip we expect exactly these integer coords."""
    paths = PdfiumReader().extract_paths(SAMPLE)
    d, _ = paths[0]
    assert d == "M 5 5 L 45 5 L 45 55 L 5 55 Z"


def test_returns_multiple_paths_with_distinct_colors():
    """Wallet demo PDF has two rects: black cut + blue engrave."""
    paths = PdfiumReader().extract_paths(WALLET)
    colors = {color.upper() for _, color in paths}
    assert len(paths) == 2
    assert "#000000" in colors
    assert "#0000FF" in colors
