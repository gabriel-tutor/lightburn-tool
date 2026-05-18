"""Main window + controller for LightBurn Bridge.

Stack of two views:
  • HomeView   — drop zone + status pill (operator's idle screen)
  • JobPreviewView — pre-send confirmation with preflight readout

The controller logic lives here: pdf_chosen → resolve profile, run preflight,
render thumbnail, populate preview, switch. Errors surface via QMessageBox.
"""

import sys
import traceback
from pathlib import Path

from PySide6.QtWidgets import QMainWindow, QMessageBox, QStackedWidget

from lbb.app.job import Job
from lbb.app.pipeline import PipelineDeps, run_pipeline
from lbb.core.errors import LbbError
from lbb.core.extractor import extract_sku
from lbb.core.preflight import run_preflight
from lbb.ui.views.admin import AdminView
from lbb.ui.views.home import HomeView
from lbb.ui.views.job_preview import JobPreviewView

_THUMB_PX = 720
_WINDOW_W = 960
_WINDOW_H = 640


class MainWindow(QMainWindow):
    def __init__(self, deps: PipelineDeps) -> None:
        super().__init__()
        self.deps = deps
        self.setWindowTitle("LightBurn Bridge")
        self.resize(_WINDOW_W, _WINDOW_H)

        self.stack = QStackedWidget()
        self.home = HomeView(deps.lightburn)
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

    # ── Navigation helpers ──────────────────────────────────────────────────

    def _show_home(self) -> None:
        self.stack.setCurrentWidget(self.home)

    def _show_preview(self) -> None:
        self.stack.setCurrentWidget(self.preview)

    # ── Controller flow ─────────────────────────────────────────────────────

    def _on_pdf_chosen(self, path: Path) -> None:
        try:
            sku = extract_sku(path.name)
        except LbbError as e:
            QMessageBox.warning(self, "Filename problem", str(e))
            return

        profile = self.deps.repo.get(sku)
        if profile is None:
            QMessageBox.warning(
                self,
                "Unknown SKU",
                f"No profile mapped for {sku.value}.\n\nAdd one via Admin first.",
            )
            return

        # Belt-and-braces: catch anything unexpected (missing bundled dep, PDF
        # parser blowing up, etc.) so the user sees an error instead of a
        # silently-frozen home screen.
        try:
            info = self.deps.pdf.read_info(path)
            preflight = run_preflight(
                info,
                canvas_mm=(profile.template.canvas_w_mm, profile.template.canvas_h_mm),
            )
            png = self.deps.pdf.render_thumbnail_png(path, _THUMB_PX)
        except Exception as e:  # noqa: BLE001
            # Print the full traceback to stderr so users running from terminal
            # (or future log-file capture) get diagnostics, then surface the
            # short version in the dialog.
            traceback.print_exception(e, file=sys.stderr)
            QMessageBox.critical(
                self,
                "Couldn't open PDF",
                f"{type(e).__name__}: {e}\n\nFile: {path}",
            )
            return

        self.preview.populate(thumbnail_png=png, profile=profile, preflight=preflight)
        self._pending_pdf = path
        self._show_preview()

    def _on_send(self) -> None:
        if self._pending_pdf is None:
            return
        result = run_pipeline(Job(source_pdf=self._pending_pdf), self.deps)
        if result.ok:
            QMessageBox.information(
                self,
                "Loaded into LightBurn",
                f"{result.output_path.name}\n\nPress Start on the laser.",
            )
            self._pending_pdf = None
            self._show_home()
        else:
            QMessageBox.critical(self, "Send failed", result.error or "Unknown error")
