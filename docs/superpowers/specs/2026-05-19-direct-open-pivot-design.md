# Direct-Open Pivot — design

**Date:** 2026-05-19
**Status:** Approved
**Driver:** Customer PDFs imported via the existing `build_lbrn2` pipeline lose
significant geometric detail. Iterative fixes (Bezier flattening, subpath
splitting, etc.) close some gaps but the path to LightBurn-native fidelity
would require rebuilding LightBurn's PDF importer end-to-end. The operator
verified that **LightBurn's native File → Import on a `.pdf` preserves the
design perfectly**.

## Goal

Stop generating `.lbrn2` files from the customer's geometry. Hand the PDF
directly to LightBurn and let its native importer handle parsing. Preserve
the app's value-add (SKU lookup + operator instructions) by adding an explicit
"layer setup" block on the preview screen.

## Architecture

```
DropZone.pdf_dropped
  → MainWindow._on_pdf_chosen
    → extract SKU (strict / lenient / picker fallback) — unchanged
    → repo.get(sku) → SkuProfile — unchanged
    → pdf.read_info() + run_preflight — unchanged
    → pdf.render_thumbnail_png — unchanged
    → JobPreviewView.populate (now also shows "Assign these layers:")
       on "Open in LightBurn →"
    → run_pipeline(Job, deps)
      → deps.lightburn.load_file(job.source_pdf)   ← was generated .lbrn2
      → return JobResult(ok=True, output_path=job.source_pdf)
```

Pipeline shrinks to roughly:

```python
def run_pipeline(job: Job, deps: PipelineDeps) -> JobResult:
    try:
        deps.lightburn.load_file(job.source_pdf)
    except LbbError as e:
        return JobResult(ok=False, error=str(e))
    return JobResult(
        ok=True,
        output_path=job.source_pdf,
        profile=job.profile,
        sku=job.profile.sku if job.profile else None,
    )
```

The `temp_dir` field on `PipelineDeps` becomes vestigial (kept for ABI
compatibility; nothing writes there in the production path).

## Preview screen — new instruction block

Between the existing metadata column and the preflight readout, add a section:

```
LAYER SETUP IN LIGHTBURN
After import, assign in LightBurn:
  • Black strokes  →  C00 (Cut)     1000 mm/min · 20%
  • Blue strokes   →  C01 (Engrave)   50 mm/sec · 15%

Material library:
  default.clb  →  LeatherVT
```

The cut-layer numbers (speed/power) come from the SKU's template; for MVP they
can be hard-coded based on the wallet template's C00/C01 entries because we
only ship one template family. A follow-up can read them dynamically from the
`.lbrn2` template (which already encodes C00/C01 settings via XML — see
`templates/wallet-small.lbrn2:39-104`).

The "Send to LightBurn →" button renames to "**Open in LightBurn →**" so
operator language matches the new behavior (we're handing the source file
over, not generating anything).

## Deprecated (kept in tree, not deleted)

These remain in `src/lbb/` as documentation of the path tried, but no longer
participate in the production flow:

- `core/template_builder.py` (`build_lbrn2`, Bezier flatten helpers, subpath
  parser)
- `adapters/pdfium_reader.py:extract_paths` (the geometry walker)
- `core/palette.py:layer_index_for_color` (color → layer routing)
- `templates/wallet-small.lbrn2`, `templates/wallet-tall.lbrn2` (cut-settings
  reference)

Their tests stay green so nothing rots, but they validate dead production code.
A follow-up task can delete cleanly once the demo lands.

## Tests

| Test | Status after pivot |
|---|---|
| `tests/integration/test_pipeline.py::test_happy_path_loads_to_lightburn` | UPDATE: assert `lightburn.loaded == [source_pdf]` and `result.output_path == source_pdf` |
| `tests/integration/test_pipeline.py::test_strokes_route_to_correct_cut_layer` | SKIP — geometry-routing is now LightBurn's job |
| `tests/integration/test_pipeline.py::test_pipeline_uses_explicit_profile_when_filename_has_no_sku` | UPDATE: assert source PDF is opened, not a generated file |
| `tests/integration/test_pipeline.py::test_unknown_sku_returns_error` | DELETE or rewrite — pipeline no longer resolves SKUs |
| `tests/integration/test_pipeline.py::test_filename_without_sku_returns_error` | DELETE — same |
| `tests/integration/test_pipeline.py::test_lightburn_not_running_returns_error` | UPDATE: assert source PDF wasn't loaded |
| `tests/unit/core/test_build_lbrn2.py::*` | KEEP (tests dead code, but math is correct) |
| NEW: `test_pipeline.py::test_run_pipeline_opens_source_pdf_directly` | Asserts the rewire works end-to-end |
| NEW: `test_job_preview.py::test_layer_setup_block_present` | Asserts the new instruction block renders |

## Trade-offs (explicit)

| | Before | After |
|---|---|---|
| Design fidelity | Broken | Perfect (LB's importer) |
| Cut layers | Auto-baked | Operator assigns manually |
| Material assignment | Auto via template ref | Operator picks from LB's library |
| Time to demo | Weeks | ~1 hour |
| App's role | Auto-everything | SKU lookup + setup reminders + dispatch |

## Non-goals

- Automated cut-layer assignment inside LightBurn (would require LB scripting
  support we don't have).
- Preserving the `.lbrn2` template as a separately-opened file (LightBurn opens
  each shell-invoked file in its own project window).
- Deletion of the deprecated `build_lbrn2` / `extract_paths` modules — keep for
  now, prune later.

## Estimated change footprint

- `src/lbb/app/pipeline.py`: ~20 LOC removed, ~5 added (net simpler)
- `src/lbb/ui/views/job_preview.py`: +~30 LOC for the instruction block
- `src/lbb/ui/main_window.py`: ~2 LOC tweak (button label change if hardcoded; ignore if signals)
- Test updates: ~5 files touched
- **Total ≈ -40 LOC net** (deletions in pipeline + small additions in preview)
