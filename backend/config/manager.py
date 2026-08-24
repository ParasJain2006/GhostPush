"""Configuration manager for loading, persisting, and updating AppSettings."""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

from common.errors import ErrorCode, GhostPushError
from backend.config.models import AppSettings
from backend.config.settings import (
    DEFAULT_AI_MODEL,
    DEFAULT_AI_PROVIDER,
    DEFAULT_API_HOST,
    DEFAULT_API_PORT,
    DEFAULT_AUTO_COMMIT,
    DEFAULT_AUTO_PUSH,
    DEFAULT_AUTO_START,
    DEFAULT_LOG_LEVEL,
    DEFAULT_NOTIFICATIONS,
    DEFAULT_THEME,
    get_config_dir,
    get_config_file_path,
)

SECRET_KEYS = {
    "api_key",
    "gemini_api_key",
    "openai_api_key",
    "anthropic_api_key",
    "groq_api_key",
    "openrouter_api_key",
    "secret",
    "token",
    "password",
}

PROVIDER_ENV_MAP = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "groq": "GROQ_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


class ConfigManager:
    """Manages application configuration persistence and secret resolution."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or get_config_file_path()

    def _get_default_dict(self) -> Dict[str, Any]:
        cwd = str(Path.cwd().resolve())
        return {
            "repository_path": cwd,
            "remote_repo_url": "",
            "ai_provider": DEFAULT_AI_PROVIDER,
            "ai_model": DEFAULT_AI_MODEL,
            "api_host": DEFAULT_API_HOST,
            "api_port": DEFAULT_API_PORT,
            "auto_push": DEFAULT_AUTO_PUSH,
            "auto_commit": DEFAULT_AUTO_COMMIT,
            "auto_start": DEFAULT_AUTO_START,
            "notifications": DEFAULT_NOTIFICATIONS,
            "theme": DEFAULT_THEME,
            "log_level": DEFAULT_LOG_LEVEL,
        }

    def load_config(self) -> AppSettings:
        """Load and validate configuration from config.json or return defaults."""
        if not self.config_path.exists():
            defaults = self._get_default_dict()
            try:
                return AppSettings.model_validate(defaults)
            except Exception as e:
                raise GhostPushError(
                    ErrorCode.INVALID_JSON,
                    "Default configuration validation failed.",
                    details=str(e),
                )

        try:
            raw_text = self.config_path.read_text(encoding="utf-8")
            data = json.loads(raw_text)
        except Exception as e:
            raise GhostPushError(
                ErrorCode.INVALID_JSON,
                f"Failed to read or parse configuration file at {self.config_path}",
                details=str(e),
            )

        if not isinstance(data, dict):
            raise GhostPushError(
                ErrorCode.INVALID_JSON,
                "Configuration JSON must be an object.",
            )

        # Strip any secret fields if present
        for key in list(data.keys()):
            if key.lower() in SECRET_KEYS or "api_key" in key.lower():
                data.pop(key, None)

        try:
            return AppSettings.model_validate(data)
        except Exception as e:
            raise GhostPushError(
                ErrorCode.INVALID_JSON,
                f"Configuration validation failed: {e}",
                details=str(e),
            )

    def save_config(self, settings: AppSettings) -> None:
        """Save non-secret AppSettings to config.json."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            data = settings.model_dump()
            for key in list(data.keys()):
                if key.lower() in SECRET_KEYS or "api_key" in key.lower():
                    data.pop(key, None)

            json_str = json.dumps(data, indent=2, ensure_ascii=False)
            self.config_path.write_text(json_str, encoding="utf-8")
        except Exception as e:
            raise GhostPushError(
                ErrorCode.FILE_WRITE_FAILED,
                f"Failed to write configuration file at {self.config_path}",
                details=str(e),
            )

    def update_config(self, updates: Dict[str, Any]) -> AppSettings:
        """Apply non-secret updates, validate, and persist new settings."""
        if not isinstance(updates, dict):
            raise ValueError("Updates must be a dictionary.")

        for key in updates.keys():
            k_lower = key.lower()
            if k_lower in SECRET_KEYS or "api_key" in k_lower or "secret" in k_lower or "password" in k_lower:
                raise ValueError(f"Secret field '{key}' cannot be persisted in config.json.")

        current = self.load_config()
        current_data = current.model_dump()
        current_data.update(updates)

        new_settings = AppSettings.model_validate(current_data)
        self.save_config(new_settings)
        return new_settings

    def get_api_key(self, provider: str) -> Optional[str]:
        """Resolve API key for a provider from process environment without persisting or logging."""
        if not provider or not isinstance(provider, str):
            return None
        norm_provider = provider.lower().strip()
        env_var = PROVIDER_ENV_MAP.get(norm_provider)
        if not env_var:
            return None

        try:
            from dotenv import load_dotenv
            frozen_env = get_config_dir() / ".env"
            if frozen_env.exists():
                load_dotenv(dotenv_path=frozen_env, override=False)
            load_dotenv(override=False)
        except ImportError:
            pass

        val = os.getenv(env_var)
        if val and val.strip():
            return val.strip()
        return None

    def set_api_key(self, provider: str, api_key: str) -> None:
        """Save an API key for a provider to %APPDATA%/GhostPush/.env and update process memory.

        Preserves existing lines/comments in .env and ensures the key is NOT saved to config.json.
        """
        if not provider or not isinstance(provider, str):
            raise GhostPushError(ErrorCode.INVALID_JSON, "Provider name must be a non-empty string.")

        norm_provider = provider.lower().strip()
        env_var = PROVIDER_ENV_MAP.get(norm_provider)
        if not env_var:
            raise GhostPushError(
                ErrorCode.INVALID_JSON,
                f"Unsupported AI provider '{provider}'. Valid providers: {sorted(PROVIDER_ENV_MAP.keys())}",
            )

        clean_key = api_key.strip()
        env_path = get_config_dir() / ".env"
        env_path.parent.mkdir(parents=True, exist_ok=True)

        lines = []
        if env_path.exists():
            lines = env_path.read_text(encoding="utf-8").splitlines()

        updated = False
        new_lines = []
        pattern = re.compile(rf"^\s*{re.escape(env_var)}\s*=")

        for line in lines:
            if pattern.match(line):
                new_lines.append(f"{env_var}={clean_key}")
                updated = True
            else:
                new_lines.append(line)

        if not updated:
            new_lines.append(f"{env_var}={clean_key}")

        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

        if clean_key:
            os.environ[env_var] = clean_key
        else:
            os.environ.pop(env_var, None)

    def has_api_key(self, provider: str) -> bool:
        """Return True only when a real (non-placeholder) credential is stored for *provider*.

        Delegates to health.is_placeholder_key for placeholder detection.
        Never reveals or logs the credential.
        """
        from backend.config.health import is_placeholder_key

        raw = self.get_api_key(provider)
        return not is_placeholder_key(raw)

    def remove_api_key(self, provider: str) -> None:
        """Remove the stored API key for *provider* from .env and process environment."""
        if not provider or not isinstance(provider, str):
            return

        norm_provider = provider.lower().strip()
        env_var = PROVIDER_ENV_MAP.get(norm_provider)
        if not env_var:
            return

        # Remove from .env file
        env_path = get_config_dir() / ".env"
        if env_path.exists():
            lines = env_path.read_text(encoding="utf-8").splitlines()
            pattern = re.compile(rf"^\s*{re.escape(env_var)}\s*=")
            new_lines = [line for line in lines if not pattern.match(line)]
            env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

        # Remove from process environment
        os.environ.pop(env_var, None)

