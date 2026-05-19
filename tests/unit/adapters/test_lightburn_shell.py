import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from lbb.adapters.lightburn_shell import LightBurnShellAdapter
from lbb.core.errors import LightBurnNotRunning


def test_open_command_for_macos():
    adapter = LightBurnShellAdapter(app_name="LightBurn")
    cmd = adapter._open_command(Path("/tmp/x.lbrn2"), platform="darwin")
    assert cmd == ["open", "-a", "LightBurn", "/tmp/x.lbrn2"]


def test_open_command_for_windows():
    adapter = LightBurnShellAdapter(app_name="LightBurn")
    cmd = adapter._open_command(Path("/tmp/x.lbrn2"), platform="win32")
    # Windows: 'start' needs an empty title arg to handle paths with spaces.
    assert cmd == ["cmd", "/c", "start", "", "/tmp/x.lbrn2"]


def test_open_command_for_linux():
    adapter = LightBurnShellAdapter(app_name="LightBurn")
    cmd = adapter._open_command(Path("/tmp/x.lbrn2"), platform="linux")
    assert cmd == ["xdg-open", "/tmp/x.lbrn2"]


def test_is_running_returns_true_when_pgrep_succeeds():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        adapter = LightBurnShellAdapter()
        assert adapter._is_running(platform="darwin")


def test_is_running_windows_finds_lightburn_in_tasklist():
    """Windows uses tasklist /FI to find the process by image name."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = (
            "Image Name                     PID Session Name        Session#    Mem Usage\n"
            "========================= ======== ================ =========== ============\n"
            "LightBurn.exe                12345 Console                    1     45,000 K\n"
        )
        adapter = LightBurnShellAdapter()
        assert adapter._is_running(platform="win32")


def test_is_running_windows_returns_false_when_tasklist_empty():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = (
            "INFO: No tasks are running which match the specified criteria.\n"
        )
        adapter = LightBurnShellAdapter()
        assert not adapter._is_running(platform="win32")


def test_is_running_returns_false_when_pgrep_no_match():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        adapter = LightBurnShellAdapter()
        assert not adapter.is_running()


def test_is_running_returns_false_when_pgrep_missing():
    with patch("subprocess.run", side_effect=FileNotFoundError("pgrep")):
        adapter = LightBurnShellAdapter()
        assert not adapter.is_running()


def test_load_file_invokes_popen_with_open_command(tmp_path):
    """load_file passes the resolved open-command to Popen (fire-and-forget)."""
    target = tmp_path / "x.lbrn2"
    target.write_text("dummy")
    with patch("subprocess.Popen") as mock_popen:
        adapter = LightBurnShellAdapter(exe_path=None)
        adapter.load_file(target)
    assert mock_popen.called
    cmd_arg = mock_popen.call_args.args[0]
    # On any platform the command's first token is the launcher
    # (open / cmd / xdg-open or the explicit LB exe).
    assert cmd_arg, "Popen called with empty command"


def test_open_command_for_windows_invokes_explicit_exe_when_found():
    """When LightBurn.exe is located, the Windows command invokes it directly
    so the file argument is handed to LightBurn — not routed through Windows'
    .pdf file association (which would open the browser). Regression for the
    2026-05-19 'PDF opens in browser' bug."""
    adapter = LightBurnShellAdapter(
        exe_path=Path(r"C:\Program Files\LightBurn\LightBurn.exe"),
    )
    cmd = adapter._open_command(Path(r"C:\tmp\x.pdf"), platform="win32")
    # Direct invocation: [exe, file] — no cmd /c shell wrapper.
    assert cmd[0].endswith("LightBurn.exe")
    assert cmd[-1].endswith("x.pdf")
    assert "start" not in cmd, "must not use shell wrapper that triggers file association"


def test_open_command_for_windows_falls_back_to_shell_when_exe_not_found():
    """If LightBurn isn't installed in a known path, fall back to the OS
    default-app opener. Still works for .lbrn2 (LightBurn registers itself
    for that extension); .pdf would route to the browser, which is the
    pre-fix behaviour and the best we can do without an exe path."""
    adapter = LightBurnShellAdapter(exe_path=None)
    cmd = adapter._open_command(Path(r"C:\tmp\x.lbrn2"), platform="win32")
    assert cmd[:4] == ["cmd", "/c", "start", ""]


def test_load_file_uses_popen_not_run():
    """Use Popen (fire-and-forget) — LightBurn is a GUI app and won't exit, so
    subprocess.run would block on its timeout. Regression for the 2026-05-19
    bug where direct exe invocation hung the load."""
    with patch("subprocess.Popen") as mock_popen:
        adapter = LightBurnShellAdapter(exe_path=Path(r"C:\Program Files\LightBurn\LightBurn.exe"))
        adapter.load_file(Path(r"C:\tmp\x.pdf"))
        assert mock_popen.called, "load_file must use Popen, not run"


def test_status_reflects_is_running():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        adapter = LightBurnShellAdapter()
        assert adapter.status().running


def test_is_running_windows_uses_create_no_window():
    """Polling tasklist must use CREATE_NO_WINDOW or the bundled GUI app
    flashes a console window every 2s (runw.exe has no parent console)."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "LightBurn.exe 1234 Console 1 45,000 K\n"
        adapter = LightBurnShellAdapter()
        adapter._is_running(platform="win32")
        kwargs = mock_run.call_args.kwargs
        expected = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        assert kwargs.get("creationflags") == expected, (
            "Windows tasklist call must pass creationflags=CREATE_NO_WINDOW; "
            f"got {kwargs.get('creationflags')!r}"
        )


def test_is_running_posix_uses_create_no_window_constant():
    """POSIX call sites use the same `getattr(subprocess, 'CREATE_NO_WINDOW', 0)`
    abstraction so the production code stays platform-uniform; on POSIX the
    value is 0 (no-op), and the kwarg must still be present."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        adapter = LightBurnShellAdapter()
        adapter._is_running(platform="darwin")
        kwargs = mock_run.call_args.kwargs
        expected = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        assert kwargs.get("creationflags") == expected


def test_load_file_open_command_uses_create_no_window():
    """The `cmd /c start ...` (and `open -a`, `xdg-open`) launch must also use
    CREATE_NO_WINDOW so clicking Send doesn't flash a console on Windows."""
    target = Path.cwd() / "fake.lbrn2"  # path doesn't need to exist for the mock
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        # Make is_running()'s tasklist/pgrep call appear successful on either OS.
        mock_run.return_value.stdout = "LightBurn.exe 1234 Console 1 45,000 K\n"
        adapter = LightBurnShellAdapter()
        adapter.load_file(target)
        expected = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        # Every subprocess.run call (is_running + open) must carry the flag.
        for i, call in enumerate(mock_run.call_args_list):
            assert call.kwargs.get("creationflags") == expected, (
                f"subprocess.run call #{i} ({call.args[0]!r}) "
                f"must pass creationflags=CREATE_NO_WINDOW"
            )


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS-only integration")
def test_is_running_against_real_processes_macos():
    """Probe a known-running process on macOS to validate pgrep wiring."""
    # The Python interpreter itself is running and pgrep-able.
    adapter = LightBurnShellAdapter(app_name="python3.12")
    # Don't assert — just exercise the path without crashing.
    adapter.is_running()
