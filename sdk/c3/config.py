"""Configuration handling"""
import os
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".c3"
CONFIG_FILE = CONFIG_DIR / "config"

DEFAULT_API_URL = "https://api.compute3.ai"
DEFAULT_WS_URL = "wss://api.compute3.ai"
WS_LOGS_PATH = "/orchestra/ws/logs"  # WebSocket path for job logs: {WS_URL}{WS_LOGS_PATH}/{job_key}

# GHCR images
GHCR_IMAGES = "ghcr.io/compute3ai/images"
COMFYUI_IMAGE = f"{GHCR_IMAGES}/comfyui"


def _load_config_file() -> dict:
    """Load config from ~/.c3/config"""
    config = {}
    if CONFIG_FILE.exists():
        for line in CONFIG_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()
    return config


def get_config_value(key: str, default: str = None) -> Optional[str]:
    """Get config value: env var > config file > default"""
    env_val = os.getenv(key)
    if env_val:
        return env_val
    config = _load_config_file()
    return config.get(key, default)


def get_api_key() -> Optional[str]:
    """Get API key from env or config file"""
    return get_config_value("C3_API_KEY")


def get_api_url() -> str:
    """Get API URL"""
    return get_config_value("C3_API_URL", DEFAULT_API_URL)


def get_ws_url() -> str:
    """Get WebSocket URL"""
    ws = get_config_value("C3_WS_URL")
    if ws:
        return ws
    # Derive from API URL
    api = get_api_url()
    return api.replace("https://", "wss://").replace("http://", "ws://")


def configure(api_key: str, api_url: str = None):
    """Save configuration to ~/.c3/config"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    config = _load_config_file()
    config["C3_API_KEY"] = api_key
    if api_url:
        config["C3_API_URL"] = api_url

    lines = [f"{k}={v}" for k, v in config.items()]
    CONFIG_FILE.write_text("\n".join(lines) + "\n")
    CONFIG_FILE.chmod(0o600)
