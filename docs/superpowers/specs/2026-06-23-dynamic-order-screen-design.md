# Dynamic, API-driven Order Screen — Design

**Date:** 2026-06-23
**Status:** Approved (design), pending implementation
**Builds on:** `2026-06-22-live-engraving-api-design.md` (the live API integration).

## Problem

The order screen still carries static scaffolding from the original HTML
prototype that does not reflect Hauke's live API: a hand-drawn fake product
shape, a "Received → Engraved → Shipped" stepper whose first step is always
ticked and whose numbers are decorative, a hardcoded "Front & Back" sides line,
a dead "Share" button, developer-only notes, and a hardcoded operator name.
Meanwhile several fields Hauke deliberately exposes in the API are ignored. The
goal: make the screen fully data-driven, surface everything meaningful the API
provides, and make the UX match the real engraving workflow.

## Ground truth (from the live API, 2026-06-23)

Order-level keys actually returned (superset of the emailed example):
`id, order_number, link_to_order, order_date, amount, status, comment,
shipping_label_path, product_picture_path, link_to_graphic, created_at,
updated_at, product_type, color, products, signed_urls`.

Notes from real data:
- `product_type` and `color` ALSO exist at the order level (a summary Hauke
  added; useful as a fallback when `products` is empty, e.g. order `#Test-1123`).
- `link_to_graphic` and `product_picture_path` are currently `null` but are part
  of the schema → capture and show only when present.
- `created_at` / `updated_at` are ISO-8601 with microseconds + offset.
- Each product has a real `image` (e.g. `product_picture/…Screenshot….png`) and
  a matching key in `signed_urls` → the real reference photo is downloadable.

## Decisions

1. **Real product reference photo**, with a type-icon fallback. Served to the
   webview as a base64 `data:` URI (avoids file-path/escaping issues), downloaded
   on demand via the existing gateway and swapped in asynchronously.
2. **Truthful status flow:** a two-stage **Engrave → Ship** indicator driven by
   live progress + the real status; a distinct **"Needs review"** state for
   `revision`. No invented "Received" step.
3. **Surface everything meaningful Hauke exposes**, hiding fields that come back
   empty.
4. **Remove static cruft** (Share button, decorative tags, DEV notes, hardcoded
   operator name, static "label.pdf").

## Changes

### Domain (`core/fulfillment.py`, stays pure)

Add to `FulfillmentOrder` (all optional, default empty):
- `link_to_graphic: str = ""`
- `created_at: datetime | None = None`
- `updated_at: datetime | None = None`
- `order_picture_key: str = ""`   (order-level `product_picture_path`)
- `type_summary: str = ""`        (order-level `product_type`, normalized)
- `color_summary: str = ""`       (order-level `color`)

Add a pure helper `sides_summary(product) -> str` producing an accurate human
breakdown, e.g. `"2 coins · Front & Back each — 4 jobs"`, `"1 coin · Front & Back"`,
`"Front only"`. `queue_sort_key`/bucket logic falls back to `type_summary` when
`products` is empty.

### Adapter (`adapters/engraving_api.py`)

`_parse_order` captures the new order fields (`link_to_graphic`,
`product_picture_path` → `order_picture_key`, `created_at`, `updated_at`,
`product_type` → normalized `type_summary`, `color` → `color_summary`).
No change to signed-URL handling — the product `image` key already resolves
through `download_file`.

### Service (`app/fulfillment_service.py`)

New: `product_image(order_number, product_index) -> dict`. Resolves the product's
`image_key`; if absent → `{"ok": False}`. Else `download_file` it, read bytes,
base64-encode, infer MIME from the extension (`.png`→`image/png`,
`.jpg`/`.jpeg`→`image/jpeg`, `.webp`→`image/webp`, default `application/octet-stream`),
return `{"ok": True, "data_uri": "data:<mime>;base64,<...>"}`. Errors
(`EngravingApiError`) → `{"ok": False, "error": str(e)}`.

`get_order` view-model gains: `link_to_graphic`, `created_label` (created_at as
`%b %d, %Y`), `updated_label`, `type_summary`, `color_summary`, `has_order_picture`,
and per product: `band_color`, `multiple_coins`, `special_length`, `length`,
`sides_summary` (from the pure helper), plus `has_image` (bool `image_key`).
`label_file` reports the real label filename (basename of `label_key`) via a new
`label_name(order_number)` (or include it in `get_order`).

### Bridge (`web/bridge.py`)

Add `product_image(order_number, product_index)` passthrough. No other change.

### Front-end (`web/assets/`)

`index.html`:
- Replace the 3-node stepper markup with a two-stage Engrave→Ship strip + a
  revision banner element.
- Add an `<img>` (hidden until loaded) inside the product visual; keep an icon
  container for the fallback.
- Remove the dead Share button, the `product` and `one per shipment` tags, both
  `.dev-note` blocks. Change "A. Fink · Operator" to "Operator".

`app.js`:
- `renderOrder`: render the fallback type-icon immediately, then call
  `API.productImage(order_number, active)`; on `{ok}` set the `<img>` src to the
  `data_uri` and reveal it (icon stays as the load/placeholder + fallback).
- Rebuild the stepper logic against the real status/progress + revision.
- `prodKv`: render chain color, coin color, multiple-coins badge, special length
  (+ value), and `sides_summary` instead of the hardcoded "Front & Back".
- `orderKv`: add Received (`created_label`), Last updated (`updated_label`),
  Graphic link (`link_to_graphic`) — each only when present.
- Label row shows the real filename.
- Keep `bridge-client.js` browser-mock coherent: add `productImage` →
  `{ok:false}` in the mock so the page still loads outside pywebview.

`app.css`: styles for the photo (object-fit, rounded, fixed aspect box), the
two-stage strip, the revision "Needs review" state, and the multiple-coins /
special-length badges.

## Error handling

- Image download failure / no image → fall back to the type icon silently (no
  scary error; engraving still works).
- Empty optional fields (`link_to_graphic`, `product_picture_path`, etc.) → the
  row is not rendered at all (no "—" clutter beyond what's meaningful).
- All existing API error handling (401/network/expired URL) is unchanged.

## Testing

TDD, no network in unit tests:
1. `sides_summary` pure helper (single coin one/two sides; multiple coins).
2. Parser captures the new order fields (and tolerates nulls).
3. `product_image`: returns a correct `data:` URI from fake-gateway bytes;
   `{ok:False}` when no image_key; error path.
4. `get_order` includes the new fields + `sides_summary` + real label name.
5. `node --check` for the JS; manual GUI verification against live orders
   (real photos load, stepper truthful, fields show, cruft gone) — and a
   systematic-debugging pass if any live photo/field misbehaves.

## Out of scope

- Editing any field other than status (API forbids it).
- Caching/preloading all product images up front (download on order-open is
  enough; the gateway already refreshes signed URLs).
- Reworking the dashboard list beyond the operator-label cleanup.
