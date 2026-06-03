"""Entry point: `uv run python -m lbb` or PyInstaller-built binary."""

import sys
from pathlib import Path

from lbb.app.container import build_fulfillment_service
from lbb.web.shell import run_app

_DATA_HOME = Path.home() / ".flanacom-tool"


def main() -> int:
    service = build_fulfillment_service(
        orders_dir=_DATA_HOME / "orders",
        state_db=_DATA_HOME / "state.sqlite",
    )
    run_app(service, title="Fulfillment Studio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
