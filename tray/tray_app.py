"""GhostPush System Tray Application.

Creates a system tray icon with a menu for controlling the backend server,
accessing configuration, and exiting. Uses BackendLauncher and TrayConfigHelper
from the existing tray package. Requires pystray and Pillow at runtime.
"""

import logging
import threading
from typing import Optional

logger = logging.getLogger("GhostPush.Tray.App")

# Guard pystray and Pillow imports so the module is importable in headless
# environments and tests without a real desktop/tray available.
try:
    import pystray
    from pystray import MenuItem as item, Menu
    from PIL import Image, ImageDraw
    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False

from tray.backend_launcher import BackendLauncher
from tray.config_ui import HAS_TKINTER, TrayConfigDialog, TrayConfigHelper


def _create_tray_icon_image(size: int = 64) -> "Image.Image":
    """Generate a simple GhostPush tray icon image using Pillow.

    Returns a square RGBA image with a filled circle on a transparent background.
    Pillow must be available (guaranteed by the HAS_PYSTRAY guard in the caller).
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Indigo circle background
    draw.ellipse((2, 2, size - 2, size - 2), fill=(99, 102, 241, 255))
    # White "G" initial
    draw.text((size // 2 - 8, size // 2 - 10), "G", fill=(255, 255, 255, 255))
    return img


class TrayApp:
    """System tray application for GhostPush.

    Wraps pystray.Icon and wires menu actions to BackendLauncher and
    TrayConfigHelper without duplicating any backend or configuration logic.
    """

    def __init__(
        self,
        launcher: Optional[BackendLauncher] = None,
        config_helper: Optional[TrayConfigHelper] = None,
    ):
        self.launcher = launcher or BackendLauncher()
        self.config_helper = config_helper or TrayConfigHelper()
        self._icon: Optional["pystray.Icon"] = None

    def _get_status_text(self, item: Optional[object] = None) -> str:
        """Return dynamic status text reflecting current backend launcher state."""
        return "Status: Running" if self.launcher.is_running() else "Status: Stopped"

    def _refresh_menu(self, icon: Optional[object] = None) -> None:
        """Refresh tray menu so status and item text reflect current state immediately."""
        target_icon = icon or self._icon
        if target_icon is not None and hasattr(target_icon, "update_menu"):
            try:
                target_icon.update_menu()
            except Exception as e:
                logger.debug(f"Failed to update menu: {e}")

    # ── Menu action delegates ──────────────────────────────────────────────────

    def action_start_backend(self, icon: Optional[object] = None, item: Optional[object] = None) -> None:
        """Start the FastAPI backend via BackendLauncher."""
        result = self.launcher.start()
        if result:
            logger.info("Backend started from tray.")
        else:
            logger.warning("Backend was already running or failed to start.")
        self._refresh_menu(icon)

    def action_stop_backend(self, icon: Optional[object] = None, item: Optional[object] = None) -> None:
        """Stop the FastAPI backend via BackendLauncher."""
        result = self.launcher.stop()
        if result:
            logger.info("Backend stopped from tray.")
        else:
            logger.warning("Backend was not running.")
        self._refresh_menu(icon)

    def action_open_config(self, icon: Optional[object] = None, item: Optional[object] = None) -> None:
        """Open the TrayConfigDialog on a dedicated thread to avoid blocking the tray loop."""
        def _open():
            try:
                dialog = TrayConfigDialog(helper=self.config_helper)
                dialog.open()
            except RuntimeError as e:
                logger.warning(f"Cannot open configuration dialog: {e}")

        t = threading.Thread(target=_open, name="GhostPushConfigUIThread", daemon=True)
        t.start()

    def action_exit(self, icon: Optional[object] = None, item: Optional[object] = None) -> None:
        """Stop the backend cleanly, then stop the tray icon."""
        logger.info("Exit requested from tray menu.")
        self.launcher.stop()
        if self._icon is not None:
            self._icon.stop()

    # ── Menu construction ──────────────────────────────────────────────────────

    def _build_menu(self) -> "pystray.Menu":
        """Construct and return the pystray tray menu."""
        return Menu(
            item(
                self._get_status_text,
                action=None,
                enabled=False,
            ),
            Menu.SEPARATOR,
            item("Start Backend", self.action_start_backend),
            item("Stop Backend", self.action_stop_backend),
            Menu.SEPARATOR,
            item("Configuration", self.action_open_config),
            Menu.SEPARATOR,
            item("Exit", self.action_exit),
        )

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Create and run the system tray icon (blocking call on the calling thread).

        Raises RuntimeError if pystray or Pillow is unavailable.
        """
        if not HAS_PYSTRAY:
            raise RuntimeError(
                "pystray and Pillow are required to run the GhostPush system tray application. "
                "Install them with: pip install pystray Pillow"
            )

        icon_image = _create_tray_icon_image()
        self._icon = pystray.Icon(
            name="GhostPush",
            icon=icon_image,
            title="GhostPush",
            menu=self._build_menu(),
        )
        logger.info("Starting GhostPush system tray icon.")
        self._icon.run()

    def stop(self) -> None:
        """Stop the tray icon programmatically (useful for tests and clean shutdown)."""
        self.launcher.stop()
        if self._icon is not None:
            self._icon.stop()
            self._icon = None
