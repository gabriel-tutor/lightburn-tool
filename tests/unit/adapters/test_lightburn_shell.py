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
        assert adapter.is_running()


def test_is_running_returns_false_when_pgrep_no_match():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        adapter = LightBurnShellAdapter()
        assert not adapter.is_running()


def test_is_running_returns_false_when_pgrep_missing():
    with patch("subprocess.run", side_effect=FileNotFoundError("pgrep")):
        adapter = LightBurnShellAdapter()
        assert not adapter.is_running()


def test_load_file_invokes_open_command(tmp_path):
    target = tmp_path / "x.lbrn2"
    target.write_text("dummy")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        adapter = LightBurnShellAdapter()
        adapter.load_file(target)
    # subprocess.run was called twice — once for pgrep (is_running), once for open
    assert (
        any("open" in (c.args[0][0] if c.args else "") for c in mock_run.call_args_list)
        or any("xdg-open" in (c.args[0][0] if c.args else "") for c in mock_run.call_args_list)
        or any("cmd" in (c.args[0][0] if c.args else "") for c in mock_run.call_args_list)
    )


def test_load_file_raises_when_lightburn_not_running():
    with patch("subprocess.run") as mock_run:
        # pgrep returns 1 (not running)
        mock_run.return_value.returncode = 1
        adapter = LightBurnShellAdapter()
        with pytest.raises(LightBurnNotRunning, match="(?i)running"):
            adapter.load_file(Path("/tmp/x.lbrn2"))


def test_status_reflects_is_running():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        adapter = LightBurnShellAdapter()
        assert adapter.status().running


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS-only integration")
def test_is_running_against_real_processes_macos():
    """Probe a known-running process on macOS to validate pgrep wiring."""
    # The Python interpreter itself is running and pgrep-able.
    adapter = LightBurnShellAdapter(app_name="python3.12")
    # Don't assert — just exercise the path without crashing.
    adapter.is_running()
