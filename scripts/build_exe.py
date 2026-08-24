"""Automated PyInstaller Executable Builder for GhostPush.

Runs PyInstaller using ghostpush.spec and verifies output files in dist/GhostPush.
"""

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def build_executable() -> bool:
    """Execute PyInstaller build and verify artifact output."""
    spec_file = PROJECT_ROOT / "ghostpush.spec"
    if not spec_file.exists():
        print(f"[GhostPush Build] Error: Spec file missing at {spec_file}", file=sys.stderr)
        return False

    print(f"[GhostPush Build] Running PyInstaller build using {spec_file.name}...")
    cmd = [sys.executable, "-m", "PyInstaller", str(spec_file), "--noconfirm"]

    try:
        res = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        if res.returncode != 0:
            print("[GhostPush Build] PyInstaller build failed with stdout/stderr:", file=sys.stderr)
            print(res.stdout, file=sys.stderr)
            print(res.stderr, file=sys.stderr)
            return False
    except Exception as e:
        print(f"[GhostPush Build] Exception during build process: {e}", file=sys.stderr)
        return False

    # Verification — PyInstaller 6.x places datas inside _internal/
    dist_dir = PROJECT_ROOT / "dist" / "GhostPush"
    exe_file = dist_dir / "GhostPush.exe"
    internal_dir = dist_dir / "_internal"
    ext_dir = internal_dir / "extension"

    if not exe_file.exists():
        print(f"[GhostPush Build] Error: Expected binary missing at {exe_file}", file=sys.stderr)
        return False

    if not (ext_dir / "manifest.json").exists():
        # Fallback: check dist root for older PyInstaller layouts
        ext_dir_fallback = dist_dir / "extension"
        if not (ext_dir_fallback / "manifest.json").exists():
            print(f"[GhostPush Build] Error: Bundled extension missing at {ext_dir}", file=sys.stderr)
            return False
        ext_dir = ext_dir_fallback

    print(f"[GhostPush Build] Build successful! Output generated at: {dist_dir}")
    return True


if __name__ == "__main__":
    success = build_executable()
    sys.exit(0 if success else 1)
