from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import ValidationError

from common.errors import GhostPushError
from backend.config.manager import ConfigManager
from backend.config.models import AppSettings

router = APIRouter(prefix="/config", tags=["Configuration"])


def _get_config_manager(request: Request) -> ConfigManager:
    config_mgr = getattr(request.app.state, "config_mgr", None)
    if config_mgr is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Configuration service unavailable.",
        )
    return config_mgr


@router.get("", response_model=AppSettings, status_code=status.HTTP_200_OK)
def get_config(request: Request) -> AppSettings:
    """Retrieve the current non-secret application configuration."""
    config_mgr = _get_config_manager(request)
    return config_mgr.load_config()


@router.put("", response_model=AppSettings, status_code=status.HTTP_200_OK)
def update_config(updates: Dict[str, Any], request: Request) -> AppSettings:
    """Update non-secret application configuration fields."""
    config_mgr = _get_config_manager(request)
    try:
        return config_mgr.update_config(updates)
    except (ValueError, GhostPushError, ValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
