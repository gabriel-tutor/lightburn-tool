# Less-Friction Next-Job — design

**Date:** 2026-05-26
**Status:** Approved (after client demo accepted the rebrand)
**Driver:** When the operator engraves multiple PDFs in a session, each
subsequent "Open in LightBurn" surfaces LightBurn's native "Save changes?"
dialog because the previous file is still loaded. That dialog is friction
in the high-throughput case (one operator, dozens of orders/day). The
operator's "I'm done with the previous one" intent should bypass it
cleanly.

## Goal

When the operator confirms "I'm done with the previous job", close LightBurn
silently before opening the next PDF, so the next dispatch lands in a fresh
LightBurn workspace with no save-prompt friction.

## Architecture

### New port method

```python
class LightBurnPort(Protocol):
    def is_running(self) -> bool: ...
    def load_file(self, path: Path) -> None: ...
    def status(self) -> LBStatus: ...
    def close_running(self) -> None: ...   # NEW
```

### Adapters

- **`LightBurnShellAdapter.close_running()`** — force-terminate the
  LightBurn process:
  - Windows: `taskkill /F /IM LightBurn.exe`
  - POSIX:   `pkill -x LightBurn`
  - Exit code 128 (no process matched) is **not** an error — operator may
    have closed LightBurn manually.
  - `subprocess.run(..., check=False)` blocks until termination completes
    — when it returns, LightBurn is gone and we can immediately relaunch.
- **`LightBurnFake.close_running()`** — set `self._running = False`, clear
  `self.loaded[]`, append the path to a new `self.closed_count` counter for
  test assertions.

### Controller flow (MainWindow)

```python
class MainWindow(QMainWindow):
    def __init__(self, deps):
        ...
        self._last_opened_pdf: Path | None = None
        self._last_opened_profile: SkuProfile | None = None

    def _on_send(self) -> None:
        if self._pending_pdf is None:
            return
        # NEW: ask before opening if a previous job is still loaded
        if self._should_offer_close_previous():
            choice = self._confirm_close_previous(self._last_opened_profile)
            if choice == "cancel":
                return
            if choice == "yes":
                self.deps.lightburn.close_running()
        result = run_pipeline(
            Job(source_pdf=self._pending_pdf, profile=self._pending_profile),
            self.deps,
        )
        ...
        if result.ok:
            self._last_opened_pdf = self._pending_pdf
            self._last_opened_profile = self._pending_profile
            ...

    def _should_offer_close_previous(self) -> bool:
        # No previous job, or same PDF being re-sent → no prompt.
        if self._last_opened_pdf is None:
            return False
        if self._last_opened_pdf == self._pending_pdf:
            return False
        # LightBurn already closed by operator → no prompt.
        return self.deps.lightburn.is_running()

    def _confirm_close_previous(
        self, prev_profile: SkuProfile | None
    ) -> str:  # "yes" | "no" | "cancel"
        """Test seam — pytest-qt tests monkey-patch this."""
        # QMessageBox with 3 custom-labelled buttons.
        ...
```

### Dialog UX

QMessageBox with three custom buttons via `addButton(text, role)`:

```
title  : "Close previous job?"
text   : "You had {prev_sku} open in LightBurn.
          Finished engraving it?"
buttons:
  • [Yes, close it]   role=AcceptRole    → returns "yes"
  • [No, keep open]   role=DestructiveRole → returns "no"
  • [Cancel]          role=RejectRole    → returns "cancel"
```

Default button: "Yes, close it" (most common operator intent).

## Edge cases

| Situation | Behaviour |
|---|---|
| First-ever send (`_last_opened_pdf is None`) | No prompt, normal send. |
| Same PDF re-sent immediately | No prompt — same job. |
| LightBurn already closed by operator | No prompt — `is_running()` returns False. |
| Operator clicks Cancel | `_last_opened_pdf` unchanged, no dispatch. Operator stays on preview. |
| Operator clicks No | Dispatch immediately. LightBurn shows its own save dialog. `_last_opened_pdf` updates to the new PDF on success. |
| `taskkill` returns 128 (no matching process) | Treated as success — already gone. |
| `taskkill` errors otherwise | Logged via `traceback.print_exception` to stderr; dispatch continues (LightBurn will surface any issue itself). |

## Tests

1. `tests/unit/adapters/test_lightburn_shell.py::test_close_running_uses_taskkill_on_windows`
   — assert subprocess command shape, creationflags=CREATE_NO_WINDOW.
2. `tests/ui/test_main_window.py::test_no_prompt_on_first_send`
   — fresh window → drop → send → confirm `close_running` was NOT called and
     no prompt was shown.
3. `tests/ui/test_main_window.py::test_prompt_appears_when_previous_job_exists_and_lightburn_running`
   — drop A → send → drop B → send → monkey-patched `_confirm_close_previous`
     should be called; LightBurn's `close_running` invoked only on "yes".
4. `tests/ui/test_main_window.py::test_cancel_on_prompt_aborts_send`
   — patch confirm to return "cancel" → assert `lightburn.loaded` stays at
     just [A]; preview is still current.
5. `tests/ui/test_main_window.py::test_no_keep_open_skips_close_but_continues_send`
   — patch confirm to return "no" → `close_running` not called, `loaded == [A, B]`.
6. `tests/ui/test_main_window.py::test_no_prompt_when_lightburn_already_closed`
   — drop A → send → simulate LB closed → drop B → send → no prompt fires.

## Non-goals

- A "Don't ask again" checkbox.
- Auto-detection of "engrave actually completed" (we have no signal from
  LightBurn).
- Differentiating between "operator finished engraving" and "operator just
  wants to switch designs" — both lead to "close it".
- Re-implementing this via LightBurn's UDP protocol (still unreliable).
