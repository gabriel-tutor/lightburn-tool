from lbb.adapters.http_urllib import UrllibTransport


class _FakeOpener:
    def __init__(self):
        self.captured = None

    def open(self, req, timeout=None):  # mimic urllib.request.urlopen
        self.captured = req

        class _Resp:
            status = 200

            def read(self_inner):
                return b'{"ok": true}'

            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

        return _Resp()


def test_request_sets_method_headers_body():
    fake = _FakeOpener()
    t = UrllibTransport(opener=fake.open)
    code, body = t.request(
        "POST", "https://x/api",
        headers={"x-api-key": "secret", "Content-Type": "application/json"},
        body=b'{"a":1}',
    )
    assert code == 200
    assert body == b'{"ok": true}'
    req = fake.captured
    assert req.get_method() == "POST"
    assert req.data == b'{"a":1}'
    assert req.get_header("X-api-key") == "secret"


import urllib.error

from lbb.ports.engraving import EngravingApiError


class _FlakyOpener:
    """Fails the first `fail_n` calls with the given exception, then succeeds."""
    def __init__(self, fail_n, exc):
        self.fail_n = fail_n
        self.exc = exc
        self.calls = 0

    def open(self, req, timeout=None):
        self.calls += 1
        if self.calls <= self.fail_n:
            raise self.exc
        class _Resp:
            status = 200
            def read(self_inner): return b'{"ok": true}'
            def __enter__(self_inner): return self_inner
            def __exit__(self_inner, *a): return False
        return _Resp()


def _transport(opener):
    # zero-delay sleep so tests are instant
    return UrllibTransport(opener=opener.open, sleep=lambda _s: None, max_attempts=3)


def test_retries_transient_url_error_then_succeeds():
    f = _FlakyOpener(2, urllib.error.URLError("temporary"))
    t = _transport(f)
    code, body = t.request("GET", "https://x/api", headers={})
    assert code == 200
    assert f.calls == 3  # 2 failures + 1 success


def test_gives_up_after_max_attempts():
    f = _FlakyOpener(5, urllib.error.URLError("down"))
    t = _transport(f)
    try:
        t.request("GET", "https://x/api", headers={})
        assert False, "should have raised"
    except EngravingApiError:
        pass
    assert f.calls == 3  # capped at max_attempts


class _StatusOpener:
    """Returns a fixed HTTP status for the first `fail_n` calls, then 200."""
    def __init__(self, fail_n, status):
        self.fail_n = fail_n
        self.status = status
        self.calls = 0

    def open(self, req, timeout=None):
        self.calls += 1
        if self.calls <= self.fail_n:
            raise urllib.error.HTTPError(req.full_url, self.status, "err", {}, None)
        class _Resp:
            status = 200
            def read(self_inner): return b'{"ok": true}'
            def __enter__(self_inner): return self_inner
            def __exit__(self_inner, *a): return False
        return _Resp()


def test_retries_503_then_succeeds():
    s = _StatusOpener(1, 503)
    t = _transport(s)
    code, _ = t.request("GET", "https://x/api", headers={})
    assert code == 200
    assert s.calls == 2


def test_does_not_retry_404():
    s = _StatusOpener(1, 404)
    t = _transport(s)
    code, _ = t.request("GET", "https://x/api", headers={})
    assert code == 404      # returned, not retried
    assert s.calls == 1
