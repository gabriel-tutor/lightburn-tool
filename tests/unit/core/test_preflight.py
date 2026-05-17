from lbb.core.preflight import PdfInfo, run_preflight


def _info(**kw) -> PdfInfo:
    defaults = {
        "page_count": 1,
        "is_vector_only": True,
        "stroke_colors": frozenset({"#000000"}),
        "bbox_mm": (50.0, 60.0),
    }
    defaults.update(kw)
    return PdfInfo(**defaults)


def test_passes_clean_pdf():
    result = run_preflight(_info(), canvas_mm=(95.0, 110.0))
    assert result.ok
    assert result.reasons == []


def test_fails_when_raster():
    result = run_preflight(_info(is_vector_only=False), canvas_mm=(95.0, 110.0))
    assert not result.ok
    assert any("vector" in r for r in result.reasons)


def test_fails_when_off_palette_color():
    result = run_preflight(_info(stroke_colors=frozenset({"#ABCDEF"})), canvas_mm=(95.0, 110.0))
    assert not result.ok
    assert any("palette" in r.lower() for r in result.reasons)


def test_fails_when_too_large():
    result = run_preflight(_info(bbox_mm=(200.0, 200.0)), canvas_mm=(95.0, 110.0))
    assert not result.ok
    assert any("canvas" in r.lower() for r in result.reasons)


def test_fails_when_multi_page():
    result = run_preflight(_info(page_count=3), canvas_mm=(95.0, 110.0))
    assert not result.ok
    assert any("page" in r.lower() for r in result.reasons)


def test_aggregates_multiple_failures():
    result = run_preflight(
        _info(is_vector_only=False, stroke_colors=frozenset({"#ABCDEF"})),
        canvas_mm=(10.0, 10.0),
    )
    assert len(result.reasons) >= 2
