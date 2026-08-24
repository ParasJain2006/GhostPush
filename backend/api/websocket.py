"""WebSocket connection manager and synchronous-to-async notification bridge.

Architecture:
    NotificationTool.logger (sync) → WebSocketNotificationHandler.emit()
        → asyncio.run_coroutine_threadsafe(loop, broadcast) → WebSocket clients

The logging handler captures records on any thread (including the JobWorker
thread), then hands them to the FastAPI event loop for async broadcasting.
No secrets, API keys, or credentials ever appear in WebSocket payloads.
"""

import asyncio
import json
import logging
import re
from typing import Optional

from fastapi import WebSocket

# Regex matching NotificationTool's log format: "[job_id] [status] message"
_LOG_RE = re.compile(r"^\[(?P<job_id>[^\]]+)\]\s+\[(?P<status>[^\]]+)\]\s+(?P<message>.+)$")

NOTIFICATION_LOGGER_NAME = "GhostPush.NotificationTool"


class ConnectionManager:
    """Tracks active WebSocket connections and broadcasts JSON events."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._connections = [c for c in self._connections if c is not ws]

    async def broadcast(self, event: dict) -> None:
        """Broadcast a JSON-safe dict to all connected clients.

        Disconnected clients are silently removed; no exception propagates.
        """
        payload = json.dumps(event, ensure_ascii=False)
        dead: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    def active_count(self) -> int:
        return len(self._connections)


class WebSocketNotificationHandler(logging.Handler):
    """Logging handler that bridges NotificationTool log records to WebSocket clients.

    emit() is called from whichever thread produces the log record (e.g. the
    JobWorker thread).  It uses asyncio.run_coroutine_threadsafe to schedule
    the async broadcast on the FastAPI event loop without blocking the caller.
    """

    def __init__(self, manager: ConnectionManager, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__(level=logging.INFO)
        self.manager = manager
        self.loop = loop

    def emit(self, record: logging.LogRecord) -> None:
        msg = record.getMessage()
        m = _LOG_RE.match(msg)
        if not m:
            return

        event = {
            "job_id": m.group("job_id"),
            "status": m.group("status"),
            "message": m.group("message"),
        }

        try:
            asyncio.run_coroutine_threadsafe(
                self.manager.broadcast(event),
                self.loop,
            )
        except Exception:
            self.handleError(record)
