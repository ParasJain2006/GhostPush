import json
import pytest

from common.errors import GhostPushError
from backend.config.models import AppSettings
from backend.config.manager import ConfigManager
from backend.config.settings import get_config_dir, get_config_file_path


def test_app_settings_validation_success(tmp_path):
    repo_dir = tmp_path / "my_repo"
    repo_dir.mkdir()

    settings = AppSettings(
        repository_path=str(repo_dir),
        ai_provider="gemini",
        api_port=8000,
        log_level="INFO",
    )
    assert settings.repository_path == str(repo_dir)
    assert settings.ai_provider == "gemini"
    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 8000
    assert settings.log_level == "INFO"


def test_invalid_repository_path_rejected():
    with pytest.raises(ValueError, match="repository_path must be an existing directory"):
        AppSettings(
            repository_path="/non_existent_path_ghostpush_test_12345",
            ai_provider="gemini",
        )


def test_invalid_api_port_rejected(tmp_path):
    repo_dir = tmp_path / "my_repo"
    repo_dir.mkdir()

    with pytest.raises(ValueError, match="api_port must be between 1 and 65535"):
        AppSettings(
            repository_path=str(repo_dir),
            ai_provider="gemini",
            api_port=70000,
        )


def test_invalid_log_level_rejected(tmp_path):
    repo_dir = tmp_path / "my_repo"
    repo_dir.mkdir()

    with pytest.raises(ValueError, match="log_level must be one of"):
        AppSettings(
            repository_path=str(repo_dir),
            ai_provider="gemini",
            log_level="VERBOSE",
        )


def test_config_manager_save_and_load_round_trip(tmp_path):
    config_file = tmp_path / "config.json"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    manager = ConfigManager(config_path=config_file)
    settings = AppSettings(
        repository_path=str(repo_dir),
        remote_repo_url="https://github.com/example/repo.git",
        ai_provider="openai",
        ai_model="gpt-4o-mini",
        theme="light",
    )

    manager.save_config(settings)
    assert config_file.exists()

    loaded = manager.load_config()
    assert loaded.repository_path == str(repo_dir)
    assert loaded.remote_repo_url == "https://github.com/example/repo.git"
    assert loaded.ai_provider == "openai"
    assert loaded.ai_model == "gpt-4o-mini"
    assert loaded.theme == "light"


def test_config_manager_update_config(tmp_path):
    config_file = tmp_path / "config.json"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    manager = ConfigManager(config_path=config_file)
    initial_settings = AppSettings(
        repository_path=str(repo_dir),
        ai_provider="gemini",
        theme="dark",
    )
    manager.save_config(initial_settings)

    updated = manager.update_config({"theme": "light", "notifications": False})
    assert updated.theme == "light"
    assert updated.notifications is False

    loaded = manager.load_config()
    assert loaded.theme == "light"
    assert loaded.notifications is False


def test_api_key_loaded_from_environment(tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    manager = ConfigManager(config_path=config_file)

    monkeypatch.setenv("GEMINI_API_KEY", "secret_gemini_key_12345")
    monkeypatch.setenv("OPENAI_API_KEY", "secret_openai_key_67890")

    assert manager.get_api_key("gemini") == "secret_gemini_key_12345"
    assert manager.get_api_key("openai") == "secret_openai_key_67890"
    assert manager.get_api_key("non_existent_provider") is None


def test_api_key_not_present_in_config_json(tmp_path):
    config_file = tmp_path / "config.json"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    manager = ConfigManager(config_path=config_file)
    settings = AppSettings(
        repository_path=str(repo_dir),
        ai_provider="gemini",
    )
    manager.save_config(settings)

    raw_data = json.loads(config_file.read_text(encoding="utf-8"))
    assert "api_key" not in raw_data
    assert "GEMINI_API_KEY" not in raw_data
    assert "OPENAI_API_KEY" not in raw_data


def test_secret_fields_cannot_be_persisted(tmp_path):
    config_file = tmp_path / "config.json"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    manager = ConfigManager(config_path=config_file)
    settings = AppSettings(
        repository_path=str(repo_dir),
        ai_provider="gemini",
    )
    manager.save_config(settings)

    with pytest.raises(ValueError, match="Secret field"):
        manager.update_config({"api_key": "my_secret_key"})

    with pytest.raises(ValueError, match="Secret field"):
        manager.update_config({"GEMINI_API_KEY": "my_secret_key"})


def test_missing_config_behavior(tmp_path):
    non_existent_file = tmp_path / "subdir" / "config.json"
    manager = ConfigManager(config_path=non_existent_file)

    # Missing file returns valid defaults
    config = manager.load_config()
    assert isinstance(config, AppSettings)
    assert config.api_host == "127.0.0.1"
    assert config.api_port == 8000
    assert config.ai_provider == "gemini"


def test_path_resolution_helpers():
    config_dir = get_config_dir()
    config_file = get_config_file_path()
    assert config_dir.name in ("GhostPush", "ghostpush")
    assert config_file.name == "config.json"
