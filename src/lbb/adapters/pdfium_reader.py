import ctypes
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_raw
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QImage

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


# PDF path segment type constants (FPDF_SEGMENT_*)
_PDF_SEG_LINETO = 0
_PDF_SEG_BEZIERTO = 1
_PDF_SEG_MOVETO = 2

# pdfium PdfBitmap.format codes (after rev_byteorder=True the channel order
# is the natural RGB/RGBA we want).
_PDF_BITMAP_GRAY = 1
_PDF_BITMAP_RGB = 2
_PDF_BITMAP_RGBX = 3
_PDF_BITMAP_RGBA = 4

# Coords from pdfium can drift by a few thousandths of a mm vs. the source design;
# round to this precision when emitting SVG so the output is stable and clean.
_MM_PRECISION = 2


def _fmt_mm(n: float) -> str:
    """Format a millimetre value: integers as int, decimals trimmed of trailing zeros."""
    if n == int(n):
        return str(int(n))
    return f"{n:.{_MM_PRECISION}f}".rstrip("0").rstrip(".")


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

    def extract_paths(self, path: Path) -> list[tuple[str, str]]:
        """Return list of (svg_d, stroke_color_hex). Coords are mm, top-left Y-down.

        Skips BEZIERTO segments (MVP supports straight lines only — curves
        are a future enhancement to both this reader and build_lbrn2).
        """
        pdf = pdfium.PdfDocument(str(path))
        try:
            page = pdf[0]
            page_h_mm = pt_to_mm(page.get_height())
            results: list[tuple[str, str]] = []
            for obj in page.get_objects():
                if obj.type != pdfium_raw.FPDF_PAGEOBJ_PATH:
                    continue
                rgb = _stroke_color_rgb(obj)
                if rgb is None:
                    continue
                d = _path_to_svg_d(obj, page_h_mm)
                if d:
                    results.append((d, color_to_hex(*rgb)))
            return results
        finally:
            pdf.close()

    def render_thumbnail_png(self, path: Path, max_px: int) -> bytes:
        """Render the first page to PNG bytes via Qt (no Pillow dependency).

        We use QImage instead of PdfBitmap.to_pil() because Pillow's vendored
        zlib conflicts with PyInstaller's bundled zlib in production .apps,
        manifesting as 'zlib.error: Error -3 incorrect header check' when
        users pick a PDF. Qt already provides PNG encoding and ships with us.
        """
        pdf = pdfium.PdfDocument(str(path))
        try:
            page = pdf[0]
            scale = max_px / max(page.get_width(), page.get_height())
            bitmap = page.render(scale=scale, rev_byteorder=True)
            qfmt = _qimage_format_for(bitmap.format)
            qimg = QImage(
                bytes(bitmap.buffer),
                bitmap.width,
                bitmap.height,
                bitmap.stride,
                qfmt,
            )
            if qimg.isNull():
                raise RuntimeError(
                    f"Could not construct QImage from pdfium bitmap "
                    f"(format={bitmap.format}, {bitmap.width}x{bitmap.height}, "
                    f"stride={bitmap.stride})"
                )
            buf = QBuffer()
            buf.open(QIODevice.WriteOnly)
            qimg.save(buf, "PNG")
            return bytes(buf.data())
        finally:
            pdf.close()


def _qimage_format_for(pdfium_format: int) -> QImage.Format:
    """Map a pypdfium2 PdfBitmap.format code to the QImage format with
    matching channel count/order. rev_byteorder=True was passed at render."""
    if pdfium_format == _PDF_BITMAP_GRAY:
        return QImage.Format_Grayscale8
    if pdfium_format == _PDF_BITMAP_RGB:
        return QImage.Format_RGB888
    if pdfium_format == _PDF_BITMAP_RGBX:
        return QImage.Format_RGBX8888
    if pdfium_format == _PDF_BITMAP_RGBA:
        return QImage.Format_RGBA8888
    return QImage.Format_RGB888  # safest default


def _path_to_svg_d(path_obj, page_h_mm: float) -> str:
    """Walk a pdfium path object's segments and emit a canonical SVG-path string."""
    n_seg = pdfium_raw.FPDFPath_CountSegments(path_obj.raw)
    tokens: list[str] = []
    subpath_start: tuple[float, float] | None = None
    for j in range(n_seg):
        seg = pdfium_raw.FPDFPath_GetPathSegment(path_obj.raw, j)
        x_pt, y_pt = ctypes.c_float(), ctypes.c_float()
        if not pdfium_raw.FPDFPathSegment_GetPoint(seg, ctypes.byref(x_pt), ctypes.byref(y_pt)):
            continue
        x_mm = round(pt_to_mm(x_pt.value), _MM_PRECISION)
        y_mm = round(page_h_mm - pt_to_mm(y_pt.value), _MM_PRECISION)
        seg_type = pdfium_raw.FPDFPathSegment_GetType(seg)
        is_close = bool(pdfium_raw.FPDFPathSegment_GetClose(seg))

        if seg_type == _PDF_SEG_MOVETO:
            tokens.append(f"M {_fmt_mm(x_mm)} {_fmt_mm(y_mm)}")
            subpath_start = (x_mm, y_mm)
        elif seg_type == _PDF_SEG_LINETO:
            # Deduplicate the redundant closing line that re-targets the subpath start.
            if is_close and subpath_start == (x_mm, y_mm):
                tokens.append("Z")
            else:
                tokens.append(f"L {_fmt_mm(x_mm)} {_fmt_mm(y_mm)}")
                if is_close:
                    tokens.append("Z")
        # BEZIERTO and any unknown type: skip (MVP straight-lines only).
    return " ".join(tokens)
