# Re-engrave a Finished Side Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the operator re-engrave an already-finished side via a clear ↻ icon with a one-click confirm, reusing the existing engrave plumbing.

**Architecture:** Frontend-only. The engraved-side control becomes a non-clickable "✓ Engraved" status chip plus a ↻ re-engrave icon button; clicking it confirms, then calls the existing `runEngrave(pi, si, closePrevious, isRedo)` (idempotent backend — no change). The confirm silently handles close-previous so there's one prompt, not two.

**Tech Stack:** vanilla JS/CSS in pywebview assets.

**Reference spec:** `docs/superpowers/specs/2026-06-25-re-engrave-side-design.md`

## Global Constraints
- No backend change (engrave is idempotent on already-engraved keys); existing 155 tests stay green.
- CRITICAL: the new "✓ Engraved" status chip must use a NON-`.sbtn` class (`.sdone`), because `runEngrave` selects the per-side spinner button via `document.querySelectorAll('#sides .side .sbtn')[si]` — exactly one `.sbtn` must remain per side row (the `redo` or `go` button).
- Reuse the `#lbModalBg` / `runEngrave` / `showView`-clears-pending patterns from the merged close-previous feature.
- Frontend has no unit harness — verify with `node --check` + grep guards. READ each asset fully before editing; match current strings exactly.
- `uv run` for Python checks. Commit after each task. Branch `feature/re-engrave-side` (off main `9ce878a`, which already has `runEngrave`/`#lbModalBg`).

---

### Task 1: Re-engrave icon, confirm modal, and `runEngrave` redo toast

**Files:**
- Modify: `src/lbb/web/assets/app.js`
- Modify: `src/lbb/web/assets/index.html`
- Modify: `src/lbb/web/assets/app.css`

**Interfaces:**
- Consumes: `runEngrave(pi, si, closePrevious)` (existing) → extended to `runEngrave(pi, si, closePrevious, isRedo)`; `API.lightburnStatus()`; `showView()`; the keydown/backdrop listeners.
- Produces: `askReengrave(pi, si)`, `confirmReengrave()`, `closeReModal()`, `_reSide`; `#reModalBg` / `#reText` markup.

- [ ] **Step 1: Engraved-side rendering** — in `app.js`, find the `#sides` map (the engraved branch is the line with `class="sbtn ok"` ... `title="Re-open in LightBurn"` ... `Engraved</button>`). Replace ONLY that engraved-branch string (the `s.engraved ? '...'` value) with a status chip + redo button:

```javascript
      ? '<span class="sact"><span class="sdone"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>Engraved</span><button class="sbtn redo" title="Re-engrave" onclick="askReengrave('+active+','+si+')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M23 4v6h-6"/><path d="M1 20v-6h6"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg></button></span>'
```

Leave the un-engraved branch (`class="sbtn go"`) exactly as-is.

- [ ] **Step 2: Re-engrave helpers** — in `app.js`, immediately AFTER the existing close-previous helpers (`function confirmClosePrev(){ ... }`), add:

```javascript
let _reSide = null;
function askReengrave(pi, si){
  if(busy) return;
  const side = CURRENT.products[pi].sides[si];
  _reSide = {pi, si};
  const t = document.getElementById('reText');
  if(t) t.textContent = 'Re-engrave ' + side.name + '? The design will reopen in LightBurn for another run.';
  const m = document.getElementById('reModalBg'); if(m) m.classList.add('show');
}
function closeReModal(){ const m = document.getElementById('reModalBg'); if(m) m.classList.remove('show'); _reSide = null; }
async function confirmReengrave(){
  const r = _reSide; closeReModal();
  if(!r) return;
  let running = false;
  try { const s = await API.lightburnStatus(); running = !!(s && s.running); } catch(e){ running = false; }
  runEngrave(r.pi, r.si, running, true);
}
```

- [ ] **Step 3: `runEngrave` redo toast** — in `app.js`, change the `runEngrave` signature to take `isRedo` and update the success toast. Change the line:

```javascript
async function runEngrave(pi, si, closePrevious){
```
to:
```javascript
async function runEngrave(pi, si, closePrevious, isRedo){
```
and change the success toast line:
```javascript
    toast(side.name+' engraved'+(allEng(CURRENT)?' · all done':''));
```
to:
```javascript
    toast(side.name + (isRedo ? ' re-engraved' : (' engraved' + (allEng(CURRENT) ? ' · all done' : ''))));
```
(The existing close-previous call sites `runEngrave(pi,si,true)` / `runEngrave(pi,si,false)` pass no 4th arg → `isRedo` is `undefined` → falsy → unchanged behavior.)

- [ ] **Step 4: Navigation + Escape + backdrop** — in `app.js`:
  - In `showView`, the line `closeLbModal();` → add `closeReModal();` right after it:
    ```javascript
    closeLbModal();                           // abandon any pending close-previous confirm on navigation
    closeReModal();                           // abandon any pending re-engrave confirm on navigation
    ```
  - The keydown listener `if(e.key==='Escape'){ closeModal(); closeLbModal(); }` → add `closeReModal();`:
    ```javascript
    document.addEventListener('keydown', e=>{ if(e.key==='Escape'){ closeModal(); closeLbModal(); closeReModal(); } });
    ```
  - After the `#lbModalBg` backdrop listener, add:
    ```javascript
    document.getElementById('reModalBg').addEventListener('click', e=>{ if(e.target.id==='reModalBg') closeReModal(); });
    ```

- [ ] **Step 5: Confirm modal markup** — in `index.html`, add immediately AFTER the `#lbModalBg` modal block (the `<div class="modal-bg" id="lbModalBg">…</div>`) and BEFORE `<div class="toast-wrap" id="toastWrap"></div>`:

```html
<div class="modal-bg" id="reModalBg">
  <div class="modal">
    <div class="m-ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M23 4v6h-6"/><path d="M1 20v-6h6"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg></div>
    <h3>Re-engrave this side?</h3>
    <p id="reText">Re-engrave? The design will reopen in LightBurn for another run.</p>
    <div class="m-actions">
      <button class="btn" onclick="closeReModal()">Cancel</button>
      <button class="cta primary" onclick="confirmReengrave()">Re-engrave →</button>
    </div>
  </div>
</div>
```

- [ ] **Step 6: CSS** — append to `app.css` (near the other `.side .sbtn` rules):

```css
  .side .sact{display:inline-flex;align-items:center;gap:8px}
  .side .sdone{display:inline-flex;align-items:center;gap:7px;font-size:12.5px;font-weight:700;padding:8px 13px;border-radius:10px;background:var(--ok-soft);color:var(--ok-ink);border:1px solid rgba(31,157,99,.3)}
  .side .sdone svg{width:14px;height:14px}
  .side .sbtn.redo{background:transparent;color:var(--ink-soft);border-color:var(--line-strong);padding:8px 9px}
  .side .sbtn.redo svg{width:15px;height:15px}
  .side .sbtn.redo:hover{background:var(--accent-soft);color:var(--accent-ink);border-color:rgba(184,137,58,.4);transform:translateY(-1px)}
```

- [ ] **Step 7: Verify**

Run: `node --check src/lbb/web/assets/app.js`
Expected: exit 0.
Run these greps (all must hold):
- `grep -c "function askReengrave\|function confirmReengrave\|function closeReModal" src/lbb/web/assets/app.js` → 3
- `grep -c "runEngrave(r.pi, r.si, running, true)" src/lbb/web/assets/app.js` → 1
- `grep -c "class=\"sdone\"" src/lbb/web/assets/app.js` → 1 (the status chip)
- `grep -c "askReengrave(" src/lbb/web/assets/app.js` → 2 (the onclick string + the function def)
- `grep -c "reModalBg" src/lbb/web/assets/index.html` → 1
- `grep -c "closeReModal()" src/lbb/web/assets/app.js` → at least 4 (showView, keydown, backdrop, def, plus confirm/ask use closeReModal) — confirm it appears in showView and the keydown handler
- Confirm exactly one `.sbtn` per side row: `grep -c "sbtn ok" src/lbb/web/assets/app.js` → 0 (the engraved branch no longer uses `sbtn ok`; it uses `sdone` + `sbtn redo`).

- [ ] **Step 8: Commit**

```bash
git add src/lbb/web/assets/app.js src/lbb/web/assets/index.html src/lbb/web/assets/app.css
git commit -m "feat(web): re-engrave a finished side via ↻ icon + one-click confirm"
```

---

### Task 2: Verification + live smoke + rebuild (controller-run)

- [ ] **Step 1: Suite + contracts + lint + JS**
```
uv run pytest -q              # 155 passed, 4 skipped (no backend change)
uv run lint-imports           # 2 contracts kept
uv run ruff check src tests
node --check src/lbb/web/assets/app.js
node --check src/lbb/web/assets/bridge-client.js
```

- [ ] **Step 2: Live GUI smoke** (`uv run python -m lbb`) with LightBurn installed:
  - On an order with engraved sides, each engraved side shows **✓ Engraved** (status) + a **↻** icon.
  - Click ↻ → confirm modal "Re-engrave <Side>?" → **Re-engrave** → LightBurn closes & reopens that PDF (no save prompt; pill "Closing previous · opening LightBurn…"); toast "<Side> re-engraved"; the side stays Engraved.
  - **Cancel** / **Escape** / backdrop → nothing happens, no state change.
  - Un-engraved sides still show the normal **Engrave <side>** button (with the close-previous prompt).
  - The per-side spinner shows on the ↻ button during re-engrave (no layout break).
  Debug any issue (systematic-debugging) against the live setup before finishing.

- [ ] **Step 3: Rebuild artifacts**
```
uv run pyinstaller packaging/lbb.spec --clean --noconfirm
"$HOME/AppData/Local/Programs/Inno Setup 6/ISCC.exe" packaging/installer.iss
```

- [ ] **Step 4: Finish the branch** — open a PR via `superpowers:finishing-a-development-branch`.

---

## Notes for the executor

- The chip class is `.sdone` (NOT `.sbtn`) on purpose — keeps one `.sbtn` per side row so `runEngrave`'s `querySelectorAll('#sides .side .sbtn')[si]` spinner targeting stays correct (it will spin the ↻ button during a re-engrave).
- `confirmReengrave` decides `close_previous` itself (fresh `lightburn_status`), so re-engrave is ONE confirm, not two — it never routes through `engrave()`'s separate close-previous prompt.
- No backend change: marking an already-engraved key is idempotent, so the side stays Engraved after a re-engrave.
