import os
import tomllib
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

class AppConfig(BaseModel):
    storage_dir: Path = Field(default_factory=lambda: Path("storage"))
    resource_dir: Path = Field(default_factory=lambda: Path("resource"))
    
    # Concurrency controls (Semaphore limits as per risk document)
    nvenc_max_concurrency: int = 2
    comfy_max_concurrency: int = 2
    
    # ComfyUI Cloudflare Tunnel URLs
    worker_urls: List[str] = Field(default_factory=list)
    ollama_worker_url: str = ""
    
    # LLM Settings
    llm_provider: str = "openai"  # openai, gemini, ollama, deepseek
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o"
    
    # Voice Settings
    default_voice: str = "vi-VN-NamMinhNeural"
    voice_rate: str = "+0%"

    def get_task_dir(self, task_id: str) -> Path:
        p = self.storage_dir / "tasks" / task_id
        p.mkdir(parents=True, exist_ok=True)
        return p

_cached_config: Optional[AppConfig] = None

def get_config(config_path: Optional[Path] = None, force_reload: bool = False) -> AppConfig:
    global _cached_config
    if _cached_config is not None and not force_reload and config_path is None:
        return _cached_config

    cfg_dict = {}
    path = config_path or Path("config.toml")
    if path.exists():
        with open(path, "rb") as f:
            raw_toml = tomllib.load(f)
            sys_sec = raw_toml.get("system", {})
            workers_sec = raw_toml.get("cloud_workers", {})
            llm_sec = raw_toml.get("llm", {})
            voice_sec = raw_toml.get("voice", {})
            
            if "storage_dir" in sys_sec:
                cfg_dict["storage_dir"] = Path(sys_sec["storage_dir"])
            if "nvenc_max_concurrency" in sys_sec:
                cfg_dict["nvenc_max_concurrency"] = int(sys_sec["nvenc_max_concurrency"])
            if "comfy_max_concurrency" in sys_sec:
                cfg_dict["comfy_max_concurrency"] = int(sys_sec["comfy_max_concurrency"])
            if "worker_urls" in workers_sec:
                cfg_dict["worker_urls"] = workers_sec["worker_urls"]
            if "ollama_worker_url" in workers_sec:
                cfg_dict["ollama_worker_url"] = workers_sec["ollama_worker_url"]
            elif "ollama_worker_url" in llm_sec:
                cfg_dict["ollama_worker_url"] = llm_sec["ollama_worker_url"]
            if "provider" in llm_sec:
                cfg_dict["llm_provider"] = llm_sec["provider"]
            if "api_key" in llm_sec:
                cfg_dict["llm_api_key"] = llm_sec["api_key"]
            if "base_url" in llm_sec:
                cfg_dict["llm_base_url"] = llm_sec["base_url"]
            if "model" in llm_sec:
                cfg_dict["llm_model"] = llm_sec["model"]
            if "default_voice" in voice_sec:
                cfg_dict["default_voice"] = voice_sec["default_voice"]
            if "voice_rate" in voice_sec:
                cfg_dict["voice_rate"] = voice_sec["voice_rate"]

    # Allow environment variable overrides
    if os.getenv("OPENAI_API_KEY") and "llm_api_key" not in cfg_dict:
        cfg_dict["llm_api_key"] = os.environ["OPENAI_API_KEY"]
    if os.getenv("OLLAMA_WORKER_URL") and "ollama_worker_url" not in cfg_dict:
        cfg_dict["ollama_worker_url"] = os.environ["OLLAMA_WORKER_URL"]

    config = AppConfig(**cfg_dict)
    if config_path is None:
        _cached_config = config
    return config
