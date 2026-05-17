"""Shell-based LightBurn integration — uses the OS's standard 'open in app'
mechanism instead of LightBurn's undocumented UDP protocol.

The UDP protocol is fragile across LightBurn versions and platforms (notably
unresponsive on LightBurn Pro 2.0.05 / macOS as of 2026-05). This adapter
avoids the protocol entirely and lets the OS hand the file to LightBurn:

  macOS:    open -a "LightBurn" file.lbrn2
  Windows:  cmd /c start "" file.lbrn2
  Linux:    xdg-open file.lbrn2

LightBurn launches automatically if not already running.
"""

import subprocess
import sys
from pathlib import Path

from lbb.core.errors import LightBurnNotRunning, LightBurnRejected
from lbb.ports.lightburn import LBStatus, LightBurnPort

_PGREP_TIMEOUT = 1.0
_OPEN_TIMEOUT = 10.0


class LightBurnShellAdapter(LightBurnPort):
    """Open .lbrn2 files in LightBurn via the OS shell. is_running uses pgrep."""

    def __init__(self, app_name: str = "LightBurn"):
        self.app_name = app_name

    def _open_command(self, path: Path, *, platform: str | None = None) -> list[str]:
        """Per-platform command to open a file in LightBurn. Pure — testable."""
        plat = platform or sys.platform
        if plat == "darwin":
            return ["open", "-a", self.app_name, str(path)]
        if plat.startswith("win"):
            return ["cmd", "/c", "start", "", str(path)]
        return ["xdg-open", str(path)]

    def is_running(self) -> bool:
        """Check via pgrep on POSIX. Returns False if pgrep is unavailable."""
        try:
            result = subprocess.run(
                ["pgrep", "-x", self.app_name],
                capture_output=True,
                text=True,
                timeout=_PGREP_TIMEOUT,
                check=False,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def load_file(self, path: Path) -> None:
        if not self.is_running():
            raise LightBurnNotRunning()
        cmd = self._open_command(path)
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=_OPEN_TIMEOUT, check=False
            )
        except FileNotFoundError as e:
            raise LightBurnNotRunning(f"Cannot run '{cmd[0]}' — is it on PATH?") from e
        if result.returncode != 0:
            raise LightBurnRejected(result.stderr or f"exit {result.returncode}")

    def status(self) -> LBStatus:
        return LBStatus(running=self.is_running(), raw="shell")
