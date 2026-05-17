"""Composition root — the only place we wire real adapters to the pipeline.

Tests construct PipelineDeps directly with fakes. Production code (UI, CLI)
goes through build_pipeline_deps() so the wiring lives in exactly one file.
"""

from dataclasses import dataclass
from pathlib import Path

from lbb.adapters.lightburn_udp import LightBurnUDPAdapter
from lbb.adapters.pdfium_reader import PdfiumReader
from lbb.adapters.sqlite_repo import SqliteProfileRepository
from lbb.app.pipeline import PipelineDeps


@dataclass(frozen=True, slots=True)
class AppPaths:
    db_path: Path
    temp_dir: Path


def build_pipeline_deps(paths: AppPaths) -> PipelineDeps:
    """Return a PipelineDeps wired with production adapters."""
    return PipelineDeps(
        repo=SqliteProfileRepository(paths.db_path),
        pdf=PdfiumReader(),
        lightburn=LightBurnUDPAdapter(),
        temp_dir=paths.temp_dir,
    )
