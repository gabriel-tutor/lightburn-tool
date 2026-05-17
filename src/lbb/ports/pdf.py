from pathlib import Path
from typing import Protocol

from lbb.core.preflight import PdfInfo


class PdfReader(Protocol):
    def read_info(self, path: Path) -> PdfInfo: ...

    def render_thumbnail_png(self, path: Path, max_px: int) -> bytes: ...

    def extract_paths(self, path: Path) -> list[tuple[str, str]]:
        """Return list of (svg_path_d, stroke_color_hex)."""
        ...
