"""Composition root — the only place we wire real adapters to the pipeline.

Tests construct PipelineDeps directly with fakes. Production code (UI, CLI)
goes through build_pipeline_deps() so the wiring lives in exactly one file.
"""

import sys
from dataclasses import dataclass
from pathlib import Path

from lbb.adapters.lightburn_shell import LightBurnShellAdapter
from lbb.adapters.lightburn_udp import LightBurnUDPAdapter
from lbb.adapters.pdfium_reader import PdfiumReader
from lbb.adapters.sqlite_repo import SqliteProfileRepository
from lbb.app.pipeline import PipelineDeps
from lbb.ports.lightburn import LightBurnPort


@dataclass(frozen=True, slots=True)
class AppPaths:
    db_path: Path
    temp_dir: Path


def _select_lightburn() -> LightBurnPort:
    """Pick the LightBurn integration that's most reliable on this platform.

    macOS / Linux: shell-based ('open -a' / 'xdg-open') — robust and version-
    agnostic. UDP is undocumented and not consistently working on LightBurn
    Pro 2.0.05 / macOS as of 2026-05.

    Windows: keep UDP — SendUDP.exe is the documented Windows path. (Can
    switch to shell here too if UDP turns out flaky on Windows in practice.)
    """
    if sys.platform.startswith("win"):
        return LightBurnUDPAdapter()
    return LightBurnShellAdapter()


def build_pipeline_deps(paths: AppPaths) -> PipelineDeps:
    """Return a PipelineDeps wired with production adapters."""
    return PipelineDeps(
        repo=SqliteProfileRepository(paths.db_path),
        pdf=PdfiumReader(),
        lightburn=_select_lightburn(),
        temp_dir=paths.temp_dir,
    )
