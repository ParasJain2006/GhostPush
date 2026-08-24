"""AI provider health-check module.

Provides status enumeration and functions to verify whether an AI provider
is configured and reachable, without exposing or logging credentials.
"""

import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger("GhostPush.AIHealth")

# Placeholder patterns that should NOT be treated as real API keys.
_PLACEHOLDER_PATTERNS = (
    "your_",
    "change_me",
    "dummy",
    "placeholder",
    "insert_",
    "api_key_here",
    "xxx",
    "TODO",
)


class AIHealthStatus(str, Enum):
    """Result of an AI provider health check."""

    NOT_CONFIGURED = "NOT_CONFIGURED"
    CONNECTED = "CONNECTED"
    INVALID_API_KEY = "INVALID_API_KEY"
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT = "TIMEOUT"
    PROVIDER_ERROR = "PROVIDER_ERROR"


def is_placeholder_key(key: Optional[str]) -> bool:
    """Return True if *key* is missing, empty, or looks like a placeholder value."""
    if not key or not key.strip():
        return True
    k = key.strip().lower()
    return any(p in k for p in _PLACEHOLDER_PATTERNS)


def has_api_key(config_manager: "ConfigManager", provider: str) -> bool:  # noqa: F821
    """Return True only when a real (non-placeholder) credential is stored for *provider*.

    Never reveals or logs the credential itself.
    """
    raw = config_manager.get_api_key(provider)
    return not is_placeholder_key(raw)


def check_provider_health(
    config_manager: "ConfigManager",  # noqa: F821
    provider: str,
    model: Optional[str] = None,
) -> AIHealthStatus:
    """Perform a minimal real provider request and return health status.

    * NOT_CONFIGURED   – no real key stored
    * CONNECTED        – provider responded successfully
    * INVALID_API_KEY  – provider rejected the key (401/403)
    * NETWORK_ERROR    – DNS / connection failure
    * TIMEOUT          – request timed out
    * PROVIDER_ERROR   – any other provider-side error
    """
    if not has_api_key(config_manager, provider):
        return AIHealthStatus.NOT_CONFIGURED

    api_key = config_manager.get_api_key(provider)

    try:
        from agent.providers import get_llm_provider, MockLLM

        llm = get_llm_provider(
            provider_name=provider,
            model_name=model,
            api_key=api_key,
        )

        # If the factory fell back to MockLLM, the key was rejected internally.
        if isinstance(llm, MockLLM):
            return AIHealthStatus.NOT_CONFIGURED

        # Minimal invocation to verify connectivity.
        llm.invoke("Hello")
        return AIHealthStatus.CONNECTED

    except Exception as exc:
        exc_str = str(exc).lower()
        exc_type = type(exc).__name__.lower()

        # Classify the error.
        if any(tok in exc_str for tok in ("401", "403", "invalid", "unauthorized", "authentication", "permission")):
            return AIHealthStatus.INVALID_API_KEY
        if any(tok in exc_type for tok in ("timeout", "timedout")):
            return AIHealthStatus.TIMEOUT
        if any(tok in exc_str for tok in ("timeout", "timed out", "deadline")):
            return AIHealthStatus.TIMEOUT
        if any(tok in exc_str for tok in ("connection", "network", "dns", "resolve", "refused", "unreachable")):
            return AIHealthStatus.NETWORK_ERROR
        if any(tok in exc_type for tok in ("connection", "socket", "network")):
            return AIHealthStatus.NETWORK_ERROR

        logger.debug("Provider health-check error: %s", exc)
        return AIHealthStatus.PROVIDER_ERROR
