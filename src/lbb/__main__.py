"""Entry point: `uv run python -m lbb`."""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from lbb.app.container import AppPaths, build_pipeline_deps
from lbb.ui.main_window import MainWindow

_QSS_PATH = Path(__file__).parent / "ui" / "theme" / "app.qss"
_DATA_HOME = Path.home() / ".lightburn-bridge"


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(_QSS_PATH.read_text(encoding="utf-8"))

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
