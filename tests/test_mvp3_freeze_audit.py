"""Tests for Phase 10.4 (MVP-3) reliability, validation, duplicate handling, and config defaults."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from agent.graph import validate_node
from backend.api.app import app
from backend.config.manager import ConfigManager
from common.enums import JobStatus
from common.errors import ErrorCode, GhostPushError


def test_appsettings_repository_path_must_exist(tmp_path):
    """Verify that default config repository_path must be an existing directory."""
    cfg_file = tmp_path / "config.json"
    mgr = ConfigManager(config_path=cfg_file)
    settings = mgr.load_config()
    assert settings.repository_path != ""
    assert Path(settings.repository_path).is_dir()


def test_validate_node_unknown_platform():
    """Verify validate_node fails with INVALID_PLATFORM for unknown platform strings."""
    state = {
        "payload": {
            "job_id": "TEST-JOB-99",
            "platform": "unknown_platform",
            "problem": {"title": "Two Sum"},
            "solution": {"code": "print(1)"},
        },
        "status": JobStatus.CREATED.value,
        "current_step": "",
        "readme_content": "",
        "file_results": {},
        "commit_hash": "",
        "push_success": False,
        "error_message": "",
        "response": {},
    }

    res_state = validate_node(state)
    assert res_state["status"] == JobStatus.FAILED.value
    assert "Unsupported platform 'unknown_platform'" in res_state["error_message"]


def test_create_job_duplicate_returns_409():
    """Verify POST /api/v1/jobs with a duplicate job_id returns 409 Conflict."""
    with TestClient(app) as client:
        payload = {
            "api_version": "1.0",
            "job_id": "JOB-DUP-UNIQUE-9999",
            "platform": "leetcode",
            "problem": {"title": "Two Sum", "difficulty": "Easy"},
            "solution": {"language": "python", "code": "pass"},
        }
        res1 = client.post("/api/v1/jobs", json=payload)
        assert res1.status_code == 201

        res2 = client.post("/api/v1/jobs", json=payload)
        assert res2.status_code == 409
        assert "already exists" in res2.json()["detail"]
