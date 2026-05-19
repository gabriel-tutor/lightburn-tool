from dataclasses import dataclass
from pathlib import Path

from lbb.core.models import Sku, SkuProfile


@dataclass(frozen=True, slots=True)
class Job:
    """A single PDF-load request from the operator.

    `profile` is set when the operator picked the SKU manually (filename had
    no `<SKU>__` prefix). When None, the pipeline falls back to extracting
    the SKU from the filename — the historical happy path.
    """

    source_pdf: Path
    profile: SkuProfile | None = None


@dataclass(frozen=True, slots=True)
class JobResult:
    """Outcome of running a Job through the pipeline."""

    ok: bool
    output_path: Path | None = None
    sku: Sku | None = None
    profile: SkuProfile | None = None
    error: str | None = None
