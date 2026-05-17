import socket
from pathlib import Path

from lbb.core.errors import LightBurnNotRunning, LightBurnRejected
from lbb.ports.lightburn import LBStatus, LightBurnPort

DEFAULT_PORT = 19840

# Localhost UDP responds in microseconds; the long timeout was masking a real
# UI-freeze bug. PING is the polling path (called every 2s on the GUI thread),
# so it needs to be fast-failing. LOAD is user-initiated, brief wait is fine.
DEFAULT_PING_TIMEOUT = 0.1  # 100 ms — generous for loopback
DEFAULT_LOAD_TIMEOUT = 1.0  # 1 s — user has clicked Send and is waiting


class LightBurnUDPAdapter(LightBurnPort):
    """Sends LightBurn's local UDP control commands (PING, LOADFILE://, STATUS).

    Schema is community-documented (forum.lightburnsoftware.com); pin LightBurn
    versions and add coverage if you upgrade.

    NOTE: Calls block the calling thread for up to `ping_timeout` /
    `load_timeout`. The current GUI integration calls is_running() from a
    QTimer on the main thread; keep ping_timeout small. A future refactor
    should move to QUdpSocket for fully-async polling.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = DEFAULT_PORT,
        *,
        ping_timeout: float = DEFAULT_PING_TIMEOUT,
        load_timeout: float = DEFAULT_LOAD_TIMEOUT,
    ):
        self.host = host
        self.port = port
        self.ping_timeout = ping_timeout
        self.load_timeout = load_timeout

    def _roundtrip(self, payload: bytes, *, timeout: float) -> bytes | None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        try:
            sock.sendto(payload, (self.host, self.port))
            try:
                data, _ = sock.recvfrom(4096)
                return data
            except TimeoutError:
                return None
        finally:
            sock.close()

    def is_running(self) -> bool:
        return self._roundtrip(b"PING", timeout=self.ping_timeout) == b"OK"

    def load_file(self, path: Path) -> None:
        if not self.is_running():
            raise LightBurnNotRunning()
        resp = self._roundtrip(f"LOADFILE://{path}".encode(), timeout=self.load_timeout)
        if resp != b"OK":
            raise LightBurnRejected(resp or b"")

    def status(self) -> LBStatus:
        raw = self._roundtrip(b"STATUS", timeout=self.ping_timeout)
        return LBStatus(running=raw is not None, raw=(raw or b"").decode(errors="replace"))
