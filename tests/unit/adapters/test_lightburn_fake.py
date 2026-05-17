from pathlib import Path

import pytest

from lbb.adapters.lightburn_fake import LightBurnFake
from lbb.core.errors import LightBurnNotRunning


def test_default_is_running():
    fake = LightBurnFake()
    assert fake.is_running()


def test_can_simulate_not_running():
    fake = LightBurnFake(running=False)
    with pytest.raises(LightBurnNotRunning):
        fake.load_file(Path("/tmp/x.lbrn2"))


def test_records_loaded_files():
    fake = LightBurnFake()
    fake.load_file(Path("/tmp/a.lbrn2"))
    fake.load_file(Path("/tmp/b.lbrn2"))
    assert fake.loaded == [Path("/tmp/a.lbrn2"), Path("/tmp/b.lbrn2")]
