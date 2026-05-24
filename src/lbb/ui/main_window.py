"""Main window + controller for Flanacom Tool.

Stack of two views:
  • HomeView   — drop zone + status pill (operator's idle screen)
  • JobPreviewView — pre-send confirmation with preflight readout

The controller logic lives here: pdf_chosen → resolve profile, run preflight,
render thumbnail, populate preview, switch. Errors surface via QMessageBox.
"""

import sys
import traceback
from importlib.resources import files
from pathlib import Path

from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QMainWindow, QMessageBox, QStackedWidget

from lbb.app.job import Job
from lbb.app.pipeline import PipelineDeps, run_pipeline
from lbb.core.errors import LbbError
from lbb.core.extractor import extract_sku
from lbb.core.models import Sku, SkuProfile
from lbb.core.preflight import run_preflight
from lbb.ui.dialogs.sku_picker import SkuPickerDialog
from lbb.ui.views.admin import AdminView
from lbb.ui.views.home import HomeView
from lbb.ui.views.job_preview import JobPreviewView

_THUMB_PX = 720
_WINDOW_W = 960
_WINDOW_H = 640


def _load_icon() -> QIcon:
    """Load the Flanacom app icon from package assets (works in dev + bundle)."""
    pix = QPixmap()
    pix.loadFromData(
        (files("lbb.ui.assets") / "flanacom.ico").read_bytes(), "ICO"
    )
    return QIcon(pix)


class MainWindow(QMainWindow):
    def __init__(self, deps: PipelineDeps) -> None:
        super().__init__()
        self.deps = deps
        self.setWindowTitle("Flanacom Tool")
        self.setWindowIcon(_load_icon())
        self.resize(_WINDOW_W, _WINDOW_H)

        self.stack = QStackedWidget()
        self.home = HomeView()
        self.preview = JobPreviewView()
        self.admin = AdminView(deps.repo)
        self.stack.addWidget(self.home)
        self.stack.addWidget(self.preview)
        self.stack.addWidget(self.admin)
        self.setCentralWidget(self.stack)

        self.home.pdf_chosen.connect(self._on_pdf_chosen)
        self.home.open_admin.connect(lambda: self.stack.setCurrentWidget(self.admin))
        self.preview.cancel_requested.connect(self._show_home)
        self.preview.send_requested.connect(self._on_send)
        self.admin.back_requested.connect(self._show_home)

        self._pending_pdf: Path | None = None
        self._pending_profile: SkuProfile | None = None
        # Tracks the most recently dispatched job so we can offer to close
        # the previous one before sending the next (avoids LightBurn's
        # "Save changes?" dialog).
        self._last_opened_pdf: Path | None = None
        self._last_opened_profile: SkuProfile | None = None

    # ── Navigation helpers ──────────────────────────────────────────────────

    def _show_home(self) -> None:
        self.stack.setCurrentWidget(self.home)

    def _show_preview(self) -> None:
        self.stack.setCurrentWidget(self.preview)

    # ── Controller flow ─────────────────────────────────────────────────────

    def _on_pdf_chosen(self, path: Path) -> None:
        try:
            sku = extract_sku(path.name)
            profile = self.deps.repo.get(sku)
            if profile is None:
                QMessageBox.warning(
                    self,
                    "Unknown SKU",
                    f"No profile mapped for {sku.value}.\n\nAdd one via Admin first.",
                )
                return
        except LbbError:
            # Filename has no `__` delimiter. Try the whole stem as a SKU first
            # (customer-order-numbered files can be registered directly), and
            # only fall back to the manual picker if that misses too.
            stem = path.stem.strip()
            profile = self.deps.repo.get(Sku(stem)) if stem else None
            if profile is None:
                profile = self._prompt_for_sku(path)
            if profile is None:
                return  # operator cancelled or no SKUs configured

        self._continue_with_profile(path, profile)

    def _prompt_for_sku(self, path: Path) -> SkuProfile | None:
        """Open the SKU picker dialog. Returns the chosen profile, or None
        if cancelled or no SKUs are configured."""
        dlg = SkuPickerDialog(self.deps.repo, path.name, parent=self)
        dlg.exec()
        return dlg.chosen_profile

    def _continue_with_profile(self, path: Path, profile: SkuProfile) -> None:
        # Belt-and-braces: catch anything unexpected (missing bundled dep, PDF
        # parser blowing up, etc.) so the user sees an error instead of a
        # silently-frozen home screen. Print full traceback to stderr so users
        # running from terminal (or future log-file capture) get diagnostics.
        try:
            info = self.deps.pdf.read_info(path)
            preflight = run_preflight(
                info,
                canvas_mm=(profile.template.canvas_w_mm, profile.template.canvas_h_mm),
            )
            png = self.deps.pdf.render_thumbnail_png(path, _THUMB_PX)
        except Exception as e:  # noqa: BLE001
            traceback.print_exception(e, file=sys.stderr)
            QMessageBox.critical(
                self,
                "Couldn't open PDF",
                f"{type(e).__name__}: {e}\n\nFile: {path}",
            )
            return

        self.preview.populate(thumbnail_png=png, profile=profile, preflight=preflight)
        self._pending_pdf = path
        self._pending_profile = profile
        self._show_preview()

    def _on_send(self) -> None:
        if self._pending_pdf is None:
            return

        # If a previous job is still loaded in LightBurn, offer to close it
        # cleanly before opening the new one. Avoids LightBurn's native
        # "Save changes?" dialog.
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
        if result.ok:
            QMessageBox.information(
                self,
                "Loaded into LightBurn",
                f"{result.output_path.name}\n\nPress Start on the laser.",
            )
            self._last_opened_pdf = self._pending_pdf
            self._last_opened_profile = self._pending_profile
            self._pending_pdf = None
            self._pending_profile = None
            self._show_home()
        else:
            QMessageBox.critical(self, "Send failed", result.error or "Unknown error")

    def _should_offer_close_previous(self) -> bool:
        """True iff there's a previously-dispatched PDF different from the
        current one, AND LightBurn is still running with it."""
        if self._last_opened_pdf is None:
            return False
        if self._last_opened_pdf == self._pending_pdf:
            return False
        return self.deps.lightburn.is_running()

    def _confirm_close_previous(self, prev_profile: SkuProfile | None) -> str:
        """Show a 3-button dialog: returns 'yes' | 'no' | 'cancel'.

        Test seam — pytest-qt tests monkey-patch this method to avoid
        driving the modal interactively.
        """
        sku_text = (
            prev_profile.sku.value if prev_profile is not None else "the previous PDF"
        )
        box = QMessageBox(self)
        box.setWindowTitle("Close previous job?")
        box.setIcon(QMessageBox.Question)
        box.setText(f"You had <b>{sku_text}</b> open in LightBurn.")
        box.setInformativeText(
            "Finished engraving it?\n\n"
            "• Yes — I'll close LightBurn cleanly, then open the new PDF "
            "(no \"Save changes?\" prompt).\n"
            "• No — Open the new PDF anyway. LightBurn will ask what to "
            "do with the previous one.\n"
            "• Cancel — Stay on this preview and don't send."
        )
        yes_btn = box.addButton("Yes, close it", QMessageBox.AcceptRole)
        no_btn = box.addButton("No, keep open", QMessageBox.DestructiveRole)
        cancel_btn = box.addButton("Cancel", QMessageBox.RejectRole)
        box.setDefaultButton(yes_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked is yes_btn:
            return "yes"
        if clicked is no_btn:
            return "no"
        if clicked is cancel_btn:
            return "cancel"
        return "cancel"  # window closed via X → treat as cancel
