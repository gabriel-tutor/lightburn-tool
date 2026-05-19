# SKU fallback picker — design

**Date:** 2026-05-19
**Status:** Approved (option A of two presented)
**Driver:** Real customer PDFs are named by order ID (e.g.
`304-4865183-6105121.pdf`), not by SKU. Today the app rejects these at the
filename-extraction step. Goal: let the operator import any PDF and pick the
SKU manually when the filename doesn't carry it.

## Goal

Demo to the client that LightBurn Bridge accepts the PDFs their order system
already produces, while preserving the value-add (SKU drives the auto-applied
template, material, and cut/engrave layer settings inside LightBurn).

## Constraints

- **Backward compatible.** Filenames matching `<SKU>__<anything>.pdf` continue
  to work exactly as before; no extra clicks for the existing flow.
- **No regression on the polished preview screen.** That artifact is the
  demo's centerpiece; we don't redesign it.
- **Hexagonal boundaries respected.** UI → ports → adapters → core. Adapters
  do not leak through to UI.
- **Smallest practical surface area** — this is a demo enhancement, not a
  feature platform.

## Architecture

### Port (new method on existing protocol)

`src/lbb/ports/repository.py`

```python
class ProfileRepository(Protocol):
    # ...existing methods...
    def list_profiles(self) -> list[SkuProfile]: ...
```

### Adapter (implementation)

`src/lbb/adapters/sqlite_repo.py`

Implement `list_profiles()` by joining `sku_profiles` to `templates` and
`materials`, returning a list of fully-resolved `SkuProfile` objects sorted
by SKU code.

### UI — new dialog

`src/lbb/ui/dialogs/sku_picker.py` (new file)

A `QDialog` returning a chosen `SkuProfile` (or `None` on cancel):

```
+---------------------------------------------------+
| Couldn't detect a SKU from the filename           |
|                                                   |
| File: 304-4865183-6105121.pdf                     |
|                                                   |
| Pick the product:                                 |
|                                                   |
| [ LB-WALLET-LEATHER-S — Wallet — Small      ▾ ]   |
|                                                   |
|                       [ Cancel ]  [ Use SKU  → ]  |
+---------------------------------------------------+
```

ComboBox items: `f"{profile.sku.value} — {profile.template.name}"`.
Sorted by `profile.sku.value`.

If `repo.list_profiles()` returns `[]`: dialog opens with a disabled OK
button and an empty-state message ("No SKUs configured — add one in Admin
first.") so the operator gets a clear next step.

### Controller change

`src/lbb/ui/main_window.py` — `_on_pdf_chosen`

```python
def _on_pdf_chosen(self, path: Path) -> None:
    try:
        sku = extract_sku(path.name)
        profile = self.deps.repo.get(sku)
        if profile is None:
            QMessageBox.warning(self, "Unknown SKU",
                f"No profile mapped for {sku.value}.\n\nAdd one via Admin first.")
            return
    except LbbError:
        # Filename has no SKU section — let the operator pick.
        profile = self._prompt_for_sku(path)
        if profile is None:
            return  # cancelled
    # ...preflight / thumbnail / populate / navigate (unchanged)...
```

`_prompt_for_sku` opens `SkuPickerDialog`, returns the chosen `SkuProfile` or
`None`.

## Edge cases

| Situation | Behavior |
|---|---|
| Filename `<SKU>__order.pdf`, SKU registered | Existing flow, no picker. |
| Filename `<SKU>__order.pdf`, SKU **unknown** | Existing "Unknown SKU" warning. Do NOT fall through to picker. (Rationale: operator named the file with a SKU prefix; if it's wrong, they should fix it or add the SKU to Admin, not silently re-route to a different product.) |
| Filename with no `__` delimiter | Open picker. |
| Filename with empty SKU section (`__order.pdf`) | Open picker. |
| Picker opened, no SKUs in DB | Dialog shows empty-state message, OK disabled. |
| Picker cancelled | Return to home silently. |

## Testing (TDD)

1. **`tests/unit/adapters/test_sqlite_repo.py::test_list_profiles_returns_all_joined`** —
   adapter returns fully-resolved profiles sorted by SKU.
2. **`tests/unit/adapters/test_sqlite_repo.py::test_list_profiles_empty`** —
   empty DB returns `[]`, no error.
3. **`tests/ui/test_sku_picker_dialog.py::test_picker_returns_selected_profile`** —
   pytest-qt: opens dialog, selects item, asserts accepted result.
4. **`tests/ui/test_sku_picker_dialog.py::test_picker_returns_none_on_cancel`** —
   cancel returns `None`.
5. **`tests/ui/test_sku_picker_dialog.py::test_picker_empty_state_disables_ok`** —
   `list_profiles()` returns `[]` ⇒ OK disabled, empty-state label shown.
6. **`tests/ui/test_main_window_flow.py::test_no_sku_in_filename_opens_picker`** —
   controller-level: monkey-patch picker, assert it's invoked when filename has
   no `__`, and the selected profile flows into the preview screen.

All existing tests must continue to pass; no changes to `core/extractor.py`.

## Non-goals

- Allowing override of an already-correctly-detected SKU. (See alternative B
  in the brainstorming round if requested later.)
- Auto-detection from PDF content (embedded XMP metadata, OCR, etc.).
- Material/template override at preview time — picking a SKU picks the
  whole profile.
- Persisting the picked SKU back into the filename or any metadata file.

## Estimated change footprint

- 1 new method on the repository port + adapter (~15 LOC)
- 1 new UI file (`sku_picker.py`) (~80 LOC including layout + empty state)
- 1 method added to MainWindow, 1 control-flow branch changed (~15 LOC)
- ~6 new tests
- **Total ≈ 110 LOC across 4 production files + 3 test files**
