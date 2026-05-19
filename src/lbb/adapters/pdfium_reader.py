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

# Cubic Beziers are flattened to N straight-line segments. 8 samples per curve
# is invisible at typography scales (the laser's stepover is coarser than this
# anyway) and keeps the .lbrn2 file lean.
_BEZIER_SAMPLES = 8


def _fmt_mm(n: float) -> str:
    """Format a millimetre value: integers as int, decimals trimmed of trailing zeros."""
    if n == int(n):
        return str(int(n))
    return f"{n:.{_MM_PRECISION}f}".rstrip("0").rstrip(".")


def _flatten_cubic_bezier(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    n_samples: int = _BEZIER_SAMPLES,
) -> list[tuple[float, float]]:
    """Sample a cubic Bezier at N equally-spaced t-values and return the points.

    Samples are taken at t = 1/N, 2/N, …, 1.0 — the starting point P0 is
    excluded because the caller is already at P0 (it was the prior segment's
    endpoint). The final sample is P3 exactly, so polylines join cleanly.

    B(t) = (1-t)³·P0 + 3(1-t)²·t·P1 + 3(1-t)·t²·P2 + t³·P3
    """
    out: list[tuple[float, float]] = []
    for i in range(1, n_samples + 1):
        t = i / n_samples
        if i == n_samples:
            out.append(p3)
            continue
        u = 1.0 - t
        b0 = u * u * u
        b1 = 3 * u * u * t
        b2 = 3 * u * t * t
        b3 = t * t * t
        x = b0 * p0[0] + b1 * p1[0] + b2 * p2[0] + b3 * p3[0]
        y = b0 * p0[1] + b1 * p1[1] + b2 * p2[1] + b3 * p3[1]
        out.append((x, y))
    return out


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


def _read_segments(path_obj, page_h_mm: float) -> list[dict | None]:
    """Pre-extract every pdfium path segment into a list of dicts so the caller
    can do 3-segment lookahead for cubic Beziers without re-reading via FFI."""
    n_seg = pdfium_raw.FPDFPath_CountSegments(path_obj.raw)
    segments: list[dict | None] = []
    for j in range(n_seg):
        seg = pdfium_raw.FPDFPath_GetPathSegment(path_obj.raw, j)
        x_pt, y_pt = ctypes.c_float(), ctypes.c_float()
        if not pdfium_raw.FPDFPathSegment_GetPoint(seg, ctypes.byref(x_pt), ctypes.byref(y_pt)):
            segments.append(None)
            continue
        segments.append(
            {
                "type": pdfium_raw.FPDFPathSegment_GetType(seg),
                "x": round(pt_to_mm(x_pt.value), _MM_PRECISION),
                "y": round(page_h_mm - pt_to_mm(y_pt.value), _MM_PRECISION),
                "close": bool(pdfium_raw.FPDFPathSegment_GetClose(seg)),
            }
        )
    return segments


def _path_to_svg_d(path_obj, page_h_mm: float) -> str:
    """Walk a pdfium path object's segments and emit a canonical SVG-path string.

    Cubic Beziers (3 consecutive BEZIERTO segments for P1, P2, P3) are flattened
    into polyline samples via `_flatten_cubic_bezier`, so curves no longer
    silently disappear (HANDOFF §5.4 phase-1.5 enhancement).
    """
    segments = _read_segments(path_obj, page_h_mm)
    n_seg = len(segments)
    tokens: list[str] = []
    subpath_start: tuple[float, float] | None = None
    current: tuple[float, float] | None = None
    j = 0
    while j < n_seg:
        s = segments[j]
        if s is None:
            j += 1
            continue
        if s["type"] == _PDF_SEG_MOVETO:
            tokens.append(f"M {_fmt_mm(s['x'])} {_fmt_mm(s['y'])}")
            subpath_start = (s["x"], s["y"])
            current = (s["x"], s["y"])
            j += 1
        elif s["type"] == _PDF_SEG_LINETO:
            # Deduplicate the redundant closing line that re-targets the subpath start.
            if s["close"] and subpath_start == (s["x"], s["y"]):
                tokens.append("Z")
            else:
                tokens.append(f"L {_fmt_mm(s['x'])} {_fmt_mm(s['y'])}")
                if s["close"]:
                    tokens.append("Z")
            current = (s["x"], s["y"])
            j += 1
        elif s["type"] == _PDF_SEG_BEZIERTO:
            consumed, new_current = _emit_bezier_chunk(segments, j, current, tokens)
            if consumed == 0:
                j += 1
            else:
                current = new_current
                j += consumed
        else:
            j += 1
    return " ".join(tokens)


def _emit_bezier_chunk(
    segments: list[dict | None],
    j: int,
    current: tuple[float, float] | None,
    tokens: list[str],
) -> tuple[int, tuple[float, float] | None]:
    """Consume 3 consecutive BEZIERTO segments (P1, P2, P3) and append the
    flattened polyline to `tokens`. Returns (segments_consumed, new_current).
    Returns (0, current) if the Bezier chunk is malformed or truncated."""
    s1 = segments[j]
    s2 = segments[j + 1] if j + 1 < len(segments) else None
    s3 = segments[j + 2] if j + 2 < len(segments) else None
    if current is None or s1 is None or s2 is None or s3 is None:
        return 0, current
    p1 = (s1["x"], s1["y"])
    p2 = (s2["x"], s2["y"])
    p3 = (s3["x"], s3["y"])
    for sx, sy in _flatten_cubic_bezier(current, p1, p2, p3):
        tokens.append(
            f"L {_fmt_mm(round(sx, _MM_PRECISION))} {_fmt_mm(round(sy, _MM_PRECISION))}"
        )
    if s3["close"]:
        tokens.append("Z")
    return 3, p3
