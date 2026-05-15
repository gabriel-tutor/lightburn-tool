# PDF Spec for Designers — LightBurn Bridge

> **Audience:** the graphic-design team producing engraving-ready PDFs.
> **Purpose:** if your PDF follows this spec, our tool will load it into the laser with the correct settings in one drag-and-drop. If it doesn't, the tool will block the job and tell the operator why. **No surprises at the laser.**

---

## TL;DR — the five rules

1. **Filename:** `<SKU>__<anything>.pdf` (note the **two** underscores)
2. **Vector only** — no embedded images, no raster effects, no JPEG/PNG placed art
3. **Stroke colors** must be one of the **30 LightBurn palette colors** (see table)
4. **Text** must be converted to outlines (no live text)
5. **One page**, at the canvas size your SKU expects (ask engineering)

If you can tick all five before exporting, the file will work.

---

## 1. Filename — the SKU contract

```
<SKU>__<descriptor>.pdf
```

Two underscores (`__`) separate the SKU from anything you want to add after it.

| ✅ Valid | ❌ Invalid | Why |
|---|---|---|
| `LB-WALLET-LEATHER-S__order-2381.pdf` | `LB-WALLET-LEATHER-S_order-2381.pdf` | Only one underscore — no SKU delimiter |
| `LB-TUMBLER-20OZ-SS__sarah.pdf` | `wallet-design.pdf` | No SKU at all |
| `LB-TAG__pet-name-fluffy.pdf` | `__order-2381.pdf` | SKU portion is empty |
| `LB-PLAQUE-WOOD-RECT__v3.pdf` | `LB WALLET LEATHER S__x.pdf` | Spaces in SKU (use dashes) |

The SKU itself can contain dashes and single underscores — only the **double underscore** is the delimiter. The tool strips file extension and folder path before reading.

---

## 2. Vector only — no rasters

LightBurn engraves vectors precisely. Raster images cause unpredictable results and our preflight will reject them.

| ✅ OK | ❌ Not OK |
|---|---|
| Paths drawn natively in Illustrator / Inkscape / Affinity | Placed JPEG / PNG / TIFF |
| Outlined type | Photoshop-flattened layers exported as PDF |
| Boolean unions/intersections of vector shapes | "Flatten to image" any effect |
| Strokes, fills, compound paths | Drop shadows, glows, blurs (rasterize on export) |

**Tip — Illustrator:** before exporting, run *Object → Flatten Transparency* with *Preserve Vector Output* unchecked? **No** — leave that option checked or skip flattening entirely. We want vectors preserved.

**Tip — Inkscape:** *File → Document Properties → Resize page to drawing*; then export with *Optimize: None*, no rasterization.

---

## 3. The 30-color palette — your only colors

LightBurn maps every unique stroke color to a numbered "cut layer" (00–29). The laser settings (speed, power, passes, air assist) are configured per-layer. **If you stray off-palette by one digit, the import will create a new ungoverned layer.**

Use **exactly** these hex values:

| # | Hex | Swatch | # | Hex | # | Hex |
|---|---|---|---|---|---|---|
| 00 | `#000000` | black | 10 | `#7D4000` | 20 | `#88BB45` |
| 01 | `#0000FF` | blue | 11 | `#509050` | 21 | `#8000A0` |
| 02 | `#FF0000` | red | 12 | `#1818A0` | 22 | `#404040` |
| 03 | `#00E000` | green | 13 | `#A03000` | 23 | `#707000` |
| 04 | `#D0D000` | yellow | 14 | `#A050A0` | 24 | `#700070` |
| 05 | `#FF8000` | orange | 15 | `#A0A050` | 25 | `#702070` |
| 06 | `#00E0E0` | cyan | 16 | `#505000` | 26 | `#702000` |
| 07 | `#FF00FF` | magenta | 17 | `#003030` | 27 | `#207020` |
| 08 | `#B4B4B4` | grey | 18 | `#A04030` | 28 | `#202070` |
| 09 | `#5050FF` | sky | 19 | `#7D6045` | 29 | `#702020` |

**How to set this up once in your design tool:**
- **Illustrator:** create a *Swatch Library* file `lightburn-30.ase` from these values. Save it to your team's shared swatches folder.
- **Inkscape:** save the 30 colors as a custom palette file `LightBurn-30.gpl` in `~/.config/inkscape/palettes/`. It then appears in the palette dropdown.
- **Affinity Designer:** create a *Document Palette* with all 30, lock it, and reuse across projects.

**Which color means what?** Your shop's laser engineer assigns operations (cut / engrave / score / pierce / etc.) to layers. Most shops follow:

- **`#000000` (black, layer 00)** → through-cut (vector cut)
- **`#0000FF` (blue, layer 01)** → engrave / scan fill
- **`#FF0000` (red, layer 02)** → score (light surface mark)

But this varies by shop and material. **Ask engineering for the active convention for your SKU before designing.**

---

## 4. Strokes vs fills — cut vs engrave

LightBurn treats strokes and fills differently:

| Your design has… | Becomes in LightBurn… |
|---|---|
| **Stroke** only (no fill) | Vector cut/score (laser follows the line) |
| **Fill** only (no stroke) | Raster scan (laser sweeps inside the shape) |
| **Both** stroke and fill, same color | Both operations on the same layer |
| **Both** different colors | Stroke wins — fill is ignored. **Avoid this.** |

**Rule of thumb:** for solid engraved logos or filled text, give the shape a **fill** in the engrave color and **no stroke**. For lines that should be cut/scored, give them a **stroke** in the cut color and **no fill**.

If a shape needs to be both engraved (filled) *and* outlined (cut around the perimeter), make it **two separate shapes stacked on top of each other**.

---

## 5. Text — outline before export

Live text in PDFs depends on font embedding, and font embedding depends on licensing, software version, and OS. None of these belong anywhere near a laser job. **Always outline.**

- **Illustrator:** select all → *Type → Create Outlines* (`⌘⇧O` / `Ctrl+Shift+O`)
- **Inkscape:** select all → *Path → Object to Path* (`Ctrl+Shift+C`)
- **Affinity Designer:** select all → *Layer → Convert to Curves* (`Ctrl+Enter`)

After outlining, the text is geometry — it'll never re-render differently.

**Hairlines:** stroke width doesn't affect the laser cut path (the laser follows the centerline), but very-thin strokes (< 0.25pt) can look invisible on screen. **Use ≥ 0.5pt strokes** so reviewers can see what they're approving.

---

## 6. Canvas size — match the SKU

Each SKU corresponds to a physical product with a fixed working area:

```
┌──────────────────────────────────────────────┐
│  SKU                       Canvas (mm)       │
├──────────────────────────────────────────────┤
│  LB-WALLET-LEATHER-S       95  ×  110        │
│  LB-WALLET-LEATHER-M      110  ×  140        │
│  LB-TUMBLER-20OZ-SS       220  ×   75        │
│  LB-TAG-PET-WOOD-R         50  ×   50        │
│  LB-PLAQUE-WOOD-RECT      200  ×  150        │
│  …                                           │
└──────────────────────────────────────────────┘
```

Set your **document size** to the canvas dimensions, not larger. Our preflight rejects designs that exceed the canvas.

**Bleed?** No. The laser respects the canvas as the hard physical edge of the working area. Stay inside.

**Origin?** Top-left of the document corresponds to top-left of the laser bed (matches LightBurn's default user origin). Place artwork relative to that.

Engineering keeps the master list of SKU → canvas size; ask if you don't see your SKU above.

---

## 7. Things that quietly break exports

These are the most common scrap-producing pitfalls:

| Don't | Because |
|---|---|
| **Opacity / transparency** on cut paths | LightBurn ignores opacity on cut layers; result looks correct on screen, prints wrong |
| **Gradient fills** | Becomes a raster band — slow, ugly, not what designer intended |
| **Drop shadows / blurs** | Forces rasterization on export; preflight rejects the file |
| **Clipping masks** | LightBurn's PDF import sometimes drops shapes outside the mask. Flatten masks before export. |
| **Linked images (placed not embedded)** | If they're not embedded, they may vanish on import. Better: don't use raster at all (rule #2). |
| **CMYK color mode** | Convert to **RGB** before exporting. Palette is defined in RGB; CMYK values won't match exactly. |
| **Compound paths with mixed colors** | LightBurn treats compound paths as one color. Split them. |
| **Hidden / locked layers exported** | They get exported anyway. Delete them; don't just hide. |
| **Pattern fills** | Don't survive PDF round-trip. Expand to vectors first. |

---

## 8. Self-test before you send

A 60-second sanity check before handing the PDF to operations:

1. **Filename:** does it match `<SKU>__<anything>.pdf` with a double underscore?
2. **Open in LightBurn yourself** (if you have it installed): does each color land on the layer number you expected? (Layer panel, bottom of the window.)
3. **Pages:** is it exactly one page?
4. **Selection check:** in Illustrator, *Select → All*. Look at the appearance panel — any rasters? Any live text? Any layers you forgot to delete?
5. **Pixel preview:** in Illustrator, *View → Pixel Preview*. If anything looks fuzzy, you have a raster.
6. **Color sample:** pick a stroked path; check its hex in the color panel. Is it **exactly** one of the 30 values above? Even one digit off creates a phantom layer.
7. **Size:** does the document size match the SKU's canvas?

If all seven are ✅, send it.

---

## 9. When the operator rejects your file

The Bridge tool's preflight will block any file that fails the checks. Common rejection messages and what to fix:

| Message | What to do |
|---|---|
| `No SKU delimiter ('__') in filename` | Rename the file with `<SKU>__<name>.pdf` |
| `PDF contains raster content (must be vector-only)` | Find and remove the placed image / rasterized effect |
| `stroke colors not in LightBurn palette: #ABCDEF` | Re-color those strokes to the nearest of the 30 palette hex values |
| `design 200.0×200.0 mm exceeds canvas 95.0×110.0 mm` | Resize the artwork to fit the canvas |
| `expected 1 page, got 3` | Save only the relevant page as a new PDF |

Operations will paste the message into their ticket — you can usually fix and re-send within minutes.

---

## 10. Spec version

- **Version:** 1.0
- **Effective:** when LightBurn Bridge v0.1 ships
- **Owner:** engineering (`docs/designer-pdf-spec.md` in the lightburn-tool repo)
- **Changes:** any update gets a version bump and a note in the team channel before it takes effect

Questions, bugs, or *"can we add X to the spec?"* → file an issue against the lightburn-tool repo, or ask engineering directly. Conventions evolve; the spec follows.
