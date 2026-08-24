"""GhostPush Environment Validator and Setup Assistant.

Checks Python runtime compatibility, ensures required dependencies are available,
and initializes local .env from .env.example if missing.
"""

import importlib.util
import os
import shutil
import sys
from pathlib import Path
from typing import List, Optional, Tuple

REQUIRED_MODULES = [
    "fastapi",
    "uvicorn",
    "pystray",
    "PIL",
    "pydantic",
    "dotenv",
    "common",
]


def get_project_root() -> Path:
    """Resolve the absolute root directory of the GhostPush project."""
    return Path(__file__).resolve().parent.parent


def check_python_version() -> bool:
    """Return True if running on Python 3.12 or newer."""
    return sys.version_info >= (3, 12)


def check_dependencies() -> Tuple[bool, List[str]]:
    """Check availability of required runtime packages.

    Returns:
        Tuple of (all_present: bool, missing_modules: List[str])
    """
    missing: List[str] = []
    for module_name in REQUIRED_MODULES:
        try:
            spec = importlib.util.find_spec(module_name)
            if spec is None:
                missing.append(module_name)
        except (ImportError, AttributeError, ValueError):
            missing.append(module_name)

    return len(missing) == 0, missing


def get_target_env_dir(project_root: Optional[Path] = None) -> Path:
    """Return the destination directory for .env file.

    Normal dev mode: project_root
    Frozen mode: %APPDATA%/GhostPush (via get_config_dir)
    """
    if getattr(sys, "frozen", False):
        from backend.config.settings import get_config_dir
        return get_config_dir()
    return project_root or get_project_root()


def ensure_env_file(project_root: Optional[Path] = None) -> bool:
    """Ensure .env exists by copying .env.example if missing.

    Normal mode: project_root/.env
    Frozen mode: %APPDATA%/GhostPush/.env

    Preserves exact placeholder content from .env.example without inventing secrets.
    """
    target_dir = get_target_env_dir(project_root)
    env_file = target_dir / ".env"

    if env_file.exists():
        return True

    # Search for .env.example in project root or sys._MEIPASS if frozen
    example_file = (project_root or get_project_root()) / ".env.example"
    if not example_file.exists() and getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            example_file = Path(meipass) / ".env.example"

    if example_file.exists():
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(example_file, env_file)
            return True
        except OSError as e:
            print(f"[GhostPush Setup] Failed to copy .env.example: {e}", file=sys.stderr)
            return False

    return False


def setup_environment(project_root: Optional[Path] = None, verbose: bool = True) -> bool:
    """Run complete environment validation check.

    Returns True if the environment is valid and ready to run.
    """
    root = project_root or get_project_root()

    # Ensure project root is in sys.path
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    if not check_python_version():
        if verbose:
            print(
                f"[GhostPush Setup] Warning: Python 3.12+ is recommended. "
                f"Running on Python {sys.version_info.major}.{sys.version_info.minor}.",
                file=sys.stderr,
            )

    # Ensure .env exists
    ensure_env_file(root)

    # Check dependencies
    deps_ok, missing = check_dependencies()
    if not deps_ok:
        if verbose:
            print("[GhostPush Setup] Error: Missing required dependencies:", file=sys.stderr)
            for mod in missing:
                print(f"  - {mod}", file=sys.stderr)
            print(
                "\nPlease install missing dependencies using:\n"
                "  uv pip install -r requirements.txt\n"
                "or\n"
                "  pip install -r requirements.txt\n",
                file=sys.stderr,
            )
        return False

    return True


if __name__ == "__main__":
    success = setup_environment(verbose=True)
    if success:
        print("[GhostPush Setup] Environment validation successful.")
        sys.exit(0)
    else:
        sys.exit(1)
