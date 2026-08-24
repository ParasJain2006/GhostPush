"""Unit and integration tests for Phase 10.4.1 — User-Friendly AI API Key Configuration."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.config.manager import ConfigManager, PROVIDER_ENV_MAP
from backend.db.repository import JobRepository
from common.schemas import ProblemInfo, SolutionInfo, SubmissionPayload
from tray.config_ui import TrayConfigHelper, TrayConfigDialog, HAS_TKINTER


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Fixture providing isolated config directory and environment."""
    cfg_dir = tmp_path / "GhostPush"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = cfg_dir / "config.json"
    env_file = cfg_dir / ".env"

    monkeypatch.setattr("backend.config.manager.get_config_dir", lambda: cfg_dir)
    monkeypatch.setattr("backend.config.settings.get_config_dir", lambda: cfg_dir)
    monkeypatch.setattr("backend.config.manager.get_config_file_path", lambda: cfg_file)

    # Clean provider env vars from process environment for test isolation
    for env_var in PROVIDER_ENV_MAP.values():
        monkeypatch.delenv(env_var, raising=False)

    return cfg_dir


def test_set_api_key_writes_to_env_file_and_os_environ(temp_config_dir):
    """Verify set_api_key writes key to .env and updates os.environ immediately."""
    cfg_file = temp_config_dir / "config.json"
    mgr = ConfigManager(config_path=cfg_file)

    test_key = "AIzaSy-test-gemini-key-12345"
    mgr.set_api_key("gemini", test_key)

    env_file = temp_config_dir / ".env"
    assert env_file.exists()
    content = env_file.read_text(encoding="utf-8")
    assert f"GEMINI_API_KEY={test_key}" in content
    assert os.getenv("GEMINI_API_KEY") == test_key
    assert mgr.get_api_key("gemini") == test_key


def test_set_api_key_preserves_existing_comments_and_entries(temp_config_dir):
    """Verify set_api_key preserves comments and other provider keys in .env."""
    env_file = temp_config_dir / ".env"
    initial_content = (
        "# Custom comment header\n"
        "OPENAI_API_KEY=sk-test-existing-openai\n"
        "DEFAULT_AI_PROVIDER=gemini\n"
    )
    env_file.write_text(initial_content, encoding="utf-8")

    cfg_file = temp_config_dir / "config.json"
    mgr = ConfigManager(config_path=cfg_file)

    mgr.set_api_key("gemini", "AIzaSy-new-gemini-key")

    lines = env_file.read_text(encoding="utf-8").splitlines()
    assert "# Custom comment header" in lines
    assert "OPENAI_API_KEY=sk-test-existing-openai" in lines
    assert "DEFAULT_AI_PROVIDER=gemini" in lines
    assert "GEMINI_API_KEY=AIzaSy-new-gemini-key" in lines


def test_provider_switching_env_var_mapping(temp_config_dir):
    """Verify provider switching correctly uses defined PROVIDER_ENV_MAP."""
    cfg_file = temp_config_dir / "config.json"
    mgr = ConfigManager(config_path=cfg_file)

    providers = {
        "gemini": ("GEMINI_API_KEY", "key-gemini-111"),
        "openai": ("OPENAI_API_KEY", "key-openai-222"),
        "anthropic": ("ANTHROPIC_API_KEY", "key-anthropic-333"),
        "groq": ("GROQ_API_KEY", "key-groq-444"),
        "openrouter": ("OPENROUTER_API_KEY", "key-openrouter-555"),
    }

    for p_name, (env_var, secret) in providers.items():
        mgr.set_api_key(p_name, secret)
        assert os.getenv(env_var) == secret
        assert mgr.get_api_key(p_name) == secret


def test_config_json_remains_secret_free(temp_config_dir):
    """Verify config.json never contains secret keys after setting API key and saving settings."""
    cfg_file = temp_config_dir / "config.json"
    mgr = ConfigManager(config_path=cfg_file)

    mgr.set_api_key("gemini", "AIzaSy-secret-key-to-not-persist-in-json")
    mgr.update_config({"ai_provider": "gemini", "ai_model": "gemini-1.5-flash"})

    assert cfg_file.exists()
    json_text = cfg_file.read_text(encoding="utf-8")
    assert "AIzaSy-secret-key-to-not-persist-in-json" not in json_text
    assert "api_key" not in json_text
    assert "gemini_api_key" not in json_text


def test_get_config_rest_endpoint_never_exposes_secret_keys(temp_config_dir):
    """Verify GET /api/v1/config REST endpoint never exposes API keys."""
    cfg_file = temp_config_dir / "config.json"
    mgr = ConfigManager(config_path=cfg_file)
    mgr.set_api_key("openai", "sk-secret-key-999")

    with TestClient(app) as client:
        res = client.get("/api/v1/config")
        assert res.status_code == 200
        data = res.json()
        assert "api_key" not in data
        assert "openai_api_key" not in data
        assert "sk-secret-key-999" not in str(data)


def test_sqlite_job_repository_never_persists_api_key(tmp_path):
    """Verify sqlite repository strips api_key before saving job payload."""
    db_file = tmp_path / "test_ghostpush.db"
    repo = JobRepository(db_path=db_file)

    payload = SubmissionPayload(
        job_id="JOB-SECRET-TEST-1",
        platform="leetcode",
        problem=ProblemInfo(title="Two Sum"),
        solution=SolutionInfo(language="python", code="pass"),
        api_key="SUPER_SECRET_KEY_123",
    )

    record = repo.create_job(payload)
    persisted = repo.get_job("JOB-SECRET-TEST-1")

    assert record is not None
    assert persisted is not None
    payload_dict = persisted.get("payload", {})
    assert "api_key" not in payload_dict
    assert "SUPER_SECRET_KEY_123" not in str(persisted)


def test_tray_config_helper_delegates_get_and_set_api_key(temp_config_dir, monkeypatch):
    """Verify TrayConfigHelper correctly delegates get_api_key and set_api_key."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    cfg_file = temp_config_dir / "config.json"
    mgr = ConfigManager(config_path=cfg_file)
    helper = TrayConfigHelper(config_manager=mgr)

    helper.set_api_key("groq", "gsk_test_groq_key_777")
    assert helper.get_api_key("groq") == "gsk_test_groq_key_777"
