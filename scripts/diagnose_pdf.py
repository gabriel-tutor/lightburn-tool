"""One-shot diagnostic: enumerate what pdfium actually sees in a PDF.

Usage:
    uv run python scripts/diagnose_pdf.py <path-to-pdf>

Counts page objects by type (path / text / image / form / shading), then for
each path counts MOVETO/LINETO/BEZIERTO segments + bbox + stroke/fill state.
This is the evidence-gathering tool for "why does this PDF render badly?"
"""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

import pypdfium2 as pdfium
from pypdfium2 import raw

# Show first N paths individually + any paths exceeding _BIG_PATH_SEGS segments.
_DETAIL_LIMIT = 5
_BIG_PATH_SEGS = 20

_TYPE_NAMES = {
    raw.FPDF_PAGEOBJ_TEXT: "TEXT",
    raw.FPDF_PAGEOBJ_PATH: "PATH",
    raw.FPDF_PAGEOBJ_IMAGE: "IMAGE",
    raw.FPDF_PAGEOBJ_SHADING: "SHADING",
    raw.FPDF_PAGEOBJ_FORM: "FORM",
}
_SEG_NAMES = {0: "LINETO", 1: "BEZIERTO", 2: "MOVETO"}


def _stroke_rgb(obj) -> tuple[int, int, int, int] | None:
    r, g, b, a = (ctypes.c_uint() for _ in range(4))
    if not raw.FPDFPageObj_GetStrokeColor(
        obj.raw, ctypes.byref(r), ctypes.byref(g), ctypes.byref(b), ctypes.byref(a)
    ):
        return None
    return r.value, g.value, b.value, a.value


def _fill_rgb(obj) -> tuple[int, int, int, int] | None:
    r, g, b, a = (ctypes.c_uint() for _ in range(4))
    if not raw.FPDFPageObj_GetFillColor(
        obj.raw, ctypes.byref(r), ctypes.byref(g), ctypes.byref(b), ctypes.byref(a)
    ):
        return None
    return r.value, g.value, b.value, a.value


def main(pdf_path: Path) -> None:
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        print(f"File: {pdf_path}")
        print(f"Pages: {len(pdf)}")
        page = pdf[0]
        w_pt, h_pt = page.get_width(), page.get_height()
        print(f"Page 0 size: {w_pt:.1f} x {h_pt:.1f} pt  "
              f"({w_pt * 25.4 / 72:.1f} x {h_pt * 25.4 / 72:.1f} mm)")

        # Top-level object counts
        type_counts: dict[str, int] = {}
        path_objects = []
        for obj in page.get_objects():
            name = _TYPE_NAMES.get(obj.type, f"UNKNOWN-{obj.type}")
            type_counts[name] = type_counts.get(name, 0) + 1
            if obj.type == raw.FPDF_PAGEOBJ_PATH:
                path_objects.append(obj)

        print("\nTop-level page objects:")
        for name, n in sorted(type_counts.items()):
            print(f"  {name:8} : {n}")

        # Per-path segment counts
        print(f"\nPath objects ({len(path_objects)} total):")
        agg = {"MOVETO": 0, "LINETO": 0, "BEZIERTO": 0}
        n_with_stroke = 0
        n_with_fill = 0
        for i, obj in enumerate(path_objects[:50]):  # show first 50
            n_seg = raw.FPDFPath_CountSegments(obj.raw)
            seg_counts = {"MOVETO": 0, "LINETO": 0, "BEZIERTO": 0}
            for j in range(n_seg):
                seg = raw.FPDFPath_GetPathSegment(obj.raw, j)
                t = raw.FPDFPathSegment_GetType(seg)
                seg_counts[_SEG_NAMES.get(t, f"?{t}")] = seg_counts.get(
                    _SEG_NAMES.get(t, f"?{t}"), 0
                ) + 1
            for k, v in seg_counts.items():
                agg[k] = agg.get(k, 0) + v
            sc = _stroke_rgb(obj)
            fc = _fill_rgb(obj)
            if sc and sc[3] > 0:
                n_with_stroke += 1
            if fc and fc[3] > 0:
                n_with_fill += 1
            if i < _DETAIL_LIMIT or n_seg > _BIG_PATH_SEGS:
                print(
                    f"  path #{i:<3} n_seg={n_seg:<4} "
                    f"M={seg_counts['MOVETO']:<3} L={seg_counts['LINETO']:<3} "
                    f"B={seg_counts['BEZIERTO']:<3}  "
                    f"stroke={sc} fill={fc}"
                )

        print("\nAggregate segments across all paths:")
        for k, v in agg.items():
            print(f"  {k:8} : {v}")
        print(f"\nPaths with stroke color (alpha>0): {n_with_stroke}")
        print(f"Paths with fill color (alpha>0):   {n_with_fill}")
        print(
            f"\nExtraction yield estimate: BEZIERTO ({agg['BEZIERTO']}) gets dropped, "
            f"MOVETO+LINETO ({agg['MOVETO'] + agg['LINETO']}) survive. "
            f"Fraction of segments preserved: "
            f"{(agg['MOVETO'] + agg['LINETO']) / max(1, sum(agg.values())):.1%}"
        )

    finally:
        pdf.close()


if __name__ == "__main__":
    main(Path(sys.argv[1]))
