import socket
import threading
from pathlib import Path

import pytest

from lbb.adapters.lightburn_udp import LightBurnUDPAdapter
from lbb.core.errors import LightBurnNotRunning, LightBurnRejected


class _FakeLightBurn:
    """Mini UDP listener that mimics LightBurn's protocol surface."""

    def __init__(self, responses: dict[bytes, bytes]):
        self.responses = responses
        self.received: list[bytes] = []
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind(("127.0.0.1", 0))
        self.port = self._sock.getsockname()[1]
        self._stop = False
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    def _run(self):
        self._sock.settimeout(0.1)
        while not self._stop:
            try:
                data, addr = self._sock.recvfrom(2048)
            except TimeoutError:
                continue
            except OSError:
                break
            self.received.append(data)
            resp = self.responses.get(data, b"")
            if resp:
                self._sock.sendto(resp, addr)

    def stop(self):
        self._stop = True
        self._t.join(timeout=1)
        self._sock.close()


@pytest.fixture
def fake_lb():
    lb = _FakeLightBurn({b"PING": b"OK"})
    yield lb
    lb.stop()


def test_is_running_true_when_responds(fake_lb):
    adapter = LightBurnUDPAdapter(host="127.0.0.1", port=fake_lb.port)
    assert adapter.is_running()


def test_is_running_false_when_no_response():
    # Port 1 has no UDP listener on any sane host — round-trip times out.
    adapter = LightBurnUDPAdapter(host="127.0.0.1", port=1, timeout=0.1)
    assert not adapter.is_running()


def test_load_file_sends_correct_command(tmp_path):
    target = tmp_path / "x.lbrn2"
    fake = _FakeLightBurn({b"PING": b"OK", f"LOADFILE://{target}".encode(): b"OK"})
    try:
        adapter = LightBurnUDPAdapter(host="127.0.0.1", port=fake.port)
        adapter.load_file(target)
        assert any(d.startswith(b"LOADFILE://") for d in fake.received)
    finally:
        fake.stop()


def test_load_file_raises_when_not_running():
    adapter = LightBurnUDPAdapter(host="127.0.0.1", port=1, timeout=0.1)
    with pytest.raises(LightBurnNotRunning):
        adapter.load_file(Path("/tmp/x.lbrn2"))


def test_load_file_raises_on_non_ok_response(tmp_path):
    target = tmp_path / "x.lbrn2"
    fake = _FakeLightBurn({b"PING": b"OK", f"LOADFILE://{target}".encode(): b"NACK"})
    try:
        adapter = LightBurnUDPAdapter(host="127.0.0.1", port=fake.port)
        with pytest.raises(LightBurnRejected):
            adapter.load_file(target)
    finally:
        fake.stop()
