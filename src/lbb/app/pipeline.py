"""The job pipeline: hand the customer's PDF directly to LightBurn.

Direct-Open architecture (2026-05-19 pivot): we no longer parse the PDF's
geometry or generate a `.lbrn2` from a template. LightBurn's native PDF
importer preserves the design with full fidelity — our role is SKU lookup
+ operator instructions (handled upstream in the UI) + dispatch.

The previous `extract_paths` → `build_lbrn2` → write-temp-file flow is
preserved in the codebase under `core/template_builder.py` and
`adapters/pdfium_reader.py:extract_paths` but is no longer in the live path.
See docs/superpowers/specs/2026-05-19-direct-open-pivot-design.md.
"""

from dataclasses import dataclass
from pathlib import Path

from lbb.app.job import Job, JobResult
from lbb.core.errors import LbbError
from lbb.ports.lightburn import LightBurnPort
from lbb.ports.pdf import PdfReader
from lbb.ports.repository import ProfileRepository


@dataclass(frozen=True, slots=True)
class PipelineDeps:
    repo: ProfileRepository
    pdf: PdfReader
    lightburn: LightBurnPort
    temp_dir: Path  # vestigial under direct-open; kept for ABI compatibility


def run_pipeline(job: Job, deps: PipelineDeps) -> JobResult:
    """Open the customer's PDF directly in LightBurn.

    The Job's `profile` (resolved upstream by the UI from filename or picker)
    is passed through to the JobResult so the caller can still display the
    SKU / template / material that this job represents — but it does not
    influence what's loaded. LightBurn's importer handles all PDF parsing.
    """
    try:
        deps.lightburn.load_file(job.source_pdf)
    except LbbError as e:
        return JobResult(ok=False, error=str(e))
    return JobResult(
        ok=True,
        output_path=job.source_pdf,
        sku=job.profile.sku if job.profile else None,
        profile=job.profile,
    )
