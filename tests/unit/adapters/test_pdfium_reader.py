from pathlib import Path

import pytest

from lbb.adapters.pdfium_reader import (
    PdfiumReader,
    _flatten_cubic_bezier,
    color_to_hex,
    pt_to_mm,
)

# Integration test depends on a real PDF fixture. Until the
# fixture-generation script lands (task #21), this test skips.
FIXTURE = Path(__file__).parents[2] / "fixtures" / "pdfs" / "sample-vector.pdf"
CURVE_FIXTURE = Path(__file__).parents[2] / "fixtures" / "pdfs" / "curve-test.pdf"


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


# ── Bezier flattening (pure function) ───────────────────────────────────────


def test_flatten_cubic_bezier_returns_requested_sample_count():
    """N samples means N points along the curve, ending exactly at P3."""
    samples = _flatten_cubic_bezier((0, 0), (1, 1), (2, 1), (3, 0), n_samples=8)
    assert len(samples) == 8


def test_flatten_cubic_bezier_endpoint_equals_p3():
    """The last sample must equal P3 (curve endpoint), with no rounding drift."""
    p3 = (12.5, 7.3)
    samples = _flatten_cubic_bezier((0, 0), (5, 10), (10, 10), p3, n_samples=8)
    # Last sample is P3 exactly (rounded to mm precision)
    assert samples[-1] == pytest.approx(p3, abs=1e-9)


def test_flatten_cubic_bezier_midpoint_on_quarter_curve():
    """Quarter-circle parametrised as standard 4-Bezier circle approximation:
    P0=(1,0) P1=(1,0.5523) P2=(0.5523,1) P3=(0,1). Midpoint t=0.5 should sit
    near the circle's 45° point ~(0.707, 0.707)."""
    samples = _flatten_cubic_bezier(
        (1, 0), (1, 0.5523), (0.5523, 1), (0, 1), n_samples=2
    )
    # First sample is t=0.5, second is t=1.0
    mid_x, mid_y = samples[0]
    assert abs(mid_x - 0.707) < 0.01
    assert abs(mid_y - 0.707) < 0.01


def test_flatten_cubic_bezier_linear_curve_lies_on_line():
    """When control points lie on the line P0-P3, flattening should produce
    samples that also lie on that line (a degenerate-to-line case)."""
    samples = _flatten_cubic_bezier((0, 0), (1, 1), (2, 2), (3, 3), n_samples=4)
    for x, y in samples:
        assert abs(x - y) < 1e-6


# ── Integration (gated on fixture) ──────────────────────────────────────────


@pytest.mark.skipif(not CURVE_FIXTURE.exists(), reason="curve-test.pdf fixture missing")
def test_extract_paths_flattens_beziers_into_polylines():
    """The curve-test.pdf fixture is an ellipse — fpdf2 emits it as cubic
    Beziers. Before flattening was implemented these segments were silently
    dropped, leaving paths with only MOVETO (and the design vanished). After
    flattening, each Bezier becomes a sequence of L commands."""
    paths = PdfiumReader().extract_paths(CURVE_FIXTURE)
    assert len(paths) >= 1, "no paths extracted from ellipse fixture"
    svg_d, _color = paths[0]
    # The ellipse has zero LINETOs in PDF (fpdf2 draws it purely with curves).
    # If Beziers are dropped, we'd see roughly 1 MOVETO and nothing else.
    # With flattening at N=8 samples × 4 curves = ~32 L commands.
    n_L = svg_d.count("L ")
    assert n_L >= 16, f"expected ≥16 L commands from flattened ellipse, got {n_L} in: {svg_d}"


@pytest.mark.skipif(not FIXTURE.exists(), reason="fixture PDF missing (see task #21)")
def test_reads_basic_info():
    r = PdfiumReader()
    info = r.read_info(FIXTURE)
    assert info.page_count == 1
    assert info.is_vector_only is True
    assert "#000000" in {c.lower() for c in info.stroke_colors}
    assert info.bbox_mm[0] > 0 and info.bbox_mm[1] > 0


@pytest.mark.skipif(not FIXTURE.exists(), reason="fixture PDF missing")
def test_render_thumbnail_png_produces_valid_png_via_qimage(qtbot):
    """Round-trips a PNG through QImage encoding. Regression guard for the
    bundle-side zlib conflict that arose when Pillow was used."""
    r = PdfiumReader()
    png = r.render_thumbnail_png(FIXTURE, 256)
    # PNG magic header
    assert png.startswith(b"\x89PNG\r\n\x1a\n"), "missing PNG magic — not a real PNG"
    assert len(png) > 100, "PNG suspiciously small"
