import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from common.constants import API_VERSION
from backend.api.app import app
from backend.config.manager import ConfigManager
from backend.jobs.queue import JobQueue


@pytest.fixture
def isolated_client(tmp_path):
    db_file = tmp_path / "test_api_jobs.db"
    config_file = tmp_path / "test_config.json"
    test_queue = JobQueue(db_path=db_file)
    test_config_mgr = ConfigManager(config_path=config_file)

    with TestClient(app) as client:
        app.state.queue = test_queue
        app.state.config_mgr = test_config_mgr
        yield client


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["api_version"] == API_VERSION


def test_get_config_success_and_secret_safety(isolated_client):
    response = isolated_client.get("/api/v1/config")
    assert response.status_code == 200
    data = response.json()

    assert "repository_path" in data
    assert "ai_provider" in data
    assert "api_port" in data
    assert "log_level" in data

    # Verify no secret fields exist in returned JSON schema
    for key in data.keys():
        assert "api_key" not in key.lower()
        assert "secret" not in key.lower()
        assert "token" not in key.lower()
        assert "password" not in key.lower()


def test_put_config_valid_update_and_persistence(isolated_client, tmp_path):
    valid_repo = str(tmp_path.resolve())
    updates = {
        "repository_path": valid_repo,
        "ai_provider": "openai",
        "theme": "light",
        "log_level": "DEBUG",
    }

    response = isolated_client.put("/api/v1/config", json=updates)
    assert response.status_code == 200
    data = response.json()

    assert data["ai_provider"] == "openai"
    assert data["theme"] == "light"
    assert data["log_level"] == "DEBUG"

    # Verify persistence via GET /api/v1/config
    get_resp = isolated_client.get("/api/v1/config")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["ai_provider"] == "openai"
    assert get_data["theme"] == "light"
    assert get_data["log_level"] == "DEBUG"


def test_put_config_invalid_repository_path_rejected(isolated_client):
    updates = {"repository_path": "/nonexistent_directory_ghostpush_test_xyz_123"}
    response = isolated_client.put("/api/v1/config", json=updates)
    assert response.status_code == 400
    assert "existing directory" in response.json()["detail"]


def test_put_config_invalid_api_port_rejected(isolated_client):
    updates = {"api_port": 999999}
    response = isolated_client.put("/api/v1/config", json=updates)
    assert response.status_code == 400
    assert "api_port" in response.json()["detail"]


def test_put_config_invalid_log_level_rejected(isolated_client):
    updates = {"log_level": "INVALID_LEVEL"}
    response = isolated_client.put("/api/v1/config", json=updates)
    assert response.status_code == 400
    assert "log_level" in response.json()["detail"]


def test_put_config_empty_ai_provider_rejected(isolated_client):
    updates = {"ai_provider": "   "}
    response = isolated_client.put("/api/v1/config", json=updates)
    assert response.status_code == 400
    assert "ai_provider" in response.json()["detail"]


def test_put_config_secret_field_rejected(isolated_client):
    secret_payloads = [
        {"api_key": "super_secret_val"},
        {"GEMINI_API_KEY": "secret_gemini"},
        {"OPENAI_API_KEY": "secret_openai"},
        {"password": "my_password"},
        {"token": "my_token"},
    ]

    for secret_payload in secret_payloads:
        response = isolated_client.put("/api/v1/config", json=secret_payload)
        assert response.status_code == 400
        assert "cannot be persisted" in response.json()["detail"]
        assert "super_secret_val" not in response.text
        assert "secret_gemini" not in response.text


def test_create_job_success_and_secret_stripping(isolated_client):
    payload_data = {
        "job_id": "API-JOB-001",
        "platform": "leetcode",
        "problem": {"title": "Two Sum", "difficulty": "Easy"},
        "solution": {"language": "python", "code": "def two_sum(): pass"},
        "repository_path": "/tmp/test_repo",
        "api_key": "secret_api_key_should_not_be_saved",
    }

    response = isolated_client.post("/api/v1/jobs", json=payload_data)
    assert response.status_code == 201

    job_data = response.json()
    assert job_data["job_id"] == "API-JOB-001"
    assert job_data["status"] == "QUEUED"
    assert job_data["title"] == "Two Sum"
    assert job_data["language"] == "python"

    # Verify secret key is NOT present in response
    assert "api_key" not in job_data
    assert "secret_api_key_should_not_be_saved" not in json.dumps(job_data)

    # Fetch job via GET /jobs/{job_id} and verify secret key is absent
    get_resp = isolated_client.get("/api/v1/jobs/API-JOB-001")
    assert get_resp.status_code == 200
    fetched_job = get_resp.json()
    assert fetched_job["job_id"] == "API-JOB-001"
    assert "api_key" not in fetched_job
    assert "secret_api_key_should_not_be_saved" not in json.dumps(fetched_job)


def test_get_job_not_found(isolated_client):
    response = isolated_client.get("/api/v1/jobs/NON-EXISTENT-JOB")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_list_jobs_and_pagination(isolated_client):
    for i in range(5):
        payload_data = {
            "job_id": f"PAG-JOB-{i:02d}",
            "platform": "leetcode",
            "problem": {"title": f"Problem {i}"},
            "solution": {"language": "python", "code": "code"},
            "repository_path": "/tmp/test_repo",
        }
        resp = isolated_client.post("/api/v1/jobs", json=payload_data)
        assert resp.status_code == 201

    # List all (limit=50)
    list_resp = isolated_client.get("/api/v1/jobs")
    assert list_resp.status_code == 200
    jobs = list_resp.json()
    assert len(jobs) == 5

    # Test limit and offset
    pag_resp = isolated_client.get("/api/v1/jobs?limit=2&offset=1")
    assert pag_resp.status_code == 200
    pag_jobs = pag_resp.json()
    assert len(pag_jobs) == 2


def test_invalid_payload_rejected(isolated_client):
    invalid_data = {
        "job_id": "INVALID-001",
    }
    response = isolated_client.post("/api/v1/jobs", json=invalid_data)
    assert response.status_code == 422
