"""Entry point: `uv run python -m lbb` or the PyInstaller-built binary."""

from __future__ import annotations

import sys
from pathlib import Path

from lbb.adapters.config import DEFAULT_BASE_URL, ApiConfig, load_config
from lbb.app.container import build_fulfillment_service
from lbb.web.shell import run_app

_DATA_HOME = Path.home() / ".flanacom-tool"


def main() -> int:
    _DATA_HOME.mkdir(parents=True, exist_ok=True)
    example = _DATA_HOME / "config.example.json"
    if not example.exists():
        _template = (
            '{\n  "api_base_url": "' + DEFAULT_BASE_URL + '",\n'
            '  "api_key": "PASTE-YOUR-X-API-KEY-HERE"\n}\n'
        )
        example.write_text(_template, encoding="utf-8")
    config = load_config(config_path=_DATA_HOME / "config.json")
    if config is None:
        # Launch anyway with an empty key so the UI shows the configuration banner.
        config = ApiConfig(DEFAULT_BASE_URL, "")
    service = build_fulfillment_service(
        config=config,
        state_db=_DATA_HOME / "state.sqlite",
        cache_dir=_DATA_HOME / "cache",
    )
    run_app(service, title="Fulfillment Studio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
