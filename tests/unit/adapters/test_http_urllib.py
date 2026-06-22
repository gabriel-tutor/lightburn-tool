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
