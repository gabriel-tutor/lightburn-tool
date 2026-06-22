# Dynamic API-Driven Order Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the order screen fully data-driven — show the real product reference photo, a truthful Engrave→Ship status flow, and every meaningful field Hauke's API exposes — and delete the leftover static prototype UI.

**Architecture:** Backend gains order fields + a `product_image` service method (base64 `data:` URI served through the existing gateway). Front-end renders the real photo (icon fallback), a two-stage status strip with a revision state, the extra fields, and drops dead UI. Stays inside the hexagon; no new dependency.

**Tech Stack:** Python 3.12, `uv`, pytest, stdlib `base64`, pywebview, vanilla JS/CSS.

**Reference:** `docs/superpowers/specs/2026-06-23-dynamic-order-screen-design.md`

**Conventions:** run with `uv run`. Single test: `uv run pytest <path>::<name> -v`. Suite: `uv run pytest -q`. Commit after each task. Work from `C:\Users\Client\Documents\hauke\lightburn-tool`, branch `feature/fulfillment-studio`.

---

### Task 1: Domain — new order fields + `coin_count` + `sides_summary`

**Files:**
- Modify: `src/lbb/core/fulfillment.py`
- Test: `tests/unit/core/test_fulfillment.py`

- [ ] **Step 1: Append failing tests** to `tests/unit/core/test_fulfillment.py`:

```python
from lbb.core.fulfillment import sides_summary


def test_sides_summary_single_coin():
    p = Product(product_type="Necklace",
                sides=(Side("Front", "a"), Side("Back", "b")), coin_count=1)
    assert sides_summary(p) == "Front & Back"


def test_sides_summary_front_only():
    p = Product(product_type="Keychain", sides=(Side("Front", "a"),), coin_count=1)
    assert sides_summary(p) == "Front only"


def test_sides_summary_multiple_coins():
    p = Product(product_type="Necklace",
                sides=(Side("Coin 1 Front", "a"), Side("Coin 1 Back", "b"),
                       Side("Coin 2 Front", "c"), Side("Coin 2 Back", "d")),
                coin_count=2)
    assert sides_summary(p) == "2 coins · Front & Back each — 4 jobs"


def test_sides_summary_no_sides():
    p = Product(product_type="Necklace", sides=(), coin_count=0)
    assert sides_summary(p) == "No engraving files"


def test_new_order_fields_default_empty():
    o = _order()
    assert o.link_to_graphic == ""
    assert o.created_at is None and o.updated_at is None
    assert o.order_picture_key == "" and o.type_summary == "" and o.color_summary == ""


def test_queue_sort_falls_back_to_type_summary_when_no_products():
    o = FulfillmentOrder(order_id="x", order_number="A", products=(), type_summary="Flask")
    assert queue_sort_key(o)[0] == type_rank("Flask")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/core/test_fulfillment.py -q`
Expected: FAIL (no `sides_summary`, no `coin_count`, new fields missing).

- [ ] **Step 3: Edit `src/lbb/core/fulfillment.py`**

In `Product`, add a `coin_count` field (after `qty`):

```python
@dataclass(frozen=True, slots=True)
class Product:
    product_type: str            # normalized (title case)
    band_color: str = ""         # color_band_chain
    coin_color: str = ""         # color_coin_plate
    sides: tuple[Side, ...] = ()
    qty: int = 1
    coin_count: int = 1          # number of coins/plates on this item
    image_key: str = ""
    multiple_coins: bool = False
    special_length: bool = False
    length: str = ""
```

In `FulfillmentOrder`, add the new fields (after `placed_at`):

```python
@dataclass(frozen=True, slots=True)
class FulfillmentOrder:
    order_id: str                 # API uuid — required to write status back
    order_number: str
    products: tuple[Product, ...]
    amount: int = 0
    status: OrderStatus = OrderStatus.NOT_DONE
    instruction: str = ""         # API `comment` — read-only note from Flanacom
    amazon_url: str = ""          # link_to_order
    label_key: str = ""           # shipping_label_path (signed_urls key)
    placed_at: datetime | None = None
    link_to_graphic: str = ""     # order-level link_to_graphic (often null)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    order_picture_key: str = ""   # order-level product_picture_path (often null)
    type_summary: str = ""        # order-level product_type (normalized)
    color_summary: str = ""       # order-level color
    channel: str = "Amazon · DE"

    @property
    def gift_box(self) -> bool:
        return "gift" in self.instruction.lower()
```

Add the `sides_summary` helper (near `all_sides`):

```python
def sides_summary(product: Product) -> str:
    """Human description of a product's engraving jobs."""
    n = len(product.sides)
    if n == 0:
        return "No engraving files"
    coins = max(product.coin_count, 1)
    if coins == 1:
        return "Front & Back" if n == 2 else ("Front only" if n == 1 else f"{n} engraving jobs")
    if n == coins * 2:
        return f"{coins} coins · Front & Back each — {n} jobs"
    if n == coins:
        return f"{coins} coins · Front only — {n} jobs"
    return f"{coins} coins · {n} engraving jobs"
```

Update `queue_sort_key` to fall back to `type_summary`:

```python
def queue_sort_key(order: FulfillmentOrder) -> tuple[int, str]:
    """Group by product-type rank (first product), then oldest placed first."""
    primary = order.products[0].product_type if order.products else (order.type_summary or "Other")
    placed = order.placed_at.isoformat() if order.placed_at else ""
    return (type_rank(primary), placed)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/core/test_fulfillment.py -q`
Expected: PASS (all old + 6 new). NOTE: the adapter/service don't set the new fields yet — that's later tasks; the full suite stays green because the new fields have defaults.

- [ ] **Step 5: Commit**

```bash
git add src/lbb/core/fulfillment.py tests/unit/core/test_fulfillment.py
git commit -m "feat(core): order metadata fields, coin_count, sides_summary helper"
```

---

### Task 2: Adapter — parse the new order/product fields

**Files:**
- Modify: `src/lbb/adapters/engraving_api.py`
- Test: `tests/unit/adapters/test_engraving_api.py`

- [ ] **Step 1: Append failing tests** to `tests/unit/adapters/test_engraving_api.py`:

```python
def test_parse_captures_order_metadata():
    raw = json.loads(json.dumps(ORDER))
    raw["link_to_graphic"] = "https://graphic/x"
    raw["product_picture_path"] = "product_picture/order.png"
    raw["product_type"] = "bracelet"
    raw["color"] = "Gold"
    t = FakeTransport([raw])
    [o] = _client(t).list_orders()
    assert o.link_to_graphic == "https://graphic/x"
    assert o.order_picture_key == "product_picture/order.png"
    assert o.type_summary == "Bracelet"
    assert o.color_summary == "Gold"
    assert o.created_at is not None and o.updated_at is not None


def test_parse_tolerates_missing_metadata():
    raw = json.loads(json.dumps(ORDER))
    for k in ("link_to_graphic", "product_picture_path", "product_type", "color"):
        raw.pop(k, None)
    t = FakeTransport([raw])
    [o] = _client(t).list_orders()
    assert o.link_to_graphic == "" and o.order_picture_key == ""
    assert o.type_summary == "" and o.color_summary == ""


def test_parse_sets_coin_count():
    raw = json.loads(json.dumps(ORDER))
    raw["products"][0]["coins"] = [{"front": "f1", "back": "b1"}, {"front": "f2", "back": "b2"}]
    t = FakeTransport([raw])
    [o] = _client(t).list_orders()
    assert o.products[0].coin_count == 2
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/adapters/test_engraving_api.py -q`
Expected: FAIL (new attrs not set).

- [ ] **Step 3: Edit `src/lbb/adapters/engraving_api.py`**

In `_parse_order`, extend the constructor call:

```python
def _parse_order(raw: dict) -> FulfillmentOrder:
    products = tuple(_parse_product(p) for p in (raw.get("products") or []))
    return FulfillmentOrder(
        order_id=str(raw["id"]),
        order_number=str(raw.get("order_number", "")),
        products=products,
        amount=int(raw.get("amount") or 0),
        status=_parse_status(raw.get("status")),
        instruction=str(raw.get("comment") or ""),
        amazon_url=str(raw.get("link_to_order") or ""),
        label_key=str(raw.get("shipping_label_path") or ""),
        placed_at=_parse_date(raw.get("order_date")),
        link_to_graphic=str(raw.get("link_to_graphic") or ""),
        created_at=_parse_date(raw.get("created_at")),
        updated_at=_parse_date(raw.get("updated_at")),
        order_picture_key=str(raw.get("product_picture_path") or ""),
        type_summary=normalize_type(str(raw["product_type"])) if raw.get("product_type") else "",
        color_summary=str(raw.get("color") or ""),
    )
```

In `_parse_product`, set `coin_count=len(coins)`:

```python
    return Product(
        product_type=normalize_type(str(raw.get("type") or "")),
        band_color=str(raw.get("color_band_chain") or ""),
        coin_color=str(raw.get("color_coin_plate") or ""),
        sides=tuple(sides),
        coin_count=len(coins),
        image_key=str(raw.get("image") or ""),
        multiple_coins=bool(raw.get("multiple_coins")),
        special_length=bool(raw.get("special_length")),
        length=str(raw.get("length") or ""),
    )
```

Note: `_parse_date` already exists and handles ISO-8601 with offset/microseconds (it calls `datetime.fromisoformat`).

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/adapters/test_engraving_api.py -q`
Expected: PASS (all old + 3 new).

- [ ] **Step 5: Commit**

```bash
git add src/lbb/adapters/engraving_api.py tests/unit/adapters/test_engraving_api.py
git commit -m "feat(adapter): parse order metadata + product coin_count"
```

---

### Task 3: Service — `product_image` (base64 data URI)

**Files:**
- Modify: `src/lbb/app/fulfillment_service.py`
- Test: `tests/integration/test_fulfillment_service.py`

- [ ] **Step 1: Append a failing test** to `tests/integration/test_fulfillment_service.py`:

```python
def _order_with_image():
    return FulfillmentOrder(
        order_id="uuid-img", order_number="306-IMG", amount=1,
        products=(Product(product_type="Necklace", coin_color="Silver",
                          image_key="product_picture/ref.png",
                          sides=(Side("Front", "engraving/f.pdf"),)),),
    )


def test_product_image_returns_data_uri(tmp_path):
    gw = FakeGateway([_order_with_image()])
    svc = FulfillmentService(gateway=gw, state=MemState(),
                             lightburn=FakeLightBurn(), cache_dir=tmp_path)
    res = svc.product_image("306-IMG", 0)
    assert res["ok"] is True
    assert res["data_uri"].startswith("data:image/png;base64,")
    assert gw.downloads == [("uuid-img", "product_picture/ref.png")]


def test_product_image_no_image_key(tmp_path):
    # default _order() product has no image_key
    gw = FakeGateway([_order()])
    svc = FulfillmentService(gateway=gw, state=MemState(),
                             lightburn=FakeLightBurn(), cache_dir=tmp_path)
    assert svc.product_image("306-1", 0)["ok"] is False


def test_product_image_unknown_product(tmp_path):
    gw = FakeGateway([_order_with_image()])
    svc = FulfillmentService(gateway=gw, state=MemState(),
                             lightburn=FakeLightBurn(), cache_dir=tmp_path)
    assert svc.product_image("306-IMG", 9)["ok"] is False
```

(`Product`, `Side`, `FulfillmentOrder` are already imported at the top of this test file from Task 6 of the prior plan; if not, add `from lbb.core.fulfillment import FulfillmentOrder, OrderStatus, Product, Side`.)

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/integration/test_fulfillment_service.py -q`
Expected: FAIL (`product_image` not defined).

- [ ] **Step 3: Edit `src/lbb/app/fulfillment_service.py`**

Add `import base64` at the top (with the other stdlib imports), and a MIME map near the top-level constants:

```python
import base64
```

```python
_IMAGE_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".webp": "image/webp", ".gif": "image/gif"}
```

Add the method to `FulfillmentService` (in the commands/queries area):

```python
    def product_image(self, order_number: str, product_index: int) -> dict:
        o = self.gateway.get(order_number)
        if o is None:
            return {"ok": False, "error": "Order not found"}
        try:
            p = o.products[int(product_index)]
        except (IndexError, ValueError, TypeError):
            return {"ok": False, "error": "Unknown product"}
        if not p.image_key:
            return {"ok": False}
        try:
            path = self.gateway.download_file(o.order_id, p.image_key, self._dir(o))
        except EngravingApiError as e:
            return {"ok": False, "error": str(e)}
        mime = _IMAGE_MIME.get(Path(p.image_key).suffix.lower(), "application/octet-stream")
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        return {"ok": True, "data_uri": f"data:{mime};base64,{b64}"}
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/integration/test_fulfillment_service.py -q`
Expected: PASS (all old + 3 new).

- [ ] **Step 5: Commit**

```bash
git add src/lbb/app/fulfillment_service.py tests/integration/test_fulfillment_service.py
git commit -m "feat(service): product_image returns base64 data URI"
```

---

### Task 4: Service — enrich `get_order` view-model

**Files:**
- Modify: `src/lbb/app/fulfillment_service.py`
- Test: `tests/integration/test_fulfillment_service.py`

- [ ] **Step 1: Append a failing test** to `tests/integration/test_fulfillment_service.py`:

```python
from datetime import datetime as _dt


def test_get_order_includes_metadata_and_sides_summary(tmp_path):
    o = FulfillmentOrder(
        order_id="uuid-m", order_number="306-M", amount=2,
        instruction="With Gift Box", amazon_url="https://sc/m",
        label_key="shipping_label/the-label.pdf",
        link_to_graphic="https://graphic/m",
        created_at=_dt(2026, 6, 16), updated_at=_dt(2026, 6, 22),
        type_summary="Necklace", color_summary="Silver",
        products=(Product(product_type="Necklace", band_color="Retro",
                          coin_color="Silver", multiple_coins=True,
                          special_length=True, length="50cm", coin_count=2,
                          image_key="product_picture/ref.png",
                          sides=(Side("Coin 1 Front", "a"), Side("Coin 1 Back", "b"),
                                 Side("Coin 2 Front", "c"), Side("Coin 2 Back", "d"))),),
    )
    gw = FakeGateway([o])
    svc = FulfillmentService(gateway=gw, state=MemState(),
                             lightburn=FakeLightBurn(), cache_dir=tmp_path)
    d = svc.get_order("306-M")
    assert d["link_to_graphic"] == "https://graphic/m"
    assert d["created_label"] and d["updated_label"]
    assert d["type_summary"] == "Necklace" and d["color_summary"] == "Silver"
    assert d["label_name"] == "the-label.pdf"
    p = d["products"][0]
    assert p["band_color"] == "Retro"
    assert p["multiple_coins"] is True
    assert p["special_length"] is True and p["length"] == "50cm"
    assert p["sides_summary"] == "2 coins · Front & Back each — 4 jobs"
    assert p["has_image"] is True
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/integration/test_fulfillment_service.py -q`
Expected: FAIL (KeyError on the new keys).

- [ ] **Step 3: Edit `src/lbb/app/fulfillment_service.py`**

Add a date-label helper next to `_placed_label`:

```python
def _date_label(dt) -> str:
    return f"{dt:%b} {dt.day}, {dt:%Y}" if dt else ""
```

Import `sides_summary` from core:

```python
from lbb.core.fulfillment import (
    FulfillmentOrder,
    OrderStatus,
    all_sides,
    queue_sort_key,
    sides_summary,
)
```

In `get_order`, extend the returned dict. Add these order-level keys (alongside the existing ones):

```python
            "link_to_graphic": o.link_to_graphic,
            "created_label": _date_label(o.created_at),
            "updated_label": _date_label(o.updated_at),
            "type_summary": o.type_summary,
            "color_summary": o.color_summary,
            "has_order_picture": bool(o.order_picture_key),
            "label_name": Path(o.label_key).name if o.label_key else "",
```

And extend each product dict in the `"products": [...]` comprehension to include:

```python
                    "band_color": p.band_color,
                    "multiple_coins": p.multiple_coins,
                    "special_length": p.special_length,
                    "length": p.length,
                    "coin_count": p.coin_count,
                    "sides_summary": sides_summary(p),
                    "has_image": bool(p.image_key),
```

(Keep the existing product keys — `product_type`, `name`, `color`, `qty`, `image_key`, `sides` — as they are.)

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/integration/test_fulfillment_service.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lbb/app/fulfillment_service.py tests/integration/test_fulfillment_service.py
git commit -m "feat(service): enrich get_order with metadata, sides_summary, label name"
```

---

### Task 5: Bridge — `product_image` passthrough

**Files:**
- Modify: `src/lbb/web/bridge.py`
- Test: `tests/web/test_bridge.py`

- [ ] **Step 1: Extend the fake + add a test** in `tests/web/test_bridge.py`:

In `FakeService`, add:

```python
    def product_image(self, n, idx):
        self.calls.append(("image", n, idx))
        return {"ok": True, "data_uri": "data:image/png;base64,AAA"}
```

Add a test:

```python
def test_bridge_product_image():
    svc = FakeService()
    b = JsApiBridge(svc)
    assert b.product_image("306-1", 0) == {"ok": True, "data_uri": "data:image/png;base64,AAA"}
    assert ("image", "306-1", 0) in svc.calls
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/web/test_bridge.py -q`
Expected: FAIL (`product_image` not on bridge).

- [ ] **Step 3: Edit `src/lbb/web/bridge.py`** — add to the queries section:

```python
    def product_image(self, order_number, product_index):
        return self._svc.product_image(order_number, product_index)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/web/test_bridge.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lbb/web/bridge.py tests/web/test_bridge.py
git commit -m "feat(web): bridge product_image passthrough"
```

---

### Task 6: Front-end — real product photo with icon fallback

**Files:**
- Modify: `src/lbb/web/assets/index.html`
- Modify: `src/lbb/web/assets/app.js`
- Modify: `src/lbb/web/assets/bridge-client.js`
- Modify: `src/lbb/web/assets/app.css`

Read each file fully first. No unit tests (static assets) — verify with `node --check`.

- [ ] **Step 1: `bridge-client.js` — expose `productImage`**

Add to the real API wrapper a `productImage: wrap("product_image")` entry, and to the browser MOCK a `product_image: () => ({ ok: false })`. (Match the file's existing `wrap(...)`/mock style; read it first.)

- [ ] **Step 2: `app.js` — render icon immediately, async-load the photo**

In `renderOrder`, find the block that builds `#productVisual` (it calls `productSVG(p.product_type, p.color)` and sets `vis.innerHTML = svgHtml + '<div class="sidechips">…'`). Replace that block so the SVG is wrapped in a `.prod-icon` and an `<img class="prod-photo">` is added (hidden until load), then trigger the async loader:

```js
  const vis=document.getElementById('productVisual');
  const imgClass = p.color==='Silver' ? 'silver' : '';
  vis.className='product '+(imgClass||'');
  const svgHtml = productSVG(p.product_type, p.color);
  const chips='<div class="sidechips">'+p.sides.map(s=>'<span class="schip'+(s.engraved?' done':'')+'">'+(s.engraved?'<svg class="sd" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M20 6L9 17l-5-5"/></svg>':'<svg class="sd" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/></svg>')+s.name+'</span>').join('')+'</div>';
  vis.innerHTML='<div class="prod-icon">'+svgHtml+'</div><img class="prod-photo" id="prodPhoto" alt="Product reference" hidden>'+chips;
  if(p.has_image){ loadProductPhoto(O.order_number, active); }
```

Add the loader function (top-level, near `openOrder`):

```js
async function loadProductPhoto(orderNumber, idx){
  let res;
  try { res = await API.productImage(orderNumber, idx); }
  catch(e){ return; }                    // keep the icon on any failure
  // ignore if the operator moved to another product/order while loading
  if(!CURRENT || CURRENT.order_number!==orderNumber || active!==idx) return;
  if(res && res.ok && res.data_uri){
    const img=document.getElementById('prodPhoto');
    if(img){
      img.onload=function(){ img.hidden=false; const ic=document.querySelector('#productVisual .prod-icon'); if(ic) ic.style.display='none'; };
      img.src=res.data_uri;
    }
  }
}
```

- [ ] **Step 3: `app.css` — photo styles**

Append:

```css
.product{position:relative}
.prod-photo{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;border-radius:14px;background:#fff;display:block}
.prod-photo[hidden]{display:none}
#productVisual .prod-icon{width:100%;height:100%;display:flex;align-items:center;justify-content:center}
```

- [ ] **Step 4: Verify**

Run: `node --check src/lbb/web/assets/app.js && node --check src/lbb/web/assets/bridge-client.js`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add src/lbb/web/assets/app.js src/lbb/web/assets/bridge-client.js src/lbb/web/assets/app.css src/lbb/web/assets/index.html
git commit -m "feat(web): show real product reference photo with icon fallback"
```

---

### Task 7: Front-end — truthful Engrave→Ship status strip

**Files:**
- Modify: `src/lbb/web/assets/index.html`
- Modify: `src/lbb/web/assets/app.js`
- Modify: `src/lbb/web/assets/app.css`

- [ ] **Step 1: `index.html` — replace the stepper markup**

Find the `<div class="stepper">…</div>` block (it contains `step done`, `Received`, `recSub`, `stepEng`, `bar1`, `stepShip`, `bar2`). Replace the WHOLE block with:

```html
    <div class="flow" id="flow">
      <div class="stage" id="stageEng"><span class="sdot"></span><span class="stxt"><span class="slbl">Engrave</span><span class="ssub" id="engSub">Pending</span></span></div>
      <span class="sbar"><i id="flowBar"></i></span>
      <div class="stage" id="stageShip"><span class="sdot"></span><span class="stxt"><span class="slbl">Ship</span><span class="ssub" id="shipSub">Pending</span></span></div>
      <div class="flow-rev" id="flowRev" hidden><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>Needs review — flagged for revision</div>
    </div>
```

- [ ] **Step 2: `app.js` — rebuild the stepper logic**

In `renderOrder`, find the block that manipulates `stepEng`/`stepShip`/`bar1`/`bar2`/`recSub` (the old stepper update). Replace that whole block with:

```js
  const stageEng=document.getElementById('stageEng'), stageShip=document.getElementById('stageShip');
  const flowBar=document.getElementById('flowBar'), flowRev=document.getElementById('flowRev'), flowEl=document.getElementById('flow');
  const done=doneOf(O), tot=totOf(O);
  const isShipped=O.status==='graviert_verschickt';
  const isRevision=O.status==='revision';
  const isAllEng=allEng(O);
  stageEng.classList.remove('done','active'); stageShip.classList.remove('done','active');
  flowRev.hidden=!isRevision; flowEl.classList.toggle('revision', isRevision);
  document.getElementById('engSub').textContent = isShipped||isAllEng ? 'Done' : done+'/'+Math.max(tot,0);
  if(isShipped){
    stageEng.classList.add('done'); stageShip.classList.add('done');
    flowBar.style.width='100%'; document.getElementById('shipSub').textContent='Done';
  } else if(isAllEng){
    stageEng.classList.add('done'); stageShip.classList.add('active');
    flowBar.style.width='50%'; document.getElementById('shipSub').textContent='Ready';
  } else {
    stageEng.classList.add('active');
    flowBar.style.width='0%'; document.getElementById('shipSub').textContent='Pending';
  }
```

Note: this block must run AFTER `const done`/`tot` are otherwise used; ensure no duplicate `const done`/`tot` declaration remains from the old block (remove the old `const done=doneOf(O), tot=totOf(O);` if it lived in the removed block; keep exactly one).

ALSO: near the top of `renderOrder` there is a separate line
`document.getElementById('recSub').textContent=O.placed_label||'';` that targets
the now-removed `Received` sub-label. DELETE that line (the order date is already
shown via `recSub`'s replacement and the `orderKv` "Order date" row). After this,
no `recSub` reference must remain in `app.js`.

- [ ] **Step 3: `app.css` — flow strip styles**

Append:

```css
.flow{display:flex;align-items:center;gap:14px;margin:18px 0 6px;padding:14px 18px;background:#fff;border:1px solid var(--line,#ece6da);border-radius:16px}
.flow .stage{display:flex;align-items:center;gap:10px;color:var(--ink-faint,#9a948a)}
.flow .stage .sdot{width:12px;height:12px;border-radius:50%;background:#d8d2c6;flex:none}
.flow .stage.active{color:var(--ink,#2a2620)}
.flow .stage.active .sdot{background:#c79a3f}
.flow .stage.done{color:#2e9e5b}
.flow .stage.done .sdot{background:#2e9e5b}
.flow .stxt{display:flex;flex-direction:column;line-height:1.1}
.flow .stxt .slbl{font-weight:600}
.flow .stxt .ssub{font-size:12px;color:var(--ink-faint,#9a948a)}
.flow .sbar{flex:1;height:4px;border-radius:3px;background:#ece6da;overflow:hidden}
.flow .sbar i{display:block;height:100%;background:#2e9e5b;width:0;transition:width .3s}
.flow.revision{border-color:#e6b877;background:#fff7ec}
.flow-rev{display:flex;align-items:center;gap:8px;color:#a85b00;font-weight:600;font-size:13px;margin-left:auto}
.flow-rev svg{width:16px;height:16px}
```

- [ ] **Step 4: Verify**

Run: `node --check src/lbb/web/assets/app.js`
Expected: exit 0. Also grep to confirm no remaining references to removed ids (`bar1`, `bar2`, `recSub`, `stepEng`, `stepShip`) in `app.js`:
Run: `grep -nE "bar1|bar2|recSub|stepEng|stepShip" src/lbb/web/assets/app.js` → expect no matches.

- [ ] **Step 5: Commit**

```bash
git add src/lbb/web/assets/index.html src/lbb/web/assets/app.js src/lbb/web/assets/app.css
git commit -m "feat(web): truthful Engrave->Ship status strip with revision state"
```

---

### Task 8: Front-end — surface fields + remove static cruft

**Files:**
- Modify: `src/lbb/web/assets/app.js`
- Modify: `src/lbb/web/assets/index.html`

- [ ] **Step 1: `app.js` — richer product details (`prodKv`)**

Find the `document.getElementById('prodKv').innerHTML = …` assignment in `renderOrder`. Replace its value with one that uses the real fields and `sides_summary`:

```js
  const colorClass = p.color==='Silver' ? 'badge silver' : 'badge';
  document.getElementById('prodSubh').innerHTML='Product '+(active+1)+' of '+O.products.length+' <span class="c">'+p.product_type+'</span>';
  document.getElementById('prodKv').innerHTML=
    '<div class="k">Product type</div><div class="v"><span class="badge">'+p.product_type+'</span></div>'
   +'<div class="k">Coin / plate color</div><div class="v"><span class="'+colorClass+'">'+(p.color||'—')+'</span></div>'
   +(p.band_color?'<div class="k">Chain / band color</div><div class="v"><span class="badge">'+p.band_color+'</span></div>':'')
   +(p.multiple_coins||(p.coin_count>1)?'<div class="k">Coins</div><div class="v">'+(p.coin_count||2)+' coins</div>':'')
   +(p.special_length?'<div class="k">Special length</div><div class="v">'+(p.length?p.length:'Yes')+'</div>':'')
   +'<div class="k">Engraving</div><div class="v">'+(p.sides_summary||'')+'</div>';
```

Also update the engraving-tasks subheader count line if it referenced the old hardcoded "Front & Back" anywhere — it uses `#sideC` already (keep it).

- [ ] **Step 2: `app.js` — richer order details (`orderKv`) + real label name**

Find the `document.getElementById('orderKv').innerHTML = …` assignment. Replace with one that adds Received / Last updated / Graphic link (each only when present) and keeps the existing rows:

```js
  document.getElementById('orderKv').innerHTML=
    '<div class="k">Order no.</div><div class="v mono">'+O.order_number+'</div>'
   +'<div class="k">Order date</div><div class="v">'+(O.placed_label||'')+'</div>'
   +(O.created_label?'<div class="k">Received</div><div class="v">'+O.created_label+'</div>':'')
   +(O.updated_label?'<div class="k">Last updated</div><div class="v">'+O.updated_label+'</div>':'')
   +'<div class="k">Link to Order</div><div class="v">'+(hasAmazon?'<a href="#" onclick="API.openAmazon(CURRENT.amazon_url);return false;">Open on Amazon ↗</a>':'<span style="color:var(--ink-faint)">—</span>')+'</div>'
   +(O.link_to_graphic?'<div class="k">Graphic</div><div class="v"><a href="#" onclick="API.openAmazon(CURRENT.link_to_graphic);return false;">Open graphic ↗</a></div>':'')
   +'<div class="k">Gift box</div><div class="v">'+(O.gift_box?'<span class="badge gift">'+GIFT_SVG+' With gift box</span>':'<span style="color:var(--ink-faint)">No</span>')+'</div>'
   +'<div class="k">Items</div><div class="v">'+(O.amount||O.products.length)+'</div>';
```

In the label block, set the real filename. Find the lines setting `labelCarrier`/`labelFile` and make `labelFile` use `O.label_name`:

```js
  document.getElementById('labelCarrier').textContent = O.has_label ? 'Shipping label' : '—';
  document.getElementById('labelFile').textContent = O.has_label ? (O.label_name || 'label.pdf') : '(no label file)';
```

- [ ] **Step 2b: `app.js` — fix the engraving-tasks count header**

Confirm the `#sideC` text reflects real progress; if a line sets it from `p.sides`, keep `p.sides.filter(s=>s.engraved).length+' / '+p.sides.length+' done'`. No hardcoded "Front & Back" should remain — grep:
Run: `grep -n "Front & Back\|Front only\|Front &amp; Back" src/lbb/web/assets/app.js` → expect no matches (the only such strings now come from the backend `sides_summary`).

- [ ] **Step 3: `index.html` — remove static cruft**

Make these edits:
- Delete the dead Share button: the `<button class="btn ghost" onclick="copyOrder()">…Share</button>` in the order topbar (the second one; keep the copy button next to the order number heading). Search for `>Share<` and remove that whole `<button…>…</button>`.
- Remove the `<span class="right tag">product</span>` in the product card header (line with `id="prodCardTitle"`).
- Remove the `<span class="right tag">one per shipment</span>` in the shipping-label card header.
- Remove both `<div class="dev-note">…</div>` blocks.
- Change the dashboard operator label `A. Fink · Operator` (in the `.topbar`) to just `Operator`.

Keep every element id the JS references (`prodCardTitle`, `labelCarrier`, `labelFile`, etc.).

- [ ] **Step 4: Verify**

Run: `node --check src/lbb/web/assets/app.js`
Expected: exit 0.
Run: `grep -nE ">Share<|right tag|dev-note|A\. Fink" src/lbb/web/assets/index.html` → expect no matches.

- [ ] **Step 5: Commit**

```bash
git add src/lbb/web/assets/app.js src/lbb/web/assets/index.html
git commit -m "feat(web): surface chain color/coins/special-length/metadata, real label name; remove prototype cruft"
```

---

### Task 9: Full verification + live smoke (controller-run)

- [ ] **Step 1: Whole suite + contracts + lint**

```
uv run pytest -q          # expect all pass + 4 skipped
uv run lint-imports       # 2 contracts kept
uv run ruff check src tests
node --check src/lbb/web/assets/app.js
node --check src/lbb/web/assets/bridge-client.js
```

- [ ] **Step 2: Live GUI smoke** (`uv run python -m lbb`)

Confirm against live orders: the real **product photo** loads (icon shows first, then swaps); the **Engrave→Ship** strip is truthful; **chain color / coins / special length / Received / Last updated** appear when present; the **Share button / DEV notes / "product" & "one per shipment" tags** are gone; the label shows its real filename. If a photo fails or a field looks wrong, debug it (systematic-debugging) against the live payload before finishing.

- [ ] **Step 3: Rebuild the branded bundle**

```
uv run pyinstaller packaging/lbb.spec --clean --noconfirm
```
Expected: `dist/Fulfillment Studio/Fulfillment Studio.exe` rebuilt with the updated assets.

- [ ] **Step 4: Finish the branch**

Use `superpowers:finishing-a-development-branch` to merge `feature/fulfillment-studio` or open a PR.

---

## Notes for the executor

- No secret handling changes here; the API key stays in `~/.flanacom-tool/config.json`.
- No new dependency — `base64` and `Path` are stdlib.
- Windows date formatting uses `.day` (never `%-d`).
- Front-end tasks have no unit tests; rely on `node --check` + the grep guards + the live smoke. Read each asset fully before editing; match existing string style.
- `import-linter`: `core/` imports only stdlib + `lbb.core`. The service importing `base64` is fine; nothing new crosses a boundary.
