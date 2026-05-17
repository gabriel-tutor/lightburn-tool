from dataclasses import dataclass

from lbb.core.palette import is_palette_color


@dataclass(frozen=True, slots=True)
class PdfInfo:
    page_count: int
    is_vector_only: bool
    stroke_colors: frozenset[str]
    bbox_mm: tuple[float, float]  # (width, height)


@dataclass(frozen=True, slots=True)
class PreflightResult:
    ok: bool
    reasons: list[str]


def run_preflight(info: PdfInfo, canvas_mm: tuple[float, float]) -> PreflightResult:
    reasons: list[str] = []
    if info.page_count != 1:
        reasons.append(f"expected 1 page, got {info.page_count}")
    if not info.is_vector_only:
        reasons.append("PDF contains raster content (must be vector-only)")
    off = sorted(c for c in info.stroke_colors if not is_palette_color(c))
    if off:
        reasons.append(f"stroke colors not in LightBurn palette: {', '.join(off)}")
    if info.bbox_mm[0] > canvas_mm[0] or info.bbox_mm[1] > canvas_mm[1]:
        reasons.append(
            f"design {info.bbox_mm[0]:.1f}×{info.bbox_mm[1]:.1f}mm exceeds "
            f"canvas {canvas_mm[0]:.1f}×{canvas_mm[1]:.1f}mm"
        )
    return PreflightResult(ok=not reasons, reasons=reasons)
