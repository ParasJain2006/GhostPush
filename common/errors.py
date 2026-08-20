from enum import Enum
from typing import Optional


class ErrorCode(str, Enum):
    INVALID_PLATFORM = "INVALID_PLATFORM"
    INVALID_JSON = "INVALID_JSON"
    EMPTY_CODE = "EMPTY_CODE"
    GIT_FAILED = "GIT_FAILED"
    AI_TIMEOUT = "AI_TIMEOUT"
    FILE_WRITE_FAILED = "FILE_WRITE_FAILED"
    SQLITE_ERROR = "SQLITE_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"


class GhostPushError(Exception):
    """Base exception class for GhostPush Code Repository Manager."""

    def __init__(self, code: ErrorCode, message: str, details: Optional[str] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def to_dict(self) -> dict:
        return {
            "error_code": self.code.value,
            "message": self.message,
            "details": self.details,
        }


# Alias for backward compatibility
CPAssistantError = GhostPushError
