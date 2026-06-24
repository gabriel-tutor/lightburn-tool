# Close Previous LightBurn Job Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the operator engraves the next side and LightBurn is already running, auto-close the previous job (after a one-click confirm) and open the new PDF fresh — no manual "Save changes?" handling.

**Architecture:** Reuse the existing, unused `LightBurnPort.close_running()` (force-close via taskkill/pkill). Add a `close_previous` flag to `engrave_side` (service + bridge) that calls `close_running()` before `load_file()`. The front-end gates it with a quick confirm modal shown only when LightBurn is running.

**Tech Stack:** Python 3.12 + uv + pytest; vanilla JS/CSS in pywebview assets.

**Reference spec:** `docs/superpowers/specs/2026-06-25-close-previous-lightburn-design.md`

## Global Constraints
- No new dependencies; no new ports/adapters (`close_running` already exists).
- Preserve mark-on-success: the engraved key is marked only AFTER a successful `load_file`.
- Preserve the hardened engrave flow: `busy` lock, `viewToken` stale-guard, `.is-loading` spinners, try/finally.
- `uv run` for all Python. Single test: `uv run pytest <path>::<name> -v`. Suite: `uv run pytest -q`. Commit after each task. Branch `feature/close-previous-lightburn`.
- Frontend has no unit harness — verify with `node --check` + grep guards. READ each asset fully before editing; match current strings exactly.

---

### Task 1: Service — `close_previous` flag on `engrave_side`

**Files:**
- Modify: `src/lbb/app/fulfillment_service.py`
- Test: `tests/integration/test_fulfillment_service.py`

**Interfaces:**
- Consumes: `LightBurnPort.close_running()` (already on the port + `LightBurnShellAdapter`).
- Produces: `FulfillmentService.engrave_side(order_number: str, file_key: str, close_previous: bool = False) -> dict` — when `close_previous` is True, calls `lightburn.close_running()` after a successful download and before `lightburn.load_file(pdf)`.

- [ ] **Step 1: Extend the test fake + write failing tests**

In `tests/integration/test_fulfillment_service.py`, replace the `FakeLightBurn` class (currently lines ~53-61) with one that records an ordered event log AND keeps the existing `loaded` list (existing tests assert `lb.loaded`):

```python
class FakeLightBurn:
    def __init__(self):
        self.loaded = []
        self.events = []          # ordered: 'close' / ('load', path)

    def is_running(self):
        return True

    def load_file(self, path):
        self.loaded.append(path)
        self.events.append(('load', path))

    def close_running(self):
        self.events.append('close')
```

Append these tests:

```python
def test_engrave_close_previous_closes_before_load(tmp_path):
    gw = FakeGateway([_order()])
    lb = FakeLightBurn()
    svc = FulfillmentService(gateway=gw, state=MemState(),
                             lightburn=lb, cache_dir=tmp_path)
    res = svc.engrave_side("306-1", "engraving/x Front.pdf", close_previous=True)
    assert res["ok"] is True
    # close must happen, and strictly before the load
    assert lb.events[0] == 'close'
    assert lb.events[1][0] == 'load'


def test_engrave_default_does_not_close(tmp_path):
    gw = FakeGateway([_order()])
    lb = FakeLightBurn()
    svc = FulfillmentService(gateway=gw, state=MemState(),
                             lightburn=lb, cache_dir=tmp_path)
    svc.engrave_side("306-1", "engraving/x Front.pdf")          # default close_previous=False
    assert 'close' not in lb.events
    assert lb.loaded                                            # still loaded the pdf


def test_engrave_close_skipped_when_download_fails(tmp_path):
    class BoomGateway(FakeGateway):
        def download_file(self, order_id, file_key, dest_dir):
            from lbb.ports.engraving import EngravingApiError
            raise EngravingApiError("network down")
    gw = BoomGateway([_order()])
    lb = FakeLightBurn()
    svc = FulfillmentService(gateway=gw, state=MemState(),
                             lightburn=lb, cache_dir=tmp_path)
    res = svc.engrave_side("306-1", "engraving/x Front.pdf", close_previous=True)
    assert res["ok"] is False
    assert lb.events == []           # never closed LightBurn — download failed first
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/integration/test_fulfillment_service.py -q`
Expected: FAIL (`engrave_side` has no `close_previous` param / TypeError or close not called).

- [ ] **Step 3: Edit `engrave_side`** in `src/lbb/app/fulfillment_service.py`

Replace the current method:

```python
    def engrave_side(self, order_number: str, file_key: str,
                     close_previous: bool = False) -> dict:
        o = self.gateway.get(order_number)
        if o is None:
            return {"ok": False, "error": "Order not found"}
        if file_key not in all_sides(o):
            return {"ok": False, "error": "Unknown engraving file"}
        try:
            pdf = self.gateway.download_file(o.order_id, file_key, self._dir(o))
            if close_previous:
                # Force-close the previous LightBurn job so the new PDF opens in
                # a fresh workspace with no "Save changes?" prompt. Safe when not
                # running. Done after a successful download so a download failure
                # never needlessly kills LightBurn.
                self.lightburn.close_running()
            self.lightburn.load_file(pdf)
        except (EngravingApiError, LbbError, OSError) as e:
            return {"ok": False, "error": str(e)}
        self.state.mark_engraved(order_number, file_key, True)
        done, total = self._progress(o)
        return {"ok": True, "status": str(o.status),
                "progress": {"done": done, "total": total}}
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/integration/test_fulfillment_service.py -q`
Expected: PASS (existing + 3 new). Then `uv run pytest -q` (full suite green) and `uv run ruff check src tests`.

- [ ] **Step 5: Commit**

```bash
git add src/lbb/app/fulfillment_service.py tests/integration/test_fulfillment_service.py
git commit -m "feat(service): close_previous flag on engrave_side (close LightBurn before load)"
```

---

### Task 2: Bridge — thread `close_previous` through

**Files:**
- Modify: `src/lbb/web/bridge.py`
- Test: `tests/web/test_bridge.py`

**Interfaces:**
- Consumes: `FulfillmentService.engrave_side(order_number, file_key, close_previous=False)` from Task 1.
- Produces: `JsApiBridge.engrave_side(order_number, file_key, close_previous=False)` — forwards all three args to the service.

- [ ] **Step 1: Update the fake + add a test** in `tests/web/test_bridge.py`

In `FakeService`, change `engrave_side` to capture the flag:

```python
    def engrave_side(self, n, file_key, close_previous=False):
        self.calls.append(("engrave", n, file_key, close_previous))
        return {"ok": True}
```

Add a test:

```python
def test_bridge_passes_close_previous():
    svc = FakeService()
    b = JsApiBridge(svc)
    b.engrave_side("306-1", "engraving/x Front.pdf", True)
    assert ("engrave", "306-1", "engraving/x Front.pdf", True) in svc.calls
    # default is False when omitted
    b.engrave_side("306-1", "engraving/x Front.pdf")
    assert ("engrave", "306-1", "engraving/x Front.pdf", False) in svc.calls
```

(If the existing `test_bridge_delegates_queries_and_commands` asserts a 3-tuple `("engrave", ...)`, update that assertion to the new 4-tuple shape, OR keep that test's call and add the flag — read the file and adjust the existing engrave assertion to match the new `FakeService.engrave_side` recording shape.)

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/web/test_bridge.py -q`
Expected: FAIL (bridge ignores / can't pass the 3rd arg, or tuple-shape mismatch).

- [ ] **Step 3: Edit `engrave_side`** in `src/lbb/web/bridge.py`

```python
    def engrave_side(self, order_number, file_key, close_previous=False):
        return self._svc.engrave_side(order_number, file_key, close_previous)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/web/test_bridge.py -q`
Expected: PASS. Then `uv run pytest -q` and `uv run ruff check src tests`.

- [ ] **Step 5: Commit**

```bash
git add src/lbb/web/bridge.py tests/web/test_bridge.py
git commit -m "feat(web): bridge forwards close_previous to engrave_side"
```

---

### Task 3: Front-end — confirm modal + engrave split

**Files:**
- Modify: `src/lbb/web/assets/app.js`
- Modify: `src/lbb/web/assets/index.html`
- Modify: `src/lbb/web/assets/app.css`

No unit harness — verify with `node --check` + greps. READ app.js fully first.

**Interfaces:**
- Consumes: `API.engraveSide(order_number, file_key, close_previous)` (bridge-client's generic `wrap()` already forwards a 3rd arg — no bridge-client.js change needed), `API.lightburnStatus()`.

- [ ] **Step 1: Add the confirm modal markup** to `index.html`, immediately AFTER the existing ship modal block (the `<div class="modal-bg" id="modalBg">…</div>` that ends before `<div class="toast-wrap"...>`):

```html
<div class="modal-bg" id="lbModalBg">
  <div class="modal">
    <div class="m-ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg></div>
    <h3>Close the previous job?</h3>
    <p>LightBurn still has a job open. Close it and open this side in a fresh LightBurn?</p>
    <div class="m-actions">
      <button class="btn" onclick="closeLbModal()">Cancel</button>
      <button class="cta primary" onclick="confirmClosePrev()">Close &amp; open →</button>
    </div>
  </div>
</div>
```

- [ ] **Step 2: Split `engrave` into decision + execution** in `app.js`

Replace the current `async function engrave(pi, si){ ... }` (the whole function) with the decision wrapper PLUS the renamed body. The body is identical to today's engrave EXCEPT: it is named `runEngrave`, takes a `closePrevious` arg, sets the pill text accordingly, and passes the flag to `API.engraveSide`:

```javascript
let _pendingEngrave = null;
function askClosePrev(onYes){ _pendingEngrave = onYes; document.getElementById('lbModalBg').classList.add('show'); }
function closeLbModal(){ document.getElementById('lbModalBg').classList.remove('show'); _pendingEngrave = null; }
function confirmClosePrev(){ const fn = _pendingEngrave; closeLbModal(); if(fn) fn(); }

async function engrave(pi, si){
  if(busy) return;
  let running = false;
  try { const s = await API.lightburnStatus(); running = !!(s && s.running); } catch(e){ running = false; }
  if(running){ askClosePrev(() => runEngrave(pi, si, true)); return; }
  runEngrave(pi, si, false);
}

async function runEngrave(pi, si, closePrevious){
  if(busy) return;
  const p = CURRENT.products[pi], side = p.sides[si];
  if(active!==pi){ active=pi; }
  busy=true; renderOrder();
  const engBtnEl=document.getElementById('engraveBtn');
  if(engBtnEl) engBtnEl.classList.add('is-loading');
  const sideBtnEl=document.querySelectorAll('#sides .side .sbtn')[si];
  if(sideBtnEl) sideBtnEl.classList.add('is-loading');
  document.getElementById('livePillText').textContent = closePrevious ? 'Closing previous · opening LightBurn…' : 'Opening LightBurn…';
  const tok = viewToken;
  try {
    const res = await API.engraveSide(CURRENT.order_number, side.file_key, closePrevious);
    if(!res || !res.ok){ toast((res && res.error) || 'Engrave failed','error'); return; }
    const fresh = await API.getOrder(CURRENT.order_number);
    if(tok!==viewToken) return;
    if(!fresh){ toast('Could not refresh order','error'); goDashboard(); return; }
    CURRENT = fresh;
    const np = tasksOf(CURRENT).find(t=>!t.s.engraved); if(np) active=np.pi;
    toast(side.name+' engraved'+(allEng(CURRENT)?' · all done':''));
  } catch(e){
    toast('Engrave failed','error');
  } finally {
    busy=false;
    if(engBtnEl) engBtnEl.classList.remove('is-loading');
    if(sideBtnEl) sideBtnEl.classList.remove('is-loading');
    if(tok===viewToken) renderOrder();
  }
}
```

(`engraveNext()` already calls `engrave(np.pi, np.si)` — leave it; it now inherits the prompt. The side buttons' `onclick="engrave(active,si)"` are unchanged.)

- [ ] **Step 3: Extend Escape + backdrop close** to cover the new modal.

Find the bootstrap keydown/backdrop listeners (added previously, near the bottom — `document.addEventListener('keydown', e=>{ if(e.key==='Escape') closeModal(); });` and the `#modalBg` click listener). Update them so Escape closes BOTH modals and add a backdrop listener for `#lbModalBg`:

```javascript
document.addEventListener('keydown', e=>{ if(e.key==='Escape'){ closeModal(); closeLbModal(); } });
document.getElementById('modalBg').addEventListener('click', e=>{ if(e.target.id==='modalBg') closeModal(); });
document.getElementById('lbModalBg').addEventListener('click', e=>{ if(e.target.id==='lbModalBg') closeLbModal(); });
```

(Replace the existing keydown + modalBg lines with these three; do not duplicate the keydown listener.)

- [ ] **Step 4: Verify**

Run: `node --check src/lbb/web/assets/app.js`
Expected: exit 0.
Run: `grep -n "function runEngrave\|askClosePrev\|lbModalBg\|engraveSide(CURRENT.order_number, side.file_key, closePrevious)" src/lbb/web/assets/app.js` → all present.
Run: `grep -c "async function engrave(" src/lbb/web/assets/app.js` → exactly 1 (the decision wrapper; body is `runEngrave`).

- [ ] **Step 5: Commit**

```bash
git add src/lbb/web/assets/app.js src/lbb/web/assets/index.html src/lbb/web/assets/app.css
git commit -m "feat(web): one-click confirm to close previous LightBurn job before engrave"
```

(`app.css` is staged in case the new modal needs no new rules — it reuses `.modal-bg/.modal/.m-ic/.m-actions`. If a visual gap appears in the smoke test, add rules then.)

---

### Task 4: Full verification + live smoke + rebuild (controller-run)

- [ ] **Step 1: Suite + contracts + lint + JS**
```
uv run pytest -q              # all pass + 4 skipped (was 151 → now 156)
uv run lint-imports           # 2 contracts kept
uv run ruff check src tests
node --check src/lbb/web/assets/app.js
node --check src/lbb/web/assets/bridge-client.js
```

- [ ] **Step 2: Live GUI smoke** (`uv run python -m lbb`) against the 3 real orders, with LightBurn installed:
  - First engrave (LightBurn closed) → **no prompt**, opens the PDF in LightBurn.
  - Second engrave while LightBurn is open → **confirm modal** appears; "Close & open" force-closes LightBurn and opens the new PDF fresh (no "Save changes?" dialog); pill reads "Closing previous · opening LightBurn…".
  - Cancel → nothing happens, no state change.
  - Escape / backdrop close the confirm modal.
  Debug any issue (systematic-debugging) against the live setup before finishing.

- [ ] **Step 3: Rebuild artifacts**
```
uv run pyinstaller packaging/lbb.spec --clean --noconfirm
"$HOME/AppData/Local/Programs/Inno Setup 6/ISCC.exe" packaging/installer.iss
```

- [ ] **Step 4: Finish the branch** — open a PR via `superpowers:finishing-a-development-branch`.

---

## Notes for the executor

- `close_running()` on `LightBurnShellAdapter` runs `taskkill /F /IM LightBurn.exe` (Windows) / `pkill -x LightBurn` (POSIX) and tolerates "no process" — it never raises.
- The fresh `lightburnStatus()` check on engrave-click is intentionally separate from the 3s poll, so the prompt decision is current, not up-to-3s stale.
- Keep the engrave flow's hardening intact (busy lock, viewToken guard, spinners, try/finally) — `runEngrave` is the existing body verbatim plus the flag + pill text.
