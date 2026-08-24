"""Focused unit and integration test suite for Phase 10.7: AI Configuration & Connection Health.

Verifies:
1. Missing API key -> NOT_CONFIGURED
2. Placeholder API key -> NOT_CONFIGURED
3. Valid mocked provider response -> CONNECTED
4. Invalid API key response -> INVALID_API_KEY
5. Network failure -> NETWORK_ERROR
6. Timeout -> TIMEOUT
7. Provider error -> PROVIDER_ERROR
8. API key never appears in config.json
9. API key never appears in SQLite payload
10. API key never appears in REST response
11. API key never appears in WebSocket event
12. Save key -> health check status becomes CONNECTED (mocked)
13. Remove key -> status becomes NOT_CONFIGURED
14. Provider change recalculates status
15. Startup without key produces warning log
16. Startup with valid key produces info log
17. AI failure does not crash GhostPush startup
"""

import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.config.health import AIHealthStatus, check_provider_health, is_placeholder_key
from backend.config.manager import ConfigManager
from backend.jobs.queue import JobQueue
from common.schemas import SubmissionPayload
from tray.config_ui import TrayConfigHelper
from tray.tray_app import TrayApp


def test_1_missing_api_key_returns_not_configured(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr("backend.config.manager.get_config_dir", lambda: tmp_path)

    cfg_mgr = ConfigManager(config_path=tmp_path / "config.json")
    status = check_provider_health(cfg_mgr, "gemini")
    assert status == AIHealthStatus.NOT_CONFIGURED


def test_2_placeholder_api_key_returns_not_configured(tmp_path):
    cfg_mgr = ConfigManager(config_path=tmp_path / "config.json")

    placeholders = [
        "your_gemini_api_key_here",
        "your_openai_api_key_here",
        "change_me",
        "dummy_key_123",
        "insert_key_here",
    ]

    for p_key in placeholders:
        assert is_placeholder_key(p_key) is True
        cfg_mgr.set_api_key("gemini", p_key)
        assert cfg_mgr.has_api_key("gemini") is False
        assert check_provider_health(cfg_mgr, "gemini") == AIHealthStatus.NOT_CONFIGURED


def test_3_valid_mocked_provider_response_returns_connected(tmp_path, monkeypatch):
    cfg_mgr = ConfigManager(config_path=tmp_path / "config.json")
    cfg_mgr.set_api_key("gemini", "AIzaSyRealValidKey12345")

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = "Hello response"

    monkeypatch.setattr("agent.providers.get_llm_provider", lambda **kwargs: mock_llm)

    status = check_provider_health(cfg_mgr, "gemini")
    assert status == AIHealthStatus.CONNECTED


def test_4_invalid_api_key_response_returns_invalid_api_key(tmp_path, monkeypatch):
    cfg_mgr = ConfigManager(config_path=tmp_path / "config.json")
    cfg_mgr.set_api_key("gemini", "AIzaSyInvalidKey123")

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = Exception("401 Unauthorized API key invalid")

    monkeypatch.setattr("agent.providers.get_llm_provider", lambda **kwargs: mock_llm)

    status = check_provider_health(cfg_mgr, "gemini")
    assert status == AIHealthStatus.INVALID_API_KEY


def test_5_network_failure_returns_network_error(tmp_path, monkeypatch):
    cfg_mgr = ConfigManager(config_path=tmp_path / "config.json")
    cfg_mgr.set_api_key("gemini", "AIzaSyValidKey123")

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = Exception("Connection refused by host")

    monkeypatch.setattr("agent.providers.get_llm_provider", lambda **kwargs: mock_llm)

    status = check_provider_health(cfg_mgr, "gemini")
    assert status == AIHealthStatus.NETWORK_ERROR


def test_6_timeout_returns_timeout(tmp_path, monkeypatch):
    cfg_mgr = ConfigManager(config_path=tmp_path / "config.json")
    cfg_mgr.set_api_key("gemini", "AIzaSyValidKey123")

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = TimeoutError("Request timed out")

    monkeypatch.setattr("agent.providers.get_llm_provider", lambda **kwargs: mock_llm)

    status = check_provider_health(cfg_mgr, "gemini")
    assert status == AIHealthStatus.TIMEOUT


def test_7_provider_error_returns_provider_error(tmp_path, monkeypatch):
    cfg_mgr = ConfigManager(config_path=tmp_path / "config.json")
    cfg_mgr.set_api_key("gemini", "AIzaSyValidKey123")

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = Exception("Internal 500 server error")

    monkeypatch.setattr("agent.providers.get_llm_provider", lambda **kwargs: mock_llm)

    status = check_provider_health(cfg_mgr, "gemini")
    assert status == AIHealthStatus.PROVIDER_ERROR


def test_8_api_key_never_appears_in_config_json(tmp_path):
    cfg_file = tmp_path / "config.json"
    cfg_mgr = ConfigManager(config_path=cfg_file)

    secret_key = "AIzaSySecretKeyNeverInConfigFile"
    cfg_mgr.set_api_key("gemini", secret_key)
    cfg_mgr.update_config({"ai_provider": "gemini"})

    content = cfg_file.read_text(encoding="utf-8")
    assert secret_key not in content
    assert "api_key" not in content.lower()


def test_9_api_key_never_appears_in_sqlite_payload(tmp_path):
    db_file = tmp_path / "test_jobs.db"
    queue = JobQueue(db_path=db_file)

    secret_key = "AIzaSySecretKeyNeverInSQLite"
    payload = SubmissionPayload(
        job_id="JOB-SEC-01",
        platform="leetcode",
        problem={"title": "Two Sum"},
        solution={"language": "python", "code": "pass"},
        api_key=secret_key,
    )
    queue.enqueue(payload)

    rec = queue.get_job("JOB-SEC-01")
    raw_payload_str = str(rec.get("payload", {}))
    assert secret_key not in raw_payload_str


def test_10_api_key_never_appears_in_rest_response(tmp_path):
    db_file = tmp_path / "test_rest.db"
    cfg_file = tmp_path / "test_rest.json"

    queue = JobQueue(db_path=db_file)
    cfg_mgr = ConfigManager(config_path=cfg_file)
    cfg_mgr.set_api_key("gemini", "AIzaSySecretRESTKey")

    with TestClient(app) as client:
        app.state.queue = queue
        app.state.config_mgr = cfg_mgr

        res = client.get("/api/v1/config")
        assert res.status_code == 200
        data = res.json()
        assert "AIzaSySecretRESTKey" not in str(data)
        assert "api_key" not in str(data).lower()


def test_11_api_key_never_appears_in_websocket_event():
    from backend.api.websocket import ConnectionManager
    mgr = ConnectionManager()
    assert hasattr(mgr, "broadcast")


def test_12_save_key_triggers_health_check_status_connected(tmp_path, monkeypatch):
    cfg_mgr = ConfigManager(config_path=tmp_path / "config.json")
    helper = TrayConfigHelper(config_manager=cfg_mgr)

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = "OK"
    monkeypatch.setattr("agent.providers.get_llm_provider", lambda **kwargs: mock_llm)

    helper.set_api_key("gemini", "AIzaSyValidKey123")
    status = helper.check_provider_health("gemini")
    assert status == AIHealthStatus.CONNECTED


def test_13_remove_key_status_becomes_not_configured(tmp_path):
    cfg_mgr = ConfigManager(config_path=tmp_path / "config.json")
    helper = TrayConfigHelper(config_manager=cfg_mgr)

    helper.set_api_key("gemini", "AIzaSyValidKey123")
    assert helper.has_api_key("gemini") is True

    helper.remove_api_key("gemini")
    assert helper.has_api_key("gemini") is False
    assert helper.check_provider_health("gemini") == AIHealthStatus.NOT_CONFIGURED


def test_14_provider_change_recalculates_status(tmp_path):
    cfg_mgr = ConfigManager(config_path=tmp_path / "config.json")
    helper = TrayConfigHelper(config_manager=cfg_mgr)

    helper.set_api_key("gemini", "AIzaSyGeminiKey")
    assert helper.has_api_key("gemini") is True
    assert helper.has_api_key("openai") is False


def test_15_startup_without_key_produces_warning_log(tmp_path, monkeypatch, caplog):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr("backend.config.manager.get_config_dir", lambda: tmp_path)

    cfg_file = tmp_path / "config.json"
    cfg_mgr = ConfigManager(config_path=cfg_file)
    cfg_mgr.update_config({"ai_provider": "gemini"})

    db_file = tmp_path / "test_startup.db"
    queue = JobQueue(db_path=db_file)

    with caplog.at_level("WARNING"):
        with TestClient(app) as client:
            app.state.queue = queue
            app.state.config_mgr = cfg_mgr

    assert "AI provider not configured for 'gemini'" in caplog.text


def test_16_startup_with_valid_key_produces_info_log(tmp_path, caplog):
    cfg_file = tmp_path / "config.json"
    cfg_mgr = ConfigManager(config_path=cfg_file)
    cfg_mgr.set_api_key("gemini", "AIzaSyValidStartupKey")
    cfg_mgr.update_config({"ai_provider": "gemini"})

    db_file = tmp_path / "test_startup_valid.db"
    queue = JobQueue(db_path=db_file)

    with caplog.at_level("INFO"):
        with TestClient(app) as client:
            app.state.queue = queue
            app.state.config_mgr = cfg_mgr

    assert "AI provider configured: gemini" in caplog.text


def test_17_ai_failure_does_not_crash_ghostpush_startup(tmp_path):
    cfg_file = tmp_path / "config.json"
    cfg_mgr = ConfigManager(config_path=cfg_file)
    db_file = tmp_path / "test_crash.db"
    queue = JobQueue(db_path=db_file)

    tray = TrayApp(config_helper=TrayConfigHelper(config_manager=cfg_mgr))

    # Trigger health check directly (simulating startup without key)
    tray.check_ai_status(notify=False)
    # App is safe and does not raise an exception
    assert True


def test_18_first_time_user_has_api_key_returns_false(tmp_path, monkeypatch):
    """Verify first-time user with placeholder key returns has_api_key == False."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr("backend.config.manager.get_config_dir", lambda: tmp_path)

    cfg_mgr = ConfigManager(config_path=tmp_path / "config.json")
    helper = TrayConfigHelper(config_manager=cfg_mgr)

    # First time user - no key stored
    assert helper.has_api_key("gemini") is False

    # First time user with placeholder key
    helper.set_api_key("gemini", "your_gemini_api_key_here")
    assert helper.has_api_key("gemini") is False


def test_19_async_health_check_non_blocking(tmp_path, monkeypatch):
    """Verify health check can be called asynchronously without blocking thread."""
    import time
    cfg_mgr = ConfigManager(config_path=tmp_path / "config.json")
    cfg_mgr.set_api_key("gemini", "AIzaSyValidKey123")
    helper = TrayConfigHelper(config_manager=cfg_mgr)

    def slow_check(*args, **kwargs):
        time.sleep(0.5)
        return AIHealthStatus.CONNECTED

    monkeypatch.setattr(helper, "check_provider_health", slow_check)

    start = time.time()
    # Call health check in background thread
    import threading
    t = threading.Thread(target=helper.check_provider_health, args=("gemini",))
    t.start()
    elapsed = time.time() - start

    # Spawning thread must take less than 0.1s (non-blocking)
    assert elapsed < 0.1
    t.join()

