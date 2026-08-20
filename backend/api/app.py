import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn

from backend.config.manager import ConfigManager
from backend.jobs.queue import JobQueue
from backend.jobs.worker import JobWorker
from backend.api.routes import config_router, health_router, jobs_router
from backend.api.websocket import (
    ConnectionManager,
    NOTIFICATION_LOGGER_NAME,
    WebSocketNotificationHandler,
)


logger = logging.getLogger("GhostPush.API")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────────────────────
    logger.info("Starting GhostPush API...")

    config_mgr = ConfigManager()
    queue = JobQueue()
    worker = JobWorker(
        queue=queue,
        poll_interval=0.5,
        api_key_resolver=config_mgr.get_api_key,
        config_manager=config_mgr,
    )
    worker.start()

    # WebSocket notification bridge
    ws_manager = ConnectionManager()
    loop = asyncio.get_running_loop()
    ws_handler = WebSocketNotificationHandler(manager=ws_manager, loop=loop)

    notification_logger = logging.getLogger(NOTIFICATION_LOGGER_NAME)
    notification_logger.addHandler(ws_handler)

    # Store in app state
    app.state.config_mgr = config_mgr
    app.state.queue = queue
    app.state.worker = worker
    app.state.ws_manager = ws_manager

    yield

    # ── Shutdown ───────────────────────────────────────────────────────────────
    logger.info("Shutting down GhostPush API...")

    # Remove logging handler cleanly
    notification_logger.removeHandler(ws_handler)

    # Stop worker
    worker.stop()
    worker.join(timeout=5.0)


app = FastAPI(
    title="GhostPush API",
    version="1.0",
    lifespan=lifespan,
)

app.include_router(health_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(config_router, prefix="/api/v1")


@app.websocket("/api/v1/ws/notifications")
async def websocket_notifications(ws: WebSocket):
    """WebSocket endpoint that streams NotificationTool events to connected clients."""
    manager: ConnectionManager = ws.app.state.ws_manager
    await manager.connect(ws)
    try:
        while True:
            # Keep connection alive; we only push, never expect client messages.
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)


def run_api():
    """Run the FastAPI application with uvicorn on localhost."""
    uvicorn.run("backend.api.app:app", host="127.0.0.1", port=8000, reload=False)
