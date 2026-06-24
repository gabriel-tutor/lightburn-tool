# Polish, Reliability & UX Hardening — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close every reliability and UX gap the audit found — retries, expired-link recovery, no-freeze async, loading states, honest toasts, debounced search, modal dismissal — with zero regressions, so the tool is fully working and impresses the client.

**Architecture:** No architecture changes, no new dependencies. Backend gets bounded retry + expired-URL recovery + no-throw hardening (all TDD). Frontend gets try/finally robustness, skeleton loaders, button spinners, client-side search, toast variants, and modal/empty-state polish (no JS unit harness → `node --check` + grep guards + live smoke).

**Tech Stack:** Python 3.12 + uv + pytest; vanilla JS/CSS in pywebview assets.

**Reference spec:** `docs/superpowers/specs/2026-06-24-polish-reliability-ux-design.md`

**Conventions:** `uv run` for Python. Single test: `uv run pytest <path>::<name> -v`. Suite: `uv run pytest -q`. Commit after each task. Branch `feature/polish-reliability-ux`. Frontend files: `src/lbb/web/assets/{app.js,index.html,app.css,bridge-client.js}` — READ each fully before editing; match current strings exactly.

---

### Task 1: Retry + backoff in UrllibTransport

**Files:**
- Modify: `src/lbb/adapters/http_urllib.py`
- Test: `tests/unit/adapters/test_http_urllib.py`

- [ ] **Step 1: Write failing tests** — append to `tests/unit/adapters/test_http_urllib.py`:

```python
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
    return UrllibTransport(opener=opener, sleep=lambda _s: None, max_attempts=3)


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
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/adapters/test_http_urllib.py -q`
Expected: FAIL (UrllibTransport has no `sleep`/`max_attempts`, no retry).

- [ ] **Step 3: Rewrite `src/lbb/adapters/http_urllib.py`**

```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/adapters/test_http_urllib.py -q`
Expected: PASS (existing + 4 new). Then `uv run pytest -q` → still 141+ pass.

- [ ] **Step 5: Commit**

```bash
git add src/lbb/adapters/http_urllib.py tests/unit/adapters/test_http_urllib.py
git commit -m "feat(http): bounded retry + backoff for transient failures (429/5xx/network)"
```

---

### Task 2: Expired signed-URL fallback re-GET in `download_file`

**Files:**
- Modify: `src/lbb/adapters/engraving_api.py`
- Test: `tests/unit/adapters/test_engraving_api.py`

- [ ] **Step 1: Write a failing test** — append to `tests/unit/adapters/test_engraving_api.py`:

```python
def test_download_refetches_on_expired_link_then_succeeds(tmp_path):
    """A 403 on the signed URL forces one fresh GET + retry."""
    state = {"download_calls": 0, "get_calls": 0}

    class ExpiringTransport:
        def request(self, method, url, *, headers, body=None):
            if "/dl/" in url:
                state["download_calls"] += 1
                # First download attempt: link expired (403). After a re-GET, ok.
                if state["download_calls"] == 1:
                    return 403, b"expired"
                return 200, b"%PDF-1.4 fresh"
            if method == "GET":
                state["get_calls"] += 1
                return 200, json.dumps({"orders": [ORDER]}).encode()
            return 404, b"{}"

    c = EngravingApiClient(BASE, "secret", ExpiringTransport())
    c.list_orders()                         # get_calls == 1, caches signed urls
    p = c.download_file("uuid-1", "engraving/x Front.pdf", tmp_path)
    assert p.read_bytes().startswith(b"%PDF")
    assert state["download_calls"] == 2     # first 403, retried after re-GET
    assert state["get_calls"] == 2          # one extra GET to mint fresh urls
```

(Uses the existing `ORDER` fixture / `BASE` constant in this test file; the
ORDER's `signed_urls` map the `engraving/x Front.pdf` key to a `/dl/front...` URL.)

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/adapters/test_engraving_api.py::test_download_refetches_on_expired_link_then_succeeds -q`
Expected: FAIL (download raises on the first 403, no retry).

- [ ] **Step 3: Edit `download_file` in `src/lbb/adapters/engraving_api.py`**

Add an expired-link status set near the top constants (after `_HTTP_OK = 200`):

```python
_EXPIRED_LINK_STATUS = frozenset({400, 403, 410})
```

Replace the `download_file` method body with a single-retry-on-expiry version:

```python
    def download_file(self, order_id: str, file_key: str, dest_dir: Path) -> Path:
        data = self._download_once(order_id, file_key)
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / _safe_name(file_key)
        dest.write_bytes(data)
        return dest

    def _download_once(self, order_id: str, file_key: str) -> bytes:
        url = self._fresh_url(order_id, file_key)
        code, data = self._http.request("GET", url, headers={})
        if code in _EXPIRED_LINK_STATUS:
            # Signed URL likely expired (TTL starts at server mint time, which our
            # staleness timer can't see). Force fresh URLs and retry exactly once.
            self._fetch()
            url = self._signed.get(order_id, {}).get(file_key)
            if not url:
                raise EngravingApiError(f"No download URL for {file_key}")
            code, data = self._http.request("GET", url, headers={})
        if code != _HTTP_OK:
            raise EngravingApiError(
                f"Download failed ({code}) for {file_key}", status_code=code
            )
        return data
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/adapters/test_engraving_api.py -q`
Expected: PASS (existing + 1 new). Then `uv run pytest -q`.

- [ ] **Step 5: Commit**

```bash
git add src/lbb/adapters/engraving_api.py tests/unit/adapters/test_engraving_api.py
git commit -m "feat(adapter): re-mint signed URL and retry once on expired-link download"
```

---

### Task 3: Backend no-throw hardening + drop dead `qty`

**Files:**
- Modify: `src/lbb/app/fulfillment_service.py`
- Modify: `src/lbb/core/fulfillment.py`
- Test: `tests/integration/test_fulfillment_service.py`

- [ ] **Step 1: Write failing tests** — append to `tests/integration/test_fulfillment_service.py`:

```python
def test_product_image_corrupt_file_returns_not_ok(tmp_path, monkeypatch):
    gw = FakeGateway([_order_with_image()])

    # download "succeeds" but the file can't be read back
    def boom_download(order_id, file_key, dest_dir):
        p = tmp_path / "x.png"
        return p  # path that does not exist -> read_bytes raises OSError

    gw.download_file = boom_download
    svc = FulfillmentService(gateway=gw, state=MemState(),
                             lightburn=FakeLightBurn(), cache_dir=tmp_path)
    assert svc.product_image("306-IMG", 0)["ok"] is False


def test_engrave_side_lightburn_oserror_not_marked(tmp_path):
    gw = FakeGateway([_order()])

    class BoomLightBurn(FakeLightBurn):
        def load_file(self, path):
            raise OSError("LightBurn launch failed")

    state = MemState()
    svc = FulfillmentService(gateway=gw, state=state,
                             lightburn=BoomLightBurn(), cache_dir=tmp_path)
    res = svc.engrave_side("306-1", "engraving/x Front.pdf")
    assert res["ok"] is False
    assert state.engraved_keys("306-1") == set()   # NOT marked on failure


def test_get_order_has_no_qty(tmp_path):
    gw = FakeGateway([_order()])
    svc = FulfillmentService(gateway=gw, state=MemState(),
                             lightburn=FakeLightBurn(), cache_dir=tmp_path)
    d = svc.get_order("306-1")
    assert "qty" not in d["products"][0]
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/integration/test_fulfillment_service.py -q`
Expected: FAIL (image read throws; OSError propagates; qty present).

- [ ] **Step 3a: Harden `product_image`** — in `src/lbb/app/fulfillment_service.py`, change the tail of `product_image` so the read+encode is guarded:

```python
        if not p.image_key:
            return {"ok": False}
        try:
            path = self.gateway.download_file(o.order_id, p.image_key, self._dir(o))
            data = path.read_bytes()
        except (EngravingApiError, OSError) as e:
            return {"ok": False, "error": str(e)}
        mime = _IMAGE_MIME.get(Path(p.image_key).suffix.lower(), "application/octet-stream")
        b64 = base64.b64encode(data).decode("ascii")
        return {"ok": True, "data_uri": f"data:{mime};base64,{b64}"}
```

- [ ] **Step 3b: Harden `engrave_side`** — broaden the except to include `OSError`:

```python
        try:
            pdf = self.gateway.download_file(o.order_id, file_key, self._dir(o))
            self.lightburn.load_file(pdf)
        except (EngravingApiError, LbbError, OSError) as e:
            return {"ok": False, "error": str(e)}
        self.state.mark_engraved(order_number, file_key, True)
```

- [ ] **Step 3c: Drop `qty`** — in `src/lbb/core/fulfillment.py` remove the `qty: int = 1` field from `Product`. In `src/lbb/app/fulfillment_service.py` remove the `"qty": p.qty,` line from the `get_order` product dict. Then grep for other `qty` / `.qty` references and remove/adjust:

Run: `grep -rn "qty" src/lbb tests` — update any remaining references (e.g. a test constructing `Product(qty=...)` must drop that kwarg; a test asserting `qty` must drop that assertion).

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/integration/test_fulfillment_service.py -q`
Expected: PASS (existing + 3 new). Then full `uv run pytest -q` (fix any qty fallout) and `uv run ruff check src tests`.

- [ ] **Step 5: Commit**

```bash
git add src/lbb/app/fulfillment_service.py src/lbb/core/fulfillment.py tests/integration/test_fulfillment_service.py
git commit -m "fix(service): no-throw product_image/engrave_side; drop dead qty field"
```

---

### Task 4: Frontend robustness — try/finally, busy lock, defensive guards

**Files:**
- Modify: `src/lbb/web/assets/app.js`

READ app.js fully first. No unit harness — verify with `node --check` + greps.

> **Dispatch order:** run **Task 5 (toast variants) BEFORE this task**, so the
> `toast(msg, 'error')` calls introduced here render correctly the moment they
> land. Both tasks are in this branch regardless of file order.

- [ ] **Step 1: Add a `withBusy` helper + `viewToken`** near the top ui-state block (after `let active=0, busy=false;`):

```js
let viewToken = 0;                 // bumped on every navigation; guards stale async
function nextToken(){ return ++viewToken; }
```

- [ ] **Step 2: Wrap every async ACTION in try/finally and reset state.** Rewrite these functions so `busy` and any loading class are always cleared, and stale resolves are ignored:

`engrave(pi, si)`:
```js
async function engrave(pi, si){
  if(busy) return;
  const p = CURRENT.products[pi], side = p.sides[si];
  if(active!==pi){ active=pi; }
  busy=true; renderOrder();
  document.getElementById('livePillText').textContent='Opening LightBurn…';
  const tok = viewToken;
  try {
    const res = await API.engraveSide(CURRENT.order_number, side.file_key);
    if(!res || !res.ok){ toast((res && res.error) || 'Engrave failed','error'); return; }
    const fresh = await API.getOrder(CURRENT.order_number);
    if(tok!==viewToken) return;              // operator navigated away
    if(!fresh){ toast('Could not refresh order','error'); goDashboard(); return; }
    CURRENT = fresh;
    const np = tasksOf(CURRENT).find(t=>!t.s.engraved); if(np) active=np.pi;
    toast(side.name+' engraved'+(allEng(CURRENT)?' · all done':''));
  } catch(e){
    toast('Engrave failed','error');
  } finally {
    busy=false;
    if(tok===viewToken) renderOrder();
  }
}
```

`confirmShip()`, `onStatusSelect(v)`, `flagRevision()`: same pattern — set
`busy=true` at entry, capture `const tok=viewToken;`, do the awaits, bail on
`tok!==viewToken` before assigning `CURRENT`, toast errors with kind `'error'`,
and `finally{ busy=false; if(tok===viewToken) renderOrder(); }`. For
`confirmShip`, keep the dashboard reload + `firstOpenOrder` hop, but guard the
final `openOrder` with the token.

- [ ] **Step 3: `openOrder` stale guard + products guard.**
```js
async function openOrder(orderNumber){
  const tok = nextToken();
  const o = await API.getOrder(orderNumber);
  if(tok!==viewToken) return;                // a newer navigation won
  if(!o){ toast('Order not found','error'); return; }
  CURRENT = o;
  active = firstPendingProduct(CURRENT);
  showView('order'); renderOrder();
}
```
And make `tasksOf` tolerate missing products: `function tasksOf(o){const t=[];(o.products||[]).forEach(...)...}`. `goDashboard` and `showView('dashboard')` should `nextToken()` so in-flight order loads are abandoned.

- [ ] **Step 4: `pollLightBurn` null-safe.**
```js
async function pollLightBurn(){
  let res=null;
  try { res = await API.lightburnStatus(); } catch(e){ return; }
  const running = !!(res && res.running);
  const pill = document.getElementById('livePill');
  if(pill){ pill.classList.toggle('lb-off', !running); }
}
```

- [ ] **Step 5: `copyOrder` clipboard fallback.**
```js
async function copyOrder(){
  const text = CURRENT && CURRENT.order_number; if(!text) return;
  let ok=false;
  try { if(navigator.clipboard && navigator.clipboard.writeText){ await navigator.clipboard.writeText(text); ok=true; } } catch(e){}
  if(!ok){
    try {
      const ta=document.createElement('textarea'); ta.value=text;
      ta.style.position='fixed'; ta.style.opacity='0'; document.body.appendChild(ta);
      ta.focus(); ta.select(); ok=document.execCommand('copy'); document.body.removeChild(ta);
    } catch(e){ ok=false; }
  }
  toast(ok?'Order number copied':'Could not copy', ok?'success':'error');
}
```

- [ ] **Step 6: Amazon link no-op + surface open failures.** In `renderOrder`, when `!hasAmazon` make the control inert (`amLink.style.pointerEvents='none'`) and never call `openAmazon` with a non-URL. Add a helper and use it for amazon/label/graphic opens:
```js
async function openExternal(url){
  if(!url || url==='#') return;
  const r = await API.openAmazon(url);
  if(r && !r.ok) toast(r.error||'Could not open link','error');
}
```
Wire `openLabel`/`printLabel` to toast `'error'` on `!ok` (they already check — change kind from `'gold'` to `'error'`).

- [ ] **Step 7: Verify**

Run: `node --check src/lbb/web/assets/app.js` → exit 0.
Run: `grep -nE "busy=false" src/lbb/web/assets/app.js` → present in engrave/confirmShip/onStatusSelect/flagRevision finally blocks.
Run: `grep -n "viewToken" src/lbb/web/assets/app.js` → used in openOrder + actions.

- [ ] **Step 8: Commit**

```bash
git add src/lbb/web/assets/app.js
git commit -m "fix(web): try/finally on all async actions, stale-request guard, null-safe poll, clipboard fallback"
```

---

### Task 5: Toast variants (success / error / info)

**Files:**
- Modify: `src/lbb/web/assets/app.js`
- Modify: `src/lbb/web/assets/app.css`

- [ ] **Step 1: Rewrite `toast`** in app.js to pick an icon + class by kind, and map legacy `'gold'`→`'error'`:

```js
const TOAST_ICONS = {
  success: '<path d="M20 6L9 17l-5-5"/>',
  error:   '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  info:    '<circle cx="12" cy="12" r="9"/><path d="M12 8h.01"/><path d="M11 12h1v4h1"/>',
};
function toast(msg, kind){
  if(kind==='gold'||kind==='pdf') kind='error';     // legacy aliases
  if(!TOAST_ICONS[kind]) kind='success';
  const wrap=document.getElementById('toastWrap'); const el=document.createElement('div');
  el.className='toast '+kind;
  el.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">'+TOAST_ICONS[kind]+'</svg><span>'+msg+'</span>';
  wrap.appendChild(el); requestAnimationFrame(()=>el.classList.add('show'));
  setTimeout(()=>{el.classList.remove('show');setTimeout(()=>el.remove(),300)},2600);
}
```

- [ ] **Step 2: Update error call-sites.** Grep `toast(` in app.js; any call passing `'gold'` for a FAILURE stays as `'error'` (the legacy map covers it, but prefer explicit `'error'`). Success messages get no kind (defaults success) or `'success'`. Informational ("Starting with…", "Flagged for revision", "Order put on hold") use `'info'`.

- [ ] **Step 3: CSS variants** — append to app.css (replace the single `.toast.gold` rule usage; keep base `.toast`):

```css
.toast.success svg{color:#2e9e5b}
.toast.error{border-color:#e6a3a3}
.toast.error svg{color:#d65745}
.toast.info svg{color:#2b6cb0}
.toast span{flex:1}
```

- [ ] **Step 4: Verify**

Run: `node --check src/lbb/web/assets/app.js` → exit 0.
Run: `grep -n "'gold'" src/lbb/web/assets/app.js` → ideally none left (all migrated to error/info).

- [ ] **Step 5: Commit**

```bash
git add src/lbb/web/assets/app.js src/lbb/web/assets/app.css
git commit -m "feat(web): toast variants — distinct success/error/info icon + color"
```

---

### Task 6: Skeleton loaders (dashboard + order view)

**Files:**
- Modify: `src/lbb/web/assets/app.js`
- Modify: `src/lbb/web/assets/app.css`

- [ ] **Step 1: Dashboard skeleton.** In `loadDashboard`, render skeletons before the await:
```js
async function loadDashboard(){
  const filter = document.querySelector('#filterChips .chip.active')?.dataset.f || 'all';
  const q = document.getElementById('searchInput').value || '';
  showDashboardSkeleton();
  const res = await API.listOrders(filter, q);
  ALL_ORDERS = (res && res.orders) || [];
  ORDERS = filterOrders(ALL_ORDERS, q);
  renderBanner(res && res.error, !!(res && res.error));
  renderDashboard();
}
function showDashboardSkeleton(){
  document.getElementById('dashSub').textContent='Loading…';
  let s=''; for(let i=0;i<5;i++){ s+='<div class="lrow skel"><div class="sk sk-a"></div><div class="sk sk-b"></div><div class="sk sk-c"></div><div class="sk sk-d"></div><div class="sk sk-c"></div><div></div></div>'; }
  document.getElementById('orderList').innerHTML=s;
}
```
(`ALL_ORDERS`/`filterOrders` are introduced in Task 8; for THIS task you may temporarily set `ORDERS=(res&&res.orders)||[]` and `renderBanner(res&&res.error)` with the existing single-arg signature, then Task 8 swaps in client-side filtering. Keep the skeleton + `renderDashboard()` call.)

- [ ] **Step 2: Order-view skeleton.** Add a `showOrderSkeleton()` that fills the order view's key containers (`#ordNo`, `#productVisual`, `#orderKv`, `#prodKv`, `#sides`) with `.sk` placeholders, and call it from `openOrder` right after `showView('order')` and before `getOrder` resolves:
```js
async function openOrder(orderNumber){
  const tok = nextToken();
  showView('order'); showOrderSkeleton(orderNumber);
  const o = await API.getOrder(orderNumber);
  if(tok!==viewToken) return;
  if(!o){ toast('Order not found','error'); goDashboard(); return; }
  CURRENT = o; active = firstPendingProduct(CURRENT); renderOrder();
}
function showOrderSkeleton(orderNumber){
  document.getElementById('ordNo').textContent='#'+orderNumber;
  document.getElementById('productVisual').innerHTML='<div class="sk sk-photo"></div>';
  document.getElementById('orderKv').innerHTML='<div class="sk sk-row"></div><div class="sk sk-row"></div><div class="sk sk-row"></div>';
  document.getElementById('prodKv').innerHTML='<div class="sk sk-row"></div><div class="sk sk-row"></div>';
  document.getElementById('sides').innerHTML='<div class="sk sk-side"></div><div class="sk sk-side"></div>';
}
```

- [ ] **Step 3: Skeleton CSS** — append to app.css:
```css
@keyframes shimmer{0%{background-position:-400px 0}100%{background-position:400px 0}}
.sk{background:#ece6da;background-image:linear-gradient(90deg,#ece6da 0,#f5f1e8 40px,#ece6da 80px);background-size:600px 100%;animation:shimmer 1.1s infinite linear;border-radius:8px;height:14px}
.lrow.skel{pointer-events:none}
.lrow.skel .sk-a{width:70%}.lrow.skel .sk-b{width:60%}.lrow.skel .sk-c{width:40%}.lrow.skel .sk-d{width:50%}
.sk-photo{width:100%;height:100%;min-height:220px;border-radius:14px}
.sk-row{height:18px;margin:8px 0;width:100%}
.sk-side{height:54px;margin:8px 0;border-radius:12px}
```

- [ ] **Step 4: Verify** `node --check src/lbb/web/assets/app.js` → exit 0.

- [ ] **Step 5: Commit**
```bash
git add src/lbb/web/assets/app.js src/lbb/web/assets/app.css
git commit -m "feat(web): skeleton loaders for dashboard and order view"
```

---

### Task 7: Wire up button spinners

**Files:**
- Modify: `src/lbb/web/assets/app.js`

The `.cta.is-loading` and `.sbtn.is-loading` styles already exist in app.css.

- [ ] **Step 1: Engrave spinner.** In `engrave`, add the class to the action-bar button and the specific side button at start; remove in `finally`:
```js
  const engBtnEl=document.getElementById('engraveBtn');
  if(engBtnEl) engBtnEl.classList.add('is-loading');
  // ... in finally:
  if(engBtnEl) engBtnEl.classList.remove('is-loading');
```
(If easy, also toggle `is-loading` on the side `.sbtn` for `(pi,si)` — optional but nice.)

- [ ] **Step 2: Ship spinner.** In `confirmShip`, add `is-loading` to the confirm button (`#modalBg .cta.secondary`) during the chain; keep the modal visible with the spinner until the chain resolves, then `closeModal()`. Remove the class in `finally`.

- [ ] **Step 3: Refresh spinner.** Wrap the Refresh button: change its `onclick` to a new `doRefresh()` that adds `is-loading`/disables `#refreshBtn`, awaits `loadDashboard()`, toasts `'Orders updated','success'`, then clears the class in `finally`. Update `index.html` `#refreshBtn` onclick to `doRefresh()`.

- [ ] **Step 4: Verify** `node --check src/lbb/web/assets/app.js` → exit 0; `grep -n "is-loading" src/lbb/web/assets/app.js` → present in engrave/confirmShip/doRefresh.

- [ ] **Step 5: Commit**
```bash
git add src/lbb/web/assets/app.js src/lbb/web/assets/index.html
git commit -m "feat(web): wire button spinners on engrave, ship, refresh"
```

---

### Task 8: Client-side search + product-photo cache

**Files:**
- Modify: `src/lbb/web/assets/app.js`
- Modify: `src/lbb/web/assets/index.html`

- [ ] **Step 1: Client-side search.** Introduce `let ALL_ORDERS=[];` alongside `ORDERS`. `loadDashboard` stores the full set in `ALL_ORDERS` and derives `ORDERS` via `filterOrders`. Add:
```js
function filterOrders(list, q){
  const needle=(q||'').toLowerCase().replace(/\s/g,'');
  if(!needle) return list.slice();
  return list.filter(c => (c.order_number||'').toLowerCase().replace(/\s/g,'').includes(needle));
}
function onSearchInput(){
  ORDERS = filterOrders(ALL_ORDERS, document.getElementById('searchInput').value||'');
  renderDashboard();                 // instant, no network
}
```
Change `index.html` search input `oninput="loadDashboard()"` → `oninput="onSearchInput()"`. (Filter chips still call `loadDashboard()` since they re-query the backend by status.) Keep `loadDashboard` filtering by chip only; server search arg may be passed as `''`.

- [ ] **Step 2: Product-photo cache.** Add `const PHOTO_CACHE={};` keyed by `order_number+'#'+idx`. In `loadProductPhoto`, return the cached data_uri immediately if present; otherwise fetch and store:
```js
async function loadProductPhoto(orderNumber, idx){
  const key=orderNumber+'#'+idx;
  const apply=(uri)=>{ if(!CURRENT||CURRENT.order_number!==orderNumber||active!==idx) return;
    const img=document.getElementById('prodPhoto');
    if(img){ img.onload=function(){ img.hidden=false; const ic=document.querySelector('#productVisual .prod-icon'); if(ic) ic.style.display='none'; }; img.src=uri; } };
  if(PHOTO_CACHE[key]){ apply(PHOTO_CACHE[key]); return; }
  let res; try { res = await API.productImage(orderNumber, idx); } catch(e){ return; }
  if(res && res.ok && res.data_uri){ PHOTO_CACHE[key]=res.data_uri; apply(res.data_uri); }
}
```

- [ ] **Step 3: Verify** `node --check src/lbb/web/assets/app.js` → exit 0; `grep -n "onSearchInput\|ALL_ORDERS\|PHOTO_CACHE" src/lbb/web/assets/app.js` → present; `grep -n "loadDashboard()" src/lbb/web/assets/index.html` → only on the refresh path / chips, NOT on the search input.

- [ ] **Step 4: Commit**
```bash
git add src/lbb/web/assets/app.js src/lbb/web/assets/index.html
git commit -m "feat(web): instant client-side search + product-photo cache"
```

---

### Task 9: Refresh feedback, actionable error banner, differentiated empty states

**Files:**
- Modify: `src/lbb/web/assets/app.js`
- Modify: `src/lbb/web/assets/app.css`

- [ ] **Step 1: Actionable error banner.** Update `renderBanner` to add a Retry + dismiss:
```js
function renderBanner(error){
  let bar = document.getElementById('apiBanner');
  if(!bar){ bar=document.createElement('div'); bar.id='apiBanner'; bar.className='api-banner'; document.body.prepend(bar); }
  if(error){
    bar.innerHTML='<span>⚠ '+error+'</span> <button class="bnr-btn" onclick="loadDashboard()">Retry</button><button class="bnr-x" onclick="this.parentNode.hidden=true">✕</button>';
    bar.hidden=false;
  } else bar.hidden=true;
}
```

- [ ] **Step 2: Differentiated empty states.** In `renderDashboard`, when `ORDERS.length===0`, branch the message: if the last load had an error → "Couldn't reach Flanacom — use Retry above"; else if a search query is present → "No orders match \"<q>\""; else if the active chip is `done` → "No shipped orders yet"; else → "All caught up — no open orders ✓" (celebratory). Track the error via a module flag set in `loadDashboard` (`lastLoadError = !!(res&&res.error)`).

- [ ] **Step 3: "Updated" timestamp.** After a successful (non-error) load, set a small `#dashUpdated` element (add it next to `#dashSub` in index.html) to `Updated HH:MM`. Compute time with `new Date()` in the browser (allowed in JS; this is not the Python sandbox).

- [ ] **Step 4: CSS** — append:
```css
.api-banner{display:flex;align-items:center;gap:10px}
.bnr-btn{font:inherit;font-size:12px;font-weight:600;padding:4px 10px;border-radius:8px;border:1px solid #d8a; background:#fff;cursor:pointer}
.bnr-x{margin-left:auto;border:none;background:none;cursor:pointer;font-size:14px;color:inherit}
.dash-updated{font-size:12px;color:var(--ink-faint);margin-left:8px}
.empty.cheer{color:#2e9e5b}
```

- [ ] **Step 5: Verify** `node --check src/lbb/web/assets/app.js` → exit 0.

- [ ] **Step 6: Commit**
```bash
git add src/lbb/web/assets/app.js src/lbb/web/assets/app.css src/lbb/web/assets/index.html
git commit -m "feat(web): refresh timestamp, retry/dismiss error banner, friendly empty states"
```

---

### Task 10: Modal dismissal + micro-polish

**Files:**
- Modify: `src/lbb/web/assets/app.js`
- Modify: `src/lbb/web/assets/index.html`
- Modify: `src/lbb/web/assets/app.css`

- [ ] **Step 1: Escape + backdrop close.** Add once at bootstrap:
```js
document.addEventListener('keydown', e=>{ if(e.key==='Escape') closeModal(); });
document.getElementById('modalBg').addEventListener('click', e=>{ if(e.target.id==='modalBg') closeModal(); });
```

- [ ] **Step 2: Side-done pop animation.** Add CSS:
```css
@keyframes pop{0%{transform:scale(.6);opacity:0}60%{transform:scale(1.15)}100%{transform:scale(1);opacity:1}}
.side.done .sicon{animation:pop .35s ease}
```

- [ ] **Step 3: Label "Open" → real button.** In index.html change the label `<a ... onclick="openLabel();return false;">` to `<button class="fbtn" onclick="openLabel()">…</button>` (keep classes/SVG/label).

- [ ] **Step 4: SVG fallbacks.** In `productSVG`, add `MiniFlask` (reuse the Flask shape) and `Lighter` (a simple rounded-rect lighter) branches so those types get a real icon instead of the generic box.

- [ ] **Step 5: Verify** `node --check src/lbb/web/assets/app.js` → exit 0; `grep -n "Escape" src/lbb/web/assets/app.js` → present.

- [ ] **Step 6: Commit**
```bash
git add src/lbb/web/assets/app.js src/lbb/web/assets/index.html src/lbb/web/assets/app.css
git commit -m "feat(web): modal escape/backdrop close, side-done pop, label button, MiniFlask/Lighter icons"
```

---

### Task 11: Full verification + live smoke + rebuild (controller-run)

- [ ] **Step 1: Whole suite + contracts + lint + JS**
```
uv run pytest -q              # all pass + 4 skipped
uv run lint-imports           # 2 contracts kept
uv run ruff check src tests
node --check src/lbb/web/assets/app.js
node --check src/lbb/web/assets/bridge-client.js
```

- [ ] **Step 2: Live GUI smoke** (`uv run python -m lbb`) against the 3 real orders. Verify: skeletons on cold load + opening an order; search is instant; engrave/ship/refresh show spinners; error toasts look like errors; modal closes on Escape/backdrop; Refresh shows "Orders updated"; product photos cached across tabs; nothing freezes after an action. Debug any issue (systematic-debugging) against the live payload before finishing.

- [ ] **Step 3: Rebuild + reinstall artifacts**
```
uv run pyinstaller packaging/lbb.spec --clean --noconfirm
"$HOME/AppData/Local/Programs/Inno Setup 6/ISCC.exe" packaging/installer.iss   # if updating the installer
```

- [ ] **Step 4: Finish the branch** — open a PR via `superpowers:finishing-a-development-branch`.

---

## Notes for the executor

- No secret handling changes; key stays in `~/.flanacom-tool/config.json`.
- No new dependencies; `time`/`base64` are stdlib.
- Windows date formatting in Python uses `.day` (never `%-d`). Browser JS may use `new Date()` freely.
- Frontend tasks share files and run sequentially — each implementer READS the current file before editing and matches exact strings.
- `import-linter` contracts must stay green (core stays pure; web never imports adapters).
- Preserve audit-confirmed-correct behavior listed in the spec (notably: `mark_engraved` AFTER successful LightBurn load; `list_orders` always re-GETs; writes invalidate cache).
