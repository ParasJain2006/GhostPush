"""Configuration constants and path resolution for GhostPush backend."""

import os
import sys
from pathlib import Path

DEFAULT_API_HOST = "127.0.0.1"
DEFAULT_API_PORT = 8000
DEFAULT_AUTO_PUSH = False
DEFAULT_AUTO_COMMIT = True
DEFAULT_AUTO_START = False
DEFAULT_NOTIFICATIONS = True
DEFAULT_THEME = "dark"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_AI_PROVIDER = "gemini"
DEFAULT_AI_MODEL = "gemini-1.5-flash"


def get_config_dir() -> Path:
    """Return the cross-platform application configuration directory.

    Windows: %APPDATA%/GhostPush
    Linux/macOS: ~/.config/ghostpush
    """
    if sys.platform == "win32":
        appdata = os.getenv("APPDATA")
        if appdata:
            return Path(appdata) / "GhostPush"
        return Path.home() / "AppData" / "Roaming" / "GhostPush"
    return Path.home() / ".config" / "ghostpush"


def get_config_file_path() -> Path:
    """Return the full path to config.json."""
    return get_config_dir() / "config.json"
