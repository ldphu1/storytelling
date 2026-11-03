import pytest
from pathlib import Path
from app.config import AppConfig, get_config

def test_default_config_loading():
    cfg = get_config()
    assert isinstance(cfg, AppConfig)
    assert isinstance(cfg.worker_urls, list)
    assert cfg.storage_dir.exists() or Path(cfg.storage_dir).as_posix() != ""
    assert cfg.nvenc_max_concurrency == 2
    assert cfg.comfy_max_concurrency == 2

def test_config_from_toml(tmp_path):
    toml_file = tmp_path / "config.toml"
    toml_file.write_text("""
[system]
nvenc_max_concurrency = 3
comfy_max_concurrency = 4
storage_dir = "test_storage"

[cloud_workers]
worker_urls = ["https://worker1.trycloudflare.com", "https://worker2.trycloudflare.com"]

[llm]
provider = "openai"
api_key = "sk-test"
model = "gpt-4o"
""", encoding="utf-8")

    cfg = get_config(config_path=toml_file)
    assert cfg.nvenc_max_concurrency == 3
    assert cfg.comfy_max_concurrency == 4
    assert len(cfg.worker_urls) == 2
    assert cfg.worker_urls[0] == "https://worker1.trycloudflare.com"
    assert cfg.llm_provider == "openai"
    assert cfg.llm_api_key == "sk-test"
