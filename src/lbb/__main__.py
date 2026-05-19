"""Entry point: `uv run python -m lbb` or PyInstaller-built binary."""

import sys
from importlib.resources import files
from pathlib import Path

from PySide6.QtGui import QIcon, QPixmap
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


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Flanacom Tool")
    app.setApplicationDisplayName("Flanacom Tool")
    app.setWindowIcon(_app_icon())  # taskbar / alt-tab icon
    app.setStyleSheet(_load_qss())

    paths = AppPaths(
        db_path=_DATA_HOME / "profiles.sqlite",
        temp_dir=_DATA_HOME / "jobs",
    )
    deps = build_pipeline_deps(paths)

    window = MainWindow(deps)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
