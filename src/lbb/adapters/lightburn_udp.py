import socket
from pathlib import Path

from lbb.core.errors import LightBurnNotRunning, LightBurnRejected
from lbb.ports.lightburn import LBStatus, LightBurnPort

DEFAULT_PORT = 19840


class LightBurnUDPAdapter(LightBurnPort):
    """Sends LightBurn's local UDP control commands (PING, LOADFILE://, STATUS).

    Schema is community-documented (forum.lightburnsoftware.com); pin LightBurn
    versions and add coverage if you upgrade.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = DEFAULT_PORT, timeout: float = 2.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    def _roundtrip(self, payload: bytes) -> bytes | None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self.timeout)
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
        return self._roundtrip(b"PING") == b"OK"

    def load_file(self, path: Path) -> None:
        if not self.is_running():
            raise LightBurnNotRunning()
        resp = self._roundtrip(f"LOADFILE://{path}".encode())
        if resp != b"OK":
            raise LightBurnRejected(resp or b"")

    def status(self) -> LBStatus:
        raw = self._roundtrip(b"STATUS")
        return LBStatus(running=raw is not None, raw=(raw or b"").decode(errors="replace"))
