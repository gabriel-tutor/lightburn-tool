"""Composition root — the only place we wire real adapters to the pipeline.

Tests construct PipelineDeps directly with fakes. Production code (UI, CLI)
goes through build_pipeline_deps() so the wiring lives in exactly one file.
"""

from dataclasses import dataclass
from pathlib import Path

from lbb.adapters.config import ApiConfig
from lbb.adapters.engraving_api import EngravingApiClient
from lbb.adapters.http_urllib import UrllibTransport
from lbb.adapters.lightburn_shell import LightBurnShellAdapter
from lbb.adapters.pdfium_reader import PdfiumReader
from lbb.adapters.sqlite_repo import SqliteProfileRepository
from lbb.adapters.sqlite_state import SqliteStateStore
from lbb.app.fulfillment_service import FulfillmentService
from lbb.app.pipeline import PipelineDeps
from lbb.ports.lightburn import LightBurnPort


@dataclass(frozen=True, slots=True)
class AppPaths:
    db_path: Path
    temp_dir: Path
    orders_dir: Path | None = None  # user-home directory holding orders.json + PDFs


def _select_lightburn() -> LightBurnPort:
    """Shell-based integration on every platform:
      macOS:    open -a 'LightBurn' file.lbrn2     + pgrep -x LightBurn
      Linux:    xdg-open file.lbrn2                 + pgrep -x LightBurn
      Windows:  cmd /c start '' file.lbrn2          + tasklist /FI ...

    UDP adapter is intentionally retired from the production wiring — it
    was undocumented and didn't work on LightBurn Pro 2.0.05/macOS. It's
    still in the repo and tested, available for advanced users who wire
    their own deps. See git history before 2026-05 for the previous setup.
    """
    return LightBurnShellAdapter()


def build_pipeline_deps(paths: AppPaths) -> PipelineDeps:
    """Return a PipelineDeps wired with production adapters."""
    return PipelineDeps(
        repo=SqliteProfileRepository(paths.db_path),
        pdf=PdfiumReader(),
        lightburn=_select_lightburn(),
        temp_dir=paths.temp_dir,
    )


def build_fulfillment_service(
    config: ApiConfig, state_db: Path, cache_dir: Path
) -> FulfillmentService:
    gateway = EngravingApiClient(config.base_url, config.api_key, UrllibTransport())
    return FulfillmentService(
        gateway=gateway,
        state=SqliteStateStore(state_db),
        lightburn=LightBurnShellAdapter(),
        cache_dir=cache_dir,
    )
