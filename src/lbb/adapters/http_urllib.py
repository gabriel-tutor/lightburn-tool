"""HttpTransport over stdlib urllib — no third-party HTTP dependency, so the
PyInstaller bundle stays small and import-clean. Injectable opener + sleep keep
it unit-testable without network or real delays. Transient failures (network
errors, 429, 5xx) are retried with exponential backoff."""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from collections.abc import Callable

from lbb.ports.engraving import EngravingApiError, HttpTransport

_TIMEOUT = 20.0
_MAX_ATTEMPTS = 3
_BASE_BACKOFF = 0.5  # seconds; doubled each retry
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class UrllibTransport(HttpTransport):
    def __init__(
        self,
        *,
        opener: Callable | None = None,
        timeout: float = _TIMEOUT,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = _MAX_ATTEMPTS,
    ):
        self._open = opener or urllib.request.urlopen
        self._timeout = timeout
        self._sleep = sleep
        self._max_attempts = max(1, max_attempts)

    def request(self, method, url, *, headers, body=None):
        last_exc: Exception | None = None
        for attempt in range(self._max_attempts):
            try:
                req = urllib.request.Request(url, data=body, method=method)
                for k, v in headers.items():
                    req.add_header(k, v)
                with self._open(req, timeout=self._timeout) as resp:
                    return getattr(resp, "status", 200), resp.read()
            except urllib.error.HTTPError as e:
                if e.code in _RETRYABLE_STATUS and attempt < self._max_attempts - 1:
                    self._sleep(_BASE_BACKOFF * (2 ** attempt))
                    continue
                return e.code, e.read()
            except (urllib.error.URLError, OSError, TimeoutError) as e:
                last_exc = e
                if attempt < self._max_attempts - 1:
                    self._sleep(_BASE_BACKOFF * (2 ** attempt))
                    continue
                raise EngravingApiError(f"Network error: {e}") from e
        # Unreachable, but keeps type checkers happy.
        raise EngravingApiError(f"Network error: {last_exc}")
