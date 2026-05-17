from pathlib import Path

import pytest

from lbb.adapters.pdfium_reader import PdfiumReader, color_to_hex, pt_to_mm

# Integration test depends on a real PDF fixture. Until the
# fixture-generation script lands (task #21), this test skips.
FIXTURE = Path(__file__).parents[2] / "fixtures" / "pdfs" / "sample-vector.pdf"


# ── Pure helpers (no fixture, full TDD) ─────────────────────────────────────


def test_color_to_hex_basic():
    assert color_to_hex(0, 0, 0) == "#000000"


def test_color_to_hex_uppercase():
    assert color_to_hex(255, 0, 0) == "#FF0000"


def test_color_to_hex_mixed():
    assert color_to_hex(128, 200, 64) == "#80C840"


def test_pt_to_mm_zero():
    assert pt_to_mm(0.0) == 0.0


def test_pt_to_mm_one_inch():
    # 72 PDF points == 1 inch == 25.4 mm
    assert pt_to_mm(72.0) == pytest.approx(25.4, rel=1e-6)


def test_pt_to_mm_a4_width():
    # A4 width is conventionally 595 PDF points, which converts to ~209.90 mm
    # (the actual A4 spec is 210 mm; 595 pt is the rounded PDF value).
    assert pt_to_mm(595.0) == pytest.approx(209.90, abs=0.01)


# ── Integration (gated on fixture) ──────────────────────────────────────────


@pytest.mark.skipif(not FIXTURE.exists(), reason="fixture PDF missing (see task #21)")
def test_reads_basic_info():
    r = PdfiumReader()
    info = r.read_info(FIXTURE)
    assert info.page_count == 1
    assert info.is_vector_only is True
    assert "#000000" in {c.lower() for c in info.stroke_colors}
    assert info.bbox_mm[0] > 0 and info.bbox_mm[1] > 0
