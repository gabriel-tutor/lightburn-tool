"""Load the engraving-API credentials Python-side. The secret key is read from
the FLANACOM_API_KEY env var, else a git-ignored config file. It is NEVER
embedded in the JS frontend or committed to the repo. The base URL is public."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BASE_URL = "https://puscgcazmnqxazietgvy.supabase.co/functions/v1/engraving-api"


@dataclass(frozen=True, slots=True)
class ApiConfig:
    base_url: str
    api_key: str


def load_config(
    *, env: Mapping[str, str] | None = None, config_path: Path
) -> ApiConfig | None:
    env = os.environ if env is None else env
    key = env.get("FLANACOM_API_KEY")
    if key:
        return ApiConfig(env.get("FLANACOM_API_URL", DEFAULT_BASE_URL), key)
    path = Path(config_path)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if data.get("api_key"):
            return ApiConfig(data.get("api_base_url", DEFAULT_BASE_URL), data["api_key"])
    return None
