from pathlib import Path

from lbb.core.errors import LightBurnNotRunning
from lbb.ports.lightburn import LBStatus, LightBurnPort


class LightBurnFake(LightBurnPort):
    """In-memory test double for LightBurnPort. Records every load_file call."""

    def __init__(self, running: bool = True):
        self._running = running
        self.loaded: list[Path] = []

    def is_running(self) -> bool:
        return self._running

    def load_file(self, path: Path) -> None:
        if not self._running:
            raise LightBurnNotRunning()
        self.loaded.append(path)

    def status(self) -> LBStatus:
        return LBStatus(running=self._running, raw="FAKE")
