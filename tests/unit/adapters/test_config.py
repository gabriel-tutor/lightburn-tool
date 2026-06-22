import json

from lbb.adapters.config import DEFAULT_BASE_URL, load_config


def test_env_key_takes_precedence(tmp_path):
    cfg = load_config(env={"FLANACOM_API_KEY": "envkey"}, config_path=tmp_path / "c.json")
    assert cfg.api_key == "envkey"
    assert cfg.base_url == DEFAULT_BASE_URL


def test_env_can_override_base_url(tmp_path):
    cfg = load_config(
        env={"FLANACOM_API_KEY": "k", "FLANACOM_API_URL": "https://other/api"},
        config_path=tmp_path / "c.json",
    )
    assert cfg.base_url == "https://other/api"


def test_falls_back_to_config_file(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"api_key": "filekey", "api_base_url": "https://file/api"}))
    cfg = load_config(env={}, config_path=p)
    assert cfg.api_key == "filekey"
    assert cfg.base_url == "https://file/api"


def test_returns_none_when_no_key(tmp_path):
    assert load_config(env={}, config_path=tmp_path / "missing.json") is None
