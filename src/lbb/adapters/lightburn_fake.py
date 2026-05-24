from pathlib import Path

from lbb.core.errors import LightBurnNotRunning
from lbb.ports.lightburn import LBStatus, LightBurnPort


class LightBurnFake(LightBurnPort):
    """In-memory test double for LightBurnPort. Records every load_file call.

    Two distinct off-states are modelled:
      • `running=False at construction`  → LightBurn is unreachable; every
        load_file raises (simulates "LB not installed / can't launch").
      • `close_running()` mid-session    → process was killed BUT a subsequent
        load_file silently relaunches it (mimics the real shell adapter,
        which always invokes LightBurn.exe directly and launches if needed).
    """

    def __init__(self, running: bool = True):
        self._initial_running = running
        self._running = running
        self.loaded: list[Path] = []
        self.close_calls: int = 0

    def is_running(self) -> bool:
        return self._running

    def load_file(self, path: Path) -> None:
        if not self._initial_running:
            raise LightBurnNotRunning()
        # Mid-session close_running() flipped _running to False; the real
        # shell adapter would just relaunch LightBurn here.
        self._running = True
        self.loaded.append(path)

    def status(self) -> LBStatus:
        return LBStatus(running=self._running, raw="FAKE")

    def close_running(self) -> None:
        """Simulate force-kill: process is gone until the next load_file
        relaunches it. Tests can inspect `close_calls` to verify."""
        self.close_calls += 1
        self._running = False
