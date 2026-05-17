from dataclasses import dataclass
from pathlib import Path

from lbb.core.models import Sku, SkuProfile


@dataclass(frozen=True, slots=True)
class Job:
    """A single PDF-load request from the operator."""

    source_pdf: Path


@dataclass(frozen=True, slots=True)
class JobResult:
    """Outcome of running a Job through the pipeline."""

    ok: bool
    output_path: Path | None = None
    sku: Sku | None = None
    profile: SkuProfile | None = None
    error: str | None = None
