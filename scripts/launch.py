"""Official GhostPush Application Entrypoint.

Validates runtime environment, sets up project paths, and launches the
System Tray Application (TrayApp), which manages the backend lifecycle.
"""

import multiprocessing
import sys
from pathlib import Path

# Add project root to sys.path before any local package imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.setup_env import setup_environment


def main() -> int:
    """Main launcher entrypoint."""
    # 0. Windows PyInstaller freeze support
    multiprocessing.freeze_support()

    # 1. Environment validation
    if not setup_environment(project_root=PROJECT_ROOT, verbose=True):
        print("[GhostPush Launcher] Environment check failed. Aborting launch.", file=sys.stderr)
        return 1

    # 2. Launch TrayApp (which manages BackendLauncher and UI)
    try:
        from tray.tray_app import TrayApp

        app = TrayApp()
        print("[GhostPush Launcher] Launching GhostPush System Tray Application...")
        app.run()
        return 0
    except RuntimeError as e:
        print(f"[GhostPush Launcher] Runtime error during startup: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[GhostPush Launcher] Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
