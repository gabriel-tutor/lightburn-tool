"""Shell-based LightBurn integration — invokes LightBurn explicitly so any
file type (PDF, .lbrn2, SVG, …) opens IN LightBurn regardless of the OS-level
default-app association.

  macOS:    open -a "LightBurn" file
  Windows:  cmd /c start "" "<LightBurn.exe>" file
  Linux:    xdg-open file   (TODO: same fix as Windows; not yet implemented)

The Windows command points `start` at the explicit LightBurn.exe path so the
file argument is handed to LightBurn directly. The naive `cmd /c start "" file`
would route .pdf to the OS default handler (typically a browser).

LightBurn launches automatically if not already running.
"""

import os
import subprocess
import sys
from pathlib import Path

from lbb.core.errors import LightBurnRejected
from lbb.ports.lightburn import LBStatus, LightBurnPort

_PGREP_TIMEOUT = 1.0
_OPEN_TIMEOUT = 10.0

# When the parent is a windowed PyInstaller bundle (runw.exe) it has no console,
# so each console-app child (tasklist, cmd /c start) gets a fresh window allocated
# unless we pass CREATE_NO_WINDOW. The constant only exists on Windows; getattr
# returns 0 on POSIX, where the flag is a no-op.
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# Sentinel so the constructor can distinguish "caller passed no value" (auto-find)
# from "caller passed None" (explicitly no exe, take the fallback shell path).
_AUTO_DETECT = object()


def _find_lightburn_exe(*, platform: str | None = None) -> Path | None:
    """Locate LightBurn.exe on Windows. Returns None on macOS/Linux (which use
    `open -a` / `xdg-open` patterns that don't need an explicit path) or when
    LightBurn isn't found in any common install location."""
    plat = platform or sys.platform
    if not plat.startswith("win"):
        return None
    candidates = [
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "LightBurn" / "LightBurn.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
        / "LightBurn" / "LightBurn.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "LightBurn" / "LightBurn.exe",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


class LightBurnShellAdapter(LightBurnPort):
    """Open files in LightBurn via the OS shell, invoking the LightBurn exe
    explicitly so any file type opens IN LightBurn regardless of the OS-level
    default-app association."""

    def __init__(
        self,
        app_name: str = "LightBurn",
        *,
        exe_path: Path | None | object = _AUTO_DETECT,
    ):
        self.app_name = app_name
        # Resolve at construction time so a missing install surfaces early.
        # Tests can pass exe_path=None to force the shell fallback, or pass an
        # explicit Path to skip filesystem auto-detection.
        if exe_path is _AUTO_DETECT:
            self.exe_path: Path | None = _find_lightburn_exe()
        else:
            self.exe_path = exe_path  # type: ignore[assignment]

    def _open_command(self, path: Path, *, platform: str | None = None) -> list[str]:
        """Per-platform command to open a file in LightBurn. Pure — testable.

        When `self.exe_path` is set on Windows we invoke LightBurn directly
        (no `cmd /c start` shell wrapper) so the file is handed to LightBurn
        regardless of OS-level default-app association. The caller uses
        Popen so we don't wait for the GUI to exit.
        """
        plat = platform or sys.platform
        if plat == "darwin":
            return ["open", "-a", self.app_name, str(path)]
        if plat.startswith("win"):
            if self.exe_path:
                return [str(self.exe_path), str(path)]
            # Fallback: OS default app. Fine for .lbrn2 (LightBurn is registered
            # for that extension) but routes .pdf to the browser.
            return ["cmd", "/c", "start", "", str(path)]
        return ["xdg-open", str(path)]

    def is_running(self) -> bool:
        return self._is_running(platform=sys.platform)

    def _is_running(self, *, platform: str) -> bool:
        """Platform-dispatched process check. POSIX uses pgrep, Windows tasklist."""
        try:
            if platform.startswith("win"):
                result = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {self.app_name}.exe"],
                    capture_output=True,
                    text=True,
                    timeout=_PGREP_TIMEOUT,
                    check=False,
                    creationflags=_CREATE_NO_WINDOW,
                )
                # tasklist always returns 0; the process is present iff its
                # name appears in stdout (otherwise we see "No tasks are running…").
                return f"{self.app_name}.exe" in result.stdout
            result = subprocess.run(
                ["pgrep", "-x", self.app_name],
                capture_output=True,
                text=True,
                timeout=_PGREP_TIMEOUT,
                check=False,
                creationflags=_CREATE_NO_WINDOW,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def load_file(self, path: Path) -> None:
        """Hand the file to LightBurn via Popen (fire-and-forget).

        We don't wait for the GUI to exit, and we don't gate on is_running —
        invoking LightBurn.exe launches it if not already running. Surface
        any real failure (missing exe, OS rejection) as LightBurnRejected.
        """
        cmd = self._open_command(path)
        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=_CREATE_NO_WINDOW,
            )
        except (FileNotFoundError, OSError) as e:
            raise LightBurnRejected(
                f"Cannot launch '{cmd[0]}' — is LightBurn installed?"
            ) from e

    def status(self) -> LBStatus:
        return LBStatus(running=self.is_running(), raw="shell")
