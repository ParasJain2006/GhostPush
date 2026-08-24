"""Typed configuration models for the GhostPush backend.

This module defines the single Pydantic schema that backs the backend's
configuration. Validation is enforced at model construction/validation time so
an AppSettings instance can never represent an invalid configuration.

Only schema + validation live here. Defaults and file paths live in
backend/config/settings.py; persistence lives in backend/config/manager.py.
"""

import re
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class AppSettings(BaseModel):
    """Typed application configuration for the GhostPush backend.

    Attributes:
        repository_path: Absolute path to the local git repo that receives
            solutions. Must be a non-empty path to an existing directory.
        remote_repo_url: Optional remote repository URL (may be empty for local-only).
        ai_provider: LLM provider name (e.g. "gemini", "openai"). Cannot be empty.
        ai_model: Optional LLM model name (empty means provider default).
        api_host: Host/interface the backend API will bind to.
        api_port: TCP port the backend API will bind to (1..65535).
        auto_push: Push commits to the remote automatically.
        auto_commit: Create git commits automatically.
        auto_start: Start the backend with the OS/session.
        notifications: Emit in-app status notifications.
        theme: Back/user-facing theme identifier (e.g. "dark" / "light").
        log_level: Logging level (DEBUG/INFO/WARNING/ERROR/CRITICAL).
    """

    repository_path: str = Field(..., description="Existing local repository directory")
    remote_repo_url: str = Field(default="", description="Optional remote repository URL")
    ai_provider: str = Field(..., description="LLM provider name; cannot be empty")
    ai_model: str = Field(default="", description="Optional LLM model override")
    api_host: str = Field(default="127.0.0.1", description="API bind host")
    api_port: int = Field(default=8000, description="API bind port (1-65535)")
    auto_push: bool = Field(default=False, description="Auto-push commits to remote")
    auto_commit: bool = Field(default=True, description="Auto-commit new solutions")
    auto_start: bool = Field(default=False, description="Auto-start backend with the session")
    notifications: bool = Field(default=True, description="Enable in-app notifications")
    theme: str = Field(default="dark", description="UI theme identifier")
    log_level: str = Field(default="INFO", description="Logging level name")

    @field_validator("repository_path")
    @classmethod
    def _repository_path_must_exist(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("repository_path cannot be empty")
        path = Path(value).expanduser()
        if not path.is_dir():
            raise ValueError(f"repository_path must be an existing directory: {value!r}")
        return str(path)

    @field_validator("ai_provider")
    @classmethod
    def _ai_provider_must_not_be_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("ai_provider cannot be empty")
        return value.strip()

    @field_validator("api_port")
    @classmethod
    def _api_port_must_be_valid(cls, value: int) -> int:
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"api_port must be an integer, got {value!r}")
        if not (1 <= value <= 65535):
            raise ValueError(f"api_port must be between 1 and 65535, got {value!r}")
        return value

    @field_validator("log_level")
    @classmethod
    def _log_level_must_be_valid(cls, value: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = value.strip().upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}, got {value!r}")
        return upper
