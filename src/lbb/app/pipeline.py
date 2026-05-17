"""The job pipeline: PDF → SKU → preflight → .lbrn2 → LightBurn.

Pure orchestration. All side effects flow through the injected Port adapters.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from lbb.app.job import Job, JobResult
from lbb.core.errors import LbbError, PreflightFailed, SkuNotFound
from lbb.core.extractor import extract_sku
from lbb.core.preflight import run_preflight
from lbb.core.template_builder import build_lbrn2
from lbb.ports.lightburn import LightBurnPort
from lbb.ports.pdf import PdfReader
from lbb.ports.repository import ProfileRepository


@dataclass(frozen=True, slots=True)
class PipelineDeps:
    repo: ProfileRepository
    pdf: PdfReader
    lightburn: LightBurnPort
    temp_dir: Path


def run_pipeline(job: Job, deps: PipelineDeps) -> JobResult:
    """Execute the full job pipeline. Domain errors are caught and surfaced
    through JobResult.error so the UI can render them; unexpected errors
    still bubble up so they're not silently swallowed."""
    try:
        sku = extract_sku(job.source_pdf.name)
        profile = deps.repo.get(sku)
        if profile is None:
            raise SkuNotFound(sku.value)

        info = deps.pdf.read_info(job.source_pdf)
        pf = run_preflight(
            info,
            canvas_mm=(profile.template.canvas_w_mm, profile.template.canvas_h_mm),
        )
        if not pf.ok:
            raise PreflightFailed(reasons=pf.reasons)

        paths = deps.pdf.extract_paths(job.source_pdf)
        # MVP: every path goes onto cut layer 0 (we'll honor stroke-color → layer
        # mapping in Phase 5 when we wire the palette lookup into here).
        shapes: list[tuple[str, int]] = [(d, 0) for d, _color in paths]

        out_bytes = build_lbrn2(
            template_path=Path(profile.template.lbrn2_path),
            shapes=shapes,
        )
        deps.temp_dir.mkdir(parents=True, exist_ok=True)
        out_path = deps.temp_dir / f"{sku.value}-{datetime.now():%Y%m%d-%H%M%S}.lbrn2"
        out_path.write_bytes(out_bytes)

        deps.lightburn.load_file(out_path)
        return JobResult(ok=True, output_path=out_path, sku=sku, profile=profile)
    except LbbError as e:
        return JobResult(ok=False, error=str(e))
