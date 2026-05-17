import ctypes
import io
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_raw

from lbb.core.preflight import PdfInfo
from lbb.ports.pdf import PdfReader

# ── Pure helpers (no I/O) ───────────────────────────────────────────────────


def color_to_hex(r: int, g: int, b: int) -> str:
    """Pack 0-255 channels into an uppercase #RRGGBB string."""
    return f"#{r:02X}{g:02X}{b:02X}"


def pt_to_mm(pt: float) -> float:
    """Convert PDF points (1/72 inch) to millimetres."""
    return pt * 25.4 / 72.0


def _stroke_color_rgb(obj) -> tuple[int, int, int] | None:
    """Pull a path object's stroke colour via pdfium's FFI. None if unavailable.

    pypdfium2 5.x doesn't surface this on the high-level PdfObject — we have to
    drop into the raw C API.
    """
    r, g, b, a = (ctypes.c_uint() for _ in range(4))
    ok = pdfium_raw.FPDFPageObj_GetStrokeColor(
        obj.raw, ctypes.byref(r), ctypes.byref(g), ctypes.byref(b), ctypes.byref(a)
    )
    if not ok:
        return None
    return r.value, g.value, b.value


# ── pypdfium2 wrapper (covered by gated integration test) ───────────────────


class PdfiumReader(PdfReader):
    def read_info(self, path: Path) -> PdfInfo:
        pdf = pdfium.PdfDocument(str(path))
        try:
            n_pages = len(pdf)
            page = pdf[0]
            w_mm = pt_to_mm(page.get_width())
            h_mm = pt_to_mm(page.get_height())
            is_vector_only = True
            stroke_colors: set[str] = set()
            for obj in page.get_objects():
                if obj.type == pdfium_raw.FPDF_PAGEOBJ_IMAGE:
                    is_vector_only = False
                elif obj.type == pdfium_raw.FPDF_PAGEOBJ_PATH:
                    rgb = _stroke_color_rgb(obj)
                    if rgb is not None:
                        stroke_colors.add(color_to_hex(*rgb))
            return PdfInfo(
                page_count=n_pages,
                is_vector_only=is_vector_only,
                stroke_colors=frozenset(stroke_colors),
                bbox_mm=(w_mm, h_mm),
            )
        finally:
            pdf.close()

    def render_thumbnail_png(self, path: Path, max_px: int) -> bytes:
        pdf = pdfium.PdfDocument(str(path))
        try:
            page = pdf[0]
            scale = max_px / max(page.get_width(), page.get_height())
            pil = page.render(scale=scale).to_pil()
            buf = io.BytesIO()
            pil.save(buf, format="PNG")
            return buf.getvalue()
        finally:
            pdf.close()
