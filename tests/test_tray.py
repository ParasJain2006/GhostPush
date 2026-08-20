from unittest.mock import MagicMock, patch

import pytest

from backend.config.manager import ConfigManager
from backend.config.models import AppSettings
from tray.backend_launcher import BackendLauncher
from tray.config_ui import HAS_TKINTER, TrayConfigDialog, TrayConfigHelper


# ── Launcher Tests (Phase 7.1) ─────────────────────────────────────────────────

def test_launcher_initial_state():
    launcher = BackendLauncher(host="127.0.0.1", port=8000)
    assert launcher.host == "127.0.0.1"
    assert launcher.port == 8000
    assert launcher.is_running() is False


def test_launcher_rejects_non_localhost_host():
    with pytest.raises(ValueError, match="127.0.0.1 or localhost"):
        BackendLauncher(host="0.0.0.0", port=8000)

    with pytest.raises(ValueError, match="192.168.1.100"):
        BackendLauncher(host="192.168.1.100", port=8000)


def test_launcher_accepts_localhost_variants():
    l1 = BackendLauncher(host="127.0.0.1", port=8000)
    assert l1.host == "127.0.0.1"

    l2 = BackendLauncher(host="localhost", port=8080)
    assert l2.host == "localhost"


def test_launcher_start_lifecycle_and_duplicate_protection():
    launcher = BackendLauncher()

    mock_server = MagicMock()
    with patch("uvicorn.Server", return_value=mock_server), \
         patch("threading.Thread") as mock_thread_cls:

        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        mock_thread_cls.return_value = mock_thread

        # First start succeeds
        started = launcher.start()
        assert started is True
        assert launcher.is_running() is True
        mock_thread.start.assert_called_once()

        # Second start attempt is blocked by duplicate protection
        second_start = launcher.start()
        assert second_start is False


def test_launcher_dev_mode_uses_string_target():
    launcher = BackendLauncher()
    mock_server = MagicMock()
    with patch("sys.frozen", False, create=True), \
         patch("uvicorn.Config") as mock_config_cls, \
         patch("uvicorn.Server", return_value=mock_server), \
         patch("threading.Thread"):
        launcher.start()
        mock_config_cls.assert_called_once()
        assert mock_config_cls.call_args.kwargs["app"] == "backend.api.app:app"


def test_launcher_frozen_mode_uses_app_instance():
    from backend.api.app import app as expected_app

    launcher = BackendLauncher()
    mock_server = MagicMock()
    with patch("sys.frozen", True, create=True), \
         patch("uvicorn.Config") as mock_config_cls, \
         patch("uvicorn.Server", return_value=mock_server), \
         patch("threading.Thread"):
        launcher.start()
        mock_config_cls.assert_called_once()
        assert mock_config_cls.call_args.kwargs["app"] is expected_app


def test_launcher_stop_lifecycle_and_repeated_stop_safety():
    launcher = BackendLauncher()

    mock_server = MagicMock()
    with patch("uvicorn.Server", return_value=mock_server), \
         patch("threading.Thread") as mock_thread_cls:

        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        mock_thread_cls.return_value = mock_thread

        launcher.start()
        assert launcher.is_running() is True

        # First stop signals server shutdown and joins thread
        stopped = launcher.stop()
        assert stopped is True
        assert mock_server.should_exit is True
        mock_thread.join.assert_called_once_with(timeout=5.0)

        # After stop, launcher references are cleaned up so is_running is False
        assert launcher.is_running() is False

        # Repeated stop when not running returns False safely
        second_stop = launcher.stop()
        assert second_stop is False


def test_launcher_start_failure_handling():
    launcher = BackendLauncher()

    with patch("uvicorn.Config", side_effect=RuntimeError("Invalid uvicorn config")):
        started = launcher.start()
        assert started is False
        assert launcher.is_running() is False


# ── Configuration UI Helper Tests (Phase 7.2 Headless) ─────────────────────────

def test_tray_config_helper_load_settings(tmp_path):
    config_file = tmp_path / "test_tray_config.json"
    mgr = ConfigManager(config_path=config_file)
    helper = TrayConfigHelper(config_manager=mgr)

    settings = helper.get_current_settings()
    assert isinstance(settings, AppSettings)
    assert settings.ai_provider == "gemini"


def test_tray_config_helper_update_valid_settings(tmp_path):
    config_file = tmp_path / "test_tray_config.json"
    mgr = ConfigManager(config_path=config_file)
    helper = TrayConfigHelper(config_manager=mgr)

    valid_dir = str(tmp_path.resolve())
    updates = {
        "repository_path": valid_dir,
        "ai_provider": "openai",
        "ai_model": "gpt-4o-mini",
        "log_level": "DEBUG",
        "auto_commit": True,
        "auto_push": False,
    }

    updated = helper.update_settings(updates)
    assert updated.ai_provider == "openai"
    assert updated.ai_model == "gpt-4o-mini"
    assert updated.log_level == "DEBUG"

    # Verify values returned contain no secret keys
    dumped = updated.model_dump()
    for k in dumped.keys():
        assert "api_key" not in k.lower()
        assert "secret" not in k.lower()


def test_tray_config_helper_rejects_invalid_configuration(tmp_path):
    config_file = tmp_path / "test_tray_config.json"
    mgr = ConfigManager(config_path=config_file)
    helper = TrayConfigHelper(config_manager=mgr)

    # Invalid repo directory
    with pytest.raises(Exception):
        helper.update_settings({"repository_path": "/invalid_path_12345_ghostpush"})

    # Invalid log level
    with pytest.raises(Exception):
        helper.update_settings({"log_level": "INVALID_LOG_LEVEL"})

    # Empty AI provider
    with pytest.raises(Exception):
        helper.update_settings({"ai_provider": "   "})


def test_tray_config_helper_rejects_secret_field_injection(tmp_path):
    config_file = tmp_path / "test_tray_config.json"
    mgr = ConfigManager(config_path=config_file)
    helper = TrayConfigHelper(config_manager=mgr)

    with pytest.raises(ValueError, match="cannot be persisted"):
        helper.update_settings({"api_key": "secret_key_val"})

    with pytest.raises(ValueError, match="cannot be persisted"):
        helper.update_settings({"OPENAI_API_KEY": "secret_key_val"})


def test_tray_config_dialog_raises_when_tkinter_unavailable():
    helper = MagicMock()
    with patch("tray.config_ui.HAS_TKINTER", False):
        with pytest.raises(RuntimeError, match="Tkinter is not installed or unavailable"):
            TrayConfigDialog(helper=helper)


# ── TrayApp Tests (Phase 7.3 Headless) ─────────────────────────────────────────

from tray.tray_app import HAS_PYSTRAY, TrayApp


def test_tray_app_construction_defaults():
    """TrayApp constructs with defaults without requiring a desktop."""
    app = TrayApp()
    assert app.launcher is not None
    assert app.config_helper is not None
    assert app._icon is None


def test_tray_app_construction_with_injection():
    """TrayApp accepts injected launcher and config_helper."""
    mock_launcher = MagicMock(spec=BackendLauncher)
    mock_helper = MagicMock(spec=TrayConfigHelper)
    app = TrayApp(launcher=mock_launcher, config_helper=mock_helper)
    assert app.launcher is mock_launcher
    assert app.config_helper is mock_helper


def test_tray_app_action_start_backend_delegates():
    """action_start_backend() calls launcher.start()."""
    mock_launcher = MagicMock(spec=BackendLauncher)
    mock_launcher.start.return_value = True
    app = TrayApp(launcher=mock_launcher)
    app.action_start_backend()
    mock_launcher.start.assert_called_once()


def test_tray_app_action_stop_backend_delegates():
    """action_stop_backend() calls launcher.stop()."""
    mock_launcher = MagicMock(spec=BackendLauncher)
    mock_launcher.stop.return_value = True
    app = TrayApp(launcher=mock_launcher)
    app.action_stop_backend()
    mock_launcher.stop.assert_called_once()


def test_tray_app_action_exit_stops_backend_and_icon():
    """action_exit() stops the backend and then stops the tray icon."""
    mock_launcher = MagicMock(spec=BackendLauncher)
    mock_icon = MagicMock()

    app = TrayApp(launcher=mock_launcher)
    app._icon = mock_icon

    app.action_exit()

    mock_launcher.stop.assert_called_once()
    mock_icon.stop.assert_called_once()


def test_tray_app_action_exit_safe_when_no_icon():
    """action_exit() does not crash when _icon is None (before run())."""
    mock_launcher = MagicMock(spec=BackendLauncher)
    app = TrayApp(launcher=mock_launcher)
    assert app._icon is None
    app.action_exit()  # must not raise
    mock_launcher.stop.assert_called_once()


def test_tray_app_action_open_config_spawns_thread():
    """action_open_config() spawns a daemon thread and does not block."""
    mock_launcher = MagicMock(spec=BackendLauncher)
    app = TrayApp(launcher=mock_launcher)

    threads_started = []
    real_thread_start = None

    class MockThread:
        def __init__(self, target, name, daemon):
            self.target = target
            self.name = name
            self.daemon = daemon

        def start(self):
            threads_started.append(self)

    with patch("tray.tray_app.threading.Thread", side_effect=MockThread):
        app.action_open_config()

    assert len(threads_started) == 1
    assert threads_started[0].name == "GhostPushConfigUIThread"
    assert threads_started[0].daemon is True


def test_tray_app_run_raises_when_pystray_unavailable():
    """run() raises RuntimeError when pystray/Pillow are not installed."""
    app = TrayApp()
    with patch("tray.tray_app.HAS_PYSTRAY", False):
        with pytest.raises(RuntimeError, match="pystray and Pillow are required"):
            app.run()


def test_tray_app_run_creates_icon_when_pystray_available():
    """run() builds the icon correctly when pystray is mocked."""
    mock_launcher = MagicMock(spec=BackendLauncher)
    mock_launcher.is_running.return_value = False
    app = TrayApp(launcher=mock_launcher)

    mock_image = MagicMock()
    mock_icon_instance = MagicMock()

    with patch("tray.tray_app.HAS_PYSTRAY", True), \
         patch("tray.tray_app._create_tray_icon_image", return_value=mock_image), \
         patch("tray.tray_app.pystray") as mock_pystray:

        mock_pystray.Icon.return_value = mock_icon_instance
        mock_icon_instance.run = MagicMock()

        app.run()

        mock_pystray.Icon.assert_called_once()
        mock_icon_instance.run.assert_called_once()
        assert app._icon is mock_icon_instance


def test_tray_app_dynamic_status_text():
    """_get_status_text() dynamically returns Status: Running or Status: Stopped."""
    mock_launcher = MagicMock(spec=BackendLauncher)
    mock_launcher.is_running.return_value = False
    app = TrayApp(launcher=mock_launcher)

    assert app._get_status_text() == "Status: Stopped"

    mock_launcher.is_running.return_value = True
    assert app._get_status_text() == "Status: Running"


def test_tray_app_actions_trigger_menu_refresh():
    """action_start_backend and action_stop_backend refresh the menu via update_menu()."""
    mock_launcher = MagicMock(spec=BackendLauncher)
    mock_icon = MagicMock()

    app = TrayApp(launcher=mock_launcher)
    app._icon = mock_icon

    app.action_start_backend()
    mock_icon.update_menu.assert_called_once()

    mock_icon.reset_mock()
    app.action_stop_backend()
    mock_icon.update_menu.assert_called_once()

