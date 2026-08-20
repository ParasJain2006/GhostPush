"""Tests for GhostPush WebSocket notification hub (Phase 5).

Async unit tests use asyncio.run() directly — no pytest-asyncio needed.
Integration tests use FastAPI TestClient.
"""

import asyncio
import json
import logging
from unittest.mock import AsyncMock

import pytest

from backend.api.websocket import (
    ConnectionManager,
    NOTIFICATION_LOGGER_NAME,
    WebSocketNotificationHandler,
)


# ── Unit: ConnectionManager ────────────────────────────────────────────────────

def test_connection_manager_connect_and_count():
    async def _run():
        manager = ConnectionManager()
        ws = AsyncMock()
        await manager.connect(ws)
        ws.accept.assert_called_once()
        assert manager.active_count() == 1

    asyncio.run(_run())


def test_connection_manager_disconnect_removes_client():
    async def _run():
        manager = ConnectionManager()
        ws = AsyncMock()
        await manager.connect(ws)
        manager.disconnect(ws)
        assert manager.active_count() == 0

    asyncio.run(_run())


def test_connection_manager_broadcast_sends_to_all():
    async def _run():
        manager = ConnectionManager()
        ws1, ws2 = AsyncMock(), AsyncMock()
        await manager.connect(ws1)
        await manager.connect(ws2)

        event = {"job_id": "J-1", "status": "SUCCESS", "message": "done"}
        await manager.broadcast(event)

        expected_payload = json.dumps(event, ensure_ascii=False)
        ws1.send_text.assert_called_once_with(expected_payload)
        ws2.send_text.assert_called_once_with(expected_payload)

    asyncio.run(_run())


def test_connection_manager_broadcast_skips_dead_clients():
    """A disconnected client must not crash broadcasting."""
    async def _run():
        manager = ConnectionManager()
        dead_ws = AsyncMock()
        dead_ws.send_text.side_effect = RuntimeError("Connection closed")
        live_ws = AsyncMock()

        await manager.connect(dead_ws)
        await manager.connect(live_ws)

        event = {"job_id": "J-2", "status": "FAILED", "message": "error"}
        await manager.broadcast(event)  # must not raise

        expected_payload = json.dumps(event, ensure_ascii=False)
        live_ws.send_text.assert_called_once_with(expected_payload)
        assert manager.active_count() == 1

    asyncio.run(_run())


# ── Unit: WebSocketNotificationHandler ─────────────────────────────────────────

def test_ws_handler_parses_notification_tool_log_format():
    """Handler must parse [job_id] [status] message from NotificationTool."""
    captured: list[dict] = []

    async def fake_broadcast(event: dict):
        captured.append(event)

    async def _run():
        loop = asyncio.get_event_loop()
        manager = ConnectionManager()
        handler = WebSocketNotificationHandler(manager=manager, loop=loop)
        manager.broadcast = fake_broadcast  # type: ignore[method-assign]

        record = logging.LogRecord(
            name=NOTIFICATION_LOGGER_NAME,
            level=logging.INFO,
            pathname="", lineno=0,
            msg="[JOB-42] [PROCESSING] Writing solution files",
            args=(), exc_info=None,
        )
        handler.emit(record)

        # Give run_coroutine_threadsafe a chance to schedule
        await asyncio.sleep(0.05)

    asyncio.run(_run())

    assert len(captured) == 1
    assert captured[0]["job_id"] == "JOB-42"
    assert captured[0]["status"] == "PROCESSING"
    assert captured[0]["message"] == "Writing solution files"


def test_ws_handler_ignores_unmatched_log_records():
    """Handler must silently skip log lines not matching the NotificationTool format."""
    captured: list[dict] = []

    async def fake_broadcast(event: dict):
        captured.append(event)

    async def _run():
        loop = asyncio.get_event_loop()
        manager = ConnectionManager()
        handler = WebSocketNotificationHandler(manager=manager, loop=loop)
        manager.broadcast = fake_broadcast  # type: ignore[method-assign]

        record = logging.LogRecord(
            name="other.logger", level=logging.INFO,
            pathname="", lineno=0,
            msg="This does not match the expected format",
            args=(), exc_info=None,
        )
        handler.emit(record)
        await asyncio.sleep(0.05)

    asyncio.run(_run())
    assert len(captured) == 0


def test_ws_handler_payload_contains_no_secrets():
    """WebSocket events must never include api_key or secrets."""
    captured: list[dict] = []

    async def fake_broadcast(event: dict):
        captured.append(event)

    async def _run():
        loop = asyncio.get_event_loop()
        manager = ConnectionManager()
        handler = WebSocketNotificationHandler(manager=manager, loop=loop)
        manager.broadcast = fake_broadcast  # type: ignore[method-assign]

        record = logging.LogRecord(
            name=NOTIFICATION_LOGGER_NAME, level=logging.INFO,
            pathname="", lineno=0,
            msg="[JOB-99] [SUCCESS] Committed hash abc123",
            args=(), exc_info=None,
        )
        handler.emit(record)
        await asyncio.sleep(0.05)

    asyncio.run(_run())

    assert len(captured) == 1
    payload_text = json.dumps(captured[0])
    for bad_word in ("api_key", "secret", "password", "token"):
        assert bad_word not in payload_text


def test_ws_handler_multiple_clients_receive_same_event():
    """All connected clients receive the same broadcast event."""
    received_1: list[str] = []
    received_2: list[str] = []

    async def _run():
        manager = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws1.send_text.side_effect = lambda t: received_1.append(t)
        ws2.send_text.side_effect = lambda t: received_2.append(t)

        await manager.connect(ws1)
        await manager.connect(ws2)

        event = {"job_id": "MULTI", "status": "QUEUED", "message": "started"}
        await manager.broadcast(event)

    asyncio.run(_run())

    assert len(received_1) == 1
    assert len(received_2) == 1
    assert json.loads(received_1[0]) == json.loads(received_2[0])


# ── Integration: WebSocket endpoint via TestClient ─────────────────────────────

def test_websocket_client_can_connect():
    """TestClient can connect to the WS endpoint without errors."""
    from fastapi.testclient import TestClient
    from backend.api.app import app

    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/ws/notifications") as ws:
            assert app.state.ws_manager.active_count() == 1


def test_notification_tool_bridges_to_websocket_client():
    """NotificationTool.notify_status() must produce a JSON event at the WebSocket client.

    Production path under test:
        test-thread calls NotificationTool.notify_status()
        → GhostPush.NotificationTool logger
        → WebSocketNotificationHandler.emit()
        → asyncio.run_coroutine_threadsafe(broadcast, running_loop)
        → ConnectionManager.broadcast()
        → ws.send_text()
        → TestClient WebSocket receives text
    """
    from fastapi.testclient import TestClient
    from backend.api.app import app
    from mcp.notification_tool import NotificationTool

    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/ws/notifications") as ws:
            # Trigger notification from the test thread — emit() schedules
            # broadcast() onto the app's event loop via run_coroutine_threadsafe.
            NotificationTool.notify_status("BRIDGE-TEST", "PROCESSING", "Integration test msg")

            # receive_text() blocks until the app's event loop delivers the broadcast.
            raw = ws.receive_text()

    data = json.loads(raw)
    assert data["job_id"] == "BRIDGE-TEST"
    assert data["status"] == "PROCESSING"
    assert data["message"] == "Integration test msg"
    # Confirm no secrets leaked into the WebSocket payload
    for bad_key in ("api_key", "secret", "password", "token"):
        assert bad_key not in json.dumps(data)


def test_notification_tool_event_format_is_correct():
    """Confirm NotificationTool generates the log format we parse."""
    import re
    from mcp.notification_tool import NotificationTool

    _LOG_RE = re.compile(
        r"^\[(?P<job_id>[^\]]+)\]\s+\[(?P<status>[^\]]+)\]\s+(?P<message>.+)$"
    )

    with logging.handlers_capture() if False else _capture_log(NOTIFICATION_LOGGER_NAME) as records:
        NotificationTool.notify_status("FORMAT-CHECK", "WARNING", "test notification msg")

    assert len(records) >= 1
    last = records[-1]
    m = _LOG_RE.match(last.getMessage())
    assert m is not None, f"Log format mismatch: {last.getMessage()!r}"
    assert m.group("job_id") == "FORMAT-CHECK"
    assert m.group("status") == "WARNING"
    assert m.group("message") == "test notification msg"


# ── Helpers ────────────────────────────────────────────────────────────────────

class _capture_log:
    """Context manager that captures LogRecord objects from a named logger."""

    def __init__(self, logger_name: str):
        self._logger = logging.getLogger(logger_name)
        self._records: list[logging.LogRecord] = []
        self._handler = _ListHandler(self._records)

    def __enter__(self):
        self._logger.addHandler(self._handler)
        return self._records

    def __exit__(self, *_):
        self._logger.removeHandler(self._handler)


class _ListHandler(logging.Handler):
    def __init__(self, records: list):
        super().__init__()
        self._records = records

    def emit(self, record: logging.LogRecord) -> None:
        self._records.append(record)
