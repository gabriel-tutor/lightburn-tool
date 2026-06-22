"""HttpTransport over stdlib urllib — no third-party HTTP dependency, so the
PyInstaller bundle stays small and import-clean. Injectable opener keeps it
unit-testable without network."""

from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Callable

from lbb.ports.engraving import EngravingApiError, HttpTransport

_TIMEOUT = 20.0


class UrllibTransport(HttpTransport):
    def __init__(self, *, opener: Callable | None = None, timeout: float = _TIMEOUT):
        self._open = opener or urllib.request.urlopen
        self._timeout = timeout

    def request(self, method, url, *, headers, body=None):
        req = urllib.request.Request(url, data=body, method=method)
        for k, v in headers.items():
            req.add_header(k, v)
        try:
            with self._open(req, timeout=self._timeout) as resp:
                return getattr(resp, "status", 200), resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            raise EngravingApiError(f"Network error: {e}") from e
