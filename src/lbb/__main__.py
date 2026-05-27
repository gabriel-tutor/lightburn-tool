"""Entry point: `uv run python -m lbb` or PyInstaller-built binary."""

import sys
from importlib.resources import files
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPalette, QPixmap
from PySide6.QtWidgets import QApplication

from lbb.app.container import AppPaths, build_pipeline_deps
from lbb.ui.main_window import MainWindow

_DATA_HOME = Path.home() / ".lightburn-bridge"


def _load_qss() -> str:
    """Read the bundled QSS as package data so PyInstaller can find it too."""
    return (files("lbb.ui.theme") / "app.qss").read_text(encoding="utf-8")


def _app_icon() -> QIcon:
    """Load the Flanacom icon from package assets (works in dev + bundle)."""
    pix = QPixmap()
    pix.loadFromData(
        (files("lbb.ui.assets") / "flanacom.ico").read_bytes(), "ICO"
    )
    return QIcon(pix)


def _flanacom_light_palette() -> QPalette:
    """Light palette tuned to the Flanacom brand. Forces light backgrounds on
    dialogs/widgets that don't get hit by QSS (Qt 6 otherwise follows the OS
    color scheme — Windows 11 dark mode bleeds through QMessageBox etc.)."""
    p = QPalette()
    p.setColor(QPalette.Window, QColor("#FAFAFA"))
    p.setColor(QPalette.WindowText, QColor("#1A1A1A"))
    p.setColor(QPalette.Base, QColor("#FFFFFF"))
    p.setColor(QPalette.AlternateBase, QColor("#FAFAFA"))
    p.setColor(QPalette.Text, QColor("#1A1A1A"))
    p.setColor(QPalette.PlaceholderText, QColor("#9CA3AF"))
    p.setColor(QPalette.Button, QColor("#FFFFFF"))
    p.setColor(QPalette.ButtonText, QColor("#1A1A1A"))
    p.setColor(QPalette.Highlight, QColor("#F58A1F"))
    p.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    p.setColor(QPalette.ToolTipBase, QColor("#FFFFFF"))
    p.setColor(QPalette.ToolTipText, QColor("#1A1A1A"))
    p.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#9CA3AF"))
    p.setColor(QPalette.Disabled, QPalette.Text, QColor("#9CA3AF"))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#9CA3AF"))
    return p


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Flanacom Tool")
    app.setApplicationDisplayName("Flanacom Tool")
    app.setWindowIcon(_app_icon())  # taskbar / alt-tab icon
    # Force a light color scheme regardless of OS dark mode (Windows 11
    # otherwise renders QMessageBox / QDialog with dark chrome).
    app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    app.setStyle("Fusion")  # consistent, palette-respecting style
    app.setPalette(_flanacom_light_palette())
    app.setStyleSheet(_load_qss())

    paths = AppPaths(
        db_path=_DATA_HOME / "profiles.sqlite",
        temp_dir=_DATA_HOME / "jobs",
        orders_dir=_DATA_HOME / "orders",
    )
    deps = build_pipeline_deps(paths)

    window = MainWindow(deps)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
