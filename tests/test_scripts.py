"""Unit tests for Phase 8 launch and setup automation scripts."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.setup_env import (
    check_dependencies,
    check_python_version,
    ensure_env_file,
    get_project_root,
    setup_environment,
)


def test_get_project_root_resolves_actual_root():
    root = get_project_root()
    assert isinstance(root, Path)
    assert root.exists()
    assert (root / "scripts").exists()
    assert (root / "backend").exists()


def test_check_python_version_valid():
    # Test suite runs on Python 3.12+
    assert check_python_version() is True


def test_ensure_env_file_creates_env_from_example_if_missing(tmp_path):
    example_content = "# Test .env example\nGEMINI_API_KEY=\n"
    example_file = tmp_path / ".env.example"
    env_file = tmp_path / ".env"

    example_file.write_text(example_content, encoding="utf-8")
    assert not env_file.exists()

    result = ensure_env_file(project_root=tmp_path)
    assert result is True
    assert env_file.exists()
    assert env_file.read_text(encoding="utf-8") == example_content


def test_ensure_env_file_does_not_overwrite_existing(tmp_path):
    example_file = tmp_path / ".env.example"
    env_file = tmp_path / ".env"

    example_file.write_text("KEY=EXAMPLE", encoding="utf-8")
    env_file.write_text("KEY=EXISTING_CUSTOM", encoding="utf-8")

    result = ensure_env_file(project_root=tmp_path)
    assert result is True
    assert env_file.read_text(encoding="utf-8") == "KEY=EXISTING_CUSTOM"


def test_ensure_env_file_preserves_placeholders_and_injects_no_secrets(tmp_path):
    example_file = tmp_path / ".env.example"
    env_file = tmp_path / ".env"

    example_content = "GEMINI_API_KEY=your_gemini_api_key_here\nOPENAI_API_KEY=\n"
    example_file.write_text(example_content, encoding="utf-8")

    ensure_env_file(project_root=tmp_path)
    created_content = env_file.read_text(encoding="utf-8")

    assert created_content == example_content
    # Confirm no real secret values were hardcoded
    assert "your_gemini_api_key_here" in created_content
    assert "sk-" not in created_content


def test_check_dependencies_detects_missing_module():
    with patch("importlib.util.find_spec") as mock_find_spec:
        mock_find_spec.side_effect = lambda name: None if name == "pystray" else MagicMock()
        all_ok, missing = check_dependencies()

    assert all_ok is False
    assert "pystray" in missing


def test_setup_environment_returns_true_when_valid(tmp_path):
    example_file = tmp_path / ".env.example"
    example_file.write_text("FOO=BAR", encoding="utf-8")

    with patch("scripts.setup_env.check_dependencies", return_value=(True, [])):
        res = setup_environment(project_root=tmp_path, verbose=False)
        assert res is True


def test_launch_py_delegates_to_tray_app():
    from scripts.launch import main

    mock_app_cls = MagicMock()
    mock_app_instance = MagicMock()
    mock_app_cls.return_value = mock_app_instance

    with patch("scripts.setup_env.setup_environment", return_value=True), \
         patch.dict("sys.modules", {"tray.tray_app": MagicMock(TrayApp=mock_app_cls)}):

        exit_code = main()
        assert exit_code == 0
        mock_app_cls.assert_called_once()
        mock_app_instance.run.assert_called_once()


def test_launch_py_no_duplicate_backend_launcher_logic():
    """Verify launch.py does not start uvicorn directly or bypass TrayApp."""
    import scripts.launch as launch_mod

    content = Path(launch_mod.__file__).read_text(encoding="utf-8")
    assert "uvicorn.run" not in content
    assert "from tray.backend_launcher" not in content
    assert "BackendLauncher(" not in content


def test_start_ghostpush_bat_exists_and_references_launch_py():
    bat_file = get_project_root() / "scripts" / "start_ghostpush.bat"
    assert bat_file.exists()

    content = bat_file.read_text(encoding="utf-8")
    assert "launch.py" in content
    # Verify no hardcoded absolute user paths
    assert "C:\\Users\\" not in content
    assert "T:\\" not in content


def test_ensure_env_file_in_frozen_mode_uses_config_dir(tmp_path):
    mock_appdata_dir = tmp_path / "appdata_ghostpush"
    example_file = tmp_path / ".env.example"
    example_file.write_text("FROZEN_KEY=PLACEHOLDER", encoding="utf-8")

    with patch("sys.frozen", True, create=True), \
         patch("backend.config.settings.get_config_dir", return_value=mock_appdata_dir):

        result = ensure_env_file(project_root=tmp_path)
        assert result is True

        frozen_env_file = mock_appdata_dir / ".env"
        assert frozen_env_file.exists()
        assert frozen_env_file.read_text(encoding="utf-8") == "FROZEN_KEY=PLACEHOLDER"


def test_launch_py_calls_multiprocessing_freeze_support():
    from scripts.launch import main

    mock_app_cls = MagicMock()
    mock_app_instance = MagicMock()
    mock_app_cls.return_value = mock_app_instance

    with patch("multiprocessing.freeze_support") as mock_freeze_support, \
         patch("scripts.setup_env.setup_environment", return_value=True), \
         patch.dict("sys.modules", {"tray.tray_app": MagicMock(TrayApp=mock_app_cls)}):

        main()
        mock_freeze_support.assert_called_once()

