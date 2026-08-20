"""Unit tests for Phase 9.2 packaging configuration and PyInstaller spec."""

from pathlib import Path
from PIL import Image

from scripts.setup_env import get_project_root


def test_ghostpush_ico_exists_and_valid():
    root = get_project_root()
    ico_path = root / "ghostpush.ico"
    assert ico_path.exists()

    with Image.open(ico_path) as img:
        assert img.format == "ICO"
        assert img.size[0] > 0


def test_ghostpush_spec_exists_and_valid():
    root = get_project_root()
    spec_path = root / "ghostpush.spec"
    assert spec_path.exists()

    content = spec_path.read_text(encoding="utf-8")

    # Verify datas mappings
    assert "extension" in content
    assert ".env.example" in content

    # Verify key hidden imports
    assert "uvicorn.logging" in content
    assert "pystray._win32" in content
    assert "PIL._imaging" in content
    assert "tkinter" in content
    assert "fastapi" in content
    assert "backend.api.app" in content

    # Verify output binary name and icon
    assert "GhostPush" in content
    assert "ghostpush.ico" in content


def test_build_exe_script_exists_and_references_spec():
    root = get_project_root()
    build_script = root / "scripts" / "build_exe.py"
    assert build_script.exists()

    content = build_script.read_text(encoding="utf-8")
    assert "ghostpush.spec" in content
    assert "PyInstaller" in content
