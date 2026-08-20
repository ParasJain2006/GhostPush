"""Backend server launcher for GhostPush tray application.

Manages starting, stopping, and monitoring the FastAPI backend server on localhost.
"""

import datetime
import logging
import os
import sys
import threading
import traceback
from typing import Optional

import uvicorn

logger = logging.getLogger("GhostPush.Tray.Launcher")


def _write_error_log(component: str, tb: str) -> None:
    """Persist a backend startup/runtime failure to backend_error.log.

    Diagnostic capture: backend-start exceptions are invisible in console=False
    (windowed) builds, so any failure is recorded to the config directory.
    """
    try:
        from backend.config.settings import get_config_dir

        log_path = get_config_dir() / "backend_error.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n===== {component} {datetime.datetime.now().isoformat()} =====\n{tb}\n")
    except BaseException:
        pass


class BackendLauncher:
    """Controls the background lifecycle of the GhostPush FastAPI server."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8000):
        if host not in ("127.0.0.1", "localhost"):
            raise ValueError(f"Backend API must bind to 127.0.0.1 or localhost, got: {host!r}")
        self.host = host
        self.port = port
        self._server: Optional[uvicorn.Server] = None
        self._thread: Optional[threading.Thread] = None

    def is_running(self) -> bool:
        """Return True if the backend server thread is active."""
        if self._thread is None or not self._thread.is_alive():
            return False
        return True

    def _run_server(self) -> None:
        """Run the uvicorn server, capturing any failure to backend_error.log."""
        try:
            if self._server is None:
                raise RuntimeError("No server instance available.")
            self._server.run()
        except BaseException:
            _write_error_log("backend_thread", traceback.format_exc())
            raise

    def start(self) -> bool:
        """Start the FastAPI backend server in a background thread."""
        if self.is_running():
            logger.warning("Backend server is already running.")
            return False

        try:
            if getattr(sys, "frozen", False):
                from backend.api.app import app
                app_target = app
            else:
                app_target = "backend.api.app:app"

            # Windowed (console=False) builds run with sys.stdout/sys.stderr
            # set to None; uvicorn's dictConfig (ColourizedFormatter.isatty)
            # raises on None. Substitute discard streams so it can configure.
            if sys.stdout is None:
                sys.stdout = open(os.devnull, "w", encoding="utf-8")
            if sys.stderr is None:
                sys.stderr = open(os.devnull, "w", encoding="utf-8")

            config = uvicorn.Config(
                app=app_target,
                host=self.host,
                port=self.port,
                log_level="info",
                reload=False,
            )
            self._server = uvicorn.Server(config)
            self._thread = threading.Thread(
                target=self._run_server,
                name="GhostPushBackendServerThread",
                daemon=True,
            )
            self._thread.start()
            return True
        except Exception as e:
            logger.error(f"Failed to start backend server: {e}")
            _write_error_log("start", traceback.format_exc())
            self._server = None
            self._thread = None
            return False

    def stop(self) -> bool:
        """Signal the background backend server to shut down cleanly."""
        if not self.is_running():
            return False

        try:
            if self._server is not None:
                self._server.should_exit = True
            if self._thread is not None and self._thread.is_alive():
                self._thread.join(timeout=5.0)
            return True
        except Exception as e:
            logger.error(f"Error while stopping backend server: {e}")
            return False
        finally:
            self._server = None
            self._thread = None
