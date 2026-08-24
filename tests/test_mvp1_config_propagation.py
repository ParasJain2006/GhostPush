import os
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from common.enums import JobStatus
from common.schemas import AgentResponse, ProblemInfo, SolutionInfo, SubmissionPayload
from backend.config.manager import ConfigManager
from backend.config.models import AppSettings
from backend.config.settings import get_config_dir
from backend.jobs.queue import JobQueue
from backend.jobs.worker import JobWorker


def _make_minimal_payload(job_id: str = "JOB-MVP1-001") -> SubmissionPayload:
    """Helper creating a job payload without config fields (like extension popup)."""
    return SubmissionPayload(
        job_id=job_id,
        platform="leetcode",
        problem=ProblemInfo(title="Two Sum", difficulty="Easy"),
        solution=SolutionInfo(language="python", code="def two_sum(): pass"),
        repository_path="",  # empty to test config fallback
    )


def test_mvp1_ai_provider_injected_from_config(tmp_path):
    """1. ai_provider is injected from configuration when omitted in job."""
    db_file = tmp_path / "test1.db"
    config_file = tmp_path / "config.json"
    
    config_mgr = ConfigManager(config_path=config_file)
    settings = AppSettings(
        repository_path=str(tmp_path),
        ai_provider="anthropic",
        ai_model="claude-3-5-sonnet",
        remote_repo_url="https://github.com/test/repo.git",
    )
    config_mgr.save_config(settings)

    queue = JobQueue(db_path=db_file)
    payload = _make_minimal_payload("JOB-TEST-1")
    queue.enqueue(payload)

    worker = JobWorker(queue=queue, poll_interval=0.05, config_manager=config_mgr)

    expected_resp = AgentResponse(
        status="SUCCESS",
        job_id="JOB-TEST-1",
        repository_path=str(tmp_path),
        message="OK",
    )

    with patch("backend.jobs.worker.execute_agent", return_value=expected_resp) as mock_exec:
        worker.process_one_job()

    assert mock_exec.call_count == 1
    sent_payload: SubmissionPayload = mock_exec.call_args[0][0]
    assert sent_payload.ai_provider == "anthropic"


def test_mvp1_ai_model_injected_from_config(tmp_path):
    """2. ai_model is injected from configuration when omitted in job."""
    db_file = tmp_path / "test2.db"
    config_file = tmp_path / "config.json"

    config_mgr = ConfigManager(config_path=config_file)
    settings = AppSettings(
        repository_path=str(tmp_path),
        ai_provider="openai",
        ai_model="gpt-4o",
    )
    config_mgr.save_config(settings)

    queue = JobQueue(db_path=db_file)
    payload = _make_minimal_payload("JOB-TEST-2")
    queue.enqueue(payload)

    worker = JobWorker(queue=queue, poll_interval=0.05, config_manager=config_mgr)

    expected_resp = AgentResponse(
        status="SUCCESS",
        job_id="JOB-TEST-2",
        repository_path=str(tmp_path),
        message="OK",
    )

    with patch("backend.jobs.worker.execute_agent", return_value=expected_resp) as mock_exec:
        worker.process_one_job()

    sent_payload: SubmissionPayload = mock_exec.call_args[0][0]
    assert sent_payload.ai_model == "gpt-4o"


def test_mvp1_api_key_resolved_from_config_manager(tmp_path, monkeypatch):
    """3. API key is resolved from ConfigManager environment when ai_provider is configured."""
    db_file = tmp_path / "test3.db"
    config_file = tmp_path / "config.json"
    empty_appdata = tmp_path / "empty_appdata"
    empty_appdata.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("GEMINI_API_KEY", "secret_gemini_key_12345")

    with patch("backend.config.manager.get_config_dir", return_value=empty_appdata):
        config_mgr = ConfigManager(config_path=config_file)
        settings = AppSettings(
            repository_path=str(tmp_path),
            ai_provider="gemini",
            ai_model="gemini-1.5-pro",
        )
        config_mgr.save_config(settings)

        queue = JobQueue(db_path=db_file)
        payload = _make_minimal_payload("JOB-TEST-3")
        queue.enqueue(payload)

        worker = JobWorker(queue=queue, poll_interval=0.05, config_manager=config_mgr)

        expected_resp = AgentResponse(
            status="SUCCESS",
            job_id="JOB-TEST-3",
            repository_path=str(tmp_path),
            message="OK",
        )

        with patch("backend.jobs.worker.execute_agent", return_value=expected_resp) as mock_exec:
            worker.process_one_job()

        sent_payload: SubmissionPayload = mock_exec.call_args[0][0]
        assert sent_payload.api_key == "secret_gemini_key_12345"


def test_mvp1_remote_repo_url_injected_from_config(tmp_path):
    """4. remote_repo_url is injected from configuration when omitted in job."""
    db_file = tmp_path / "test4.db"
    config_file = tmp_path / "config.json"

    config_mgr = ConfigManager(config_path=config_file)
    settings = AppSettings(
        repository_path=str(tmp_path),
        remote_repo_url="https://github.com/user/my-solutions.git",
        ai_provider="gemini",
    )
    config_mgr.save_config(settings)

    queue = JobQueue(db_path=db_file)
    payload = _make_minimal_payload("JOB-TEST-4")
    queue.enqueue(payload)

    worker = JobWorker(queue=queue, poll_interval=0.05, config_manager=config_mgr)

    expected_resp = AgentResponse(
        status="SUCCESS",
        job_id="JOB-TEST-4",
        repository_path=str(tmp_path),
        message="OK",
    )

    with patch("backend.jobs.worker.execute_agent", return_value=expected_resp) as mock_exec:
        worker.process_one_job()

    sent_payload: SubmissionPayload = mock_exec.call_args[0][0]
    assert sent_payload.remote_repo_url == "https://github.com/user/my-solutions.git"


def test_mvp1_explicit_job_values_preserved(tmp_path):
    """5. Explicit job values are preserved and not overwritten by config defaults."""
    db_file = tmp_path / "test5.db"
    config_file = tmp_path / "config.json"

    default_repo = tmp_path / "default_repo"
    default_repo.mkdir(parents=True, exist_ok=True)
    custom_repo = tmp_path / "custom_repo"
    custom_repo.mkdir(parents=True, exist_ok=True)

    config_mgr = ConfigManager(config_path=config_file)
    settings = AppSettings(
        repository_path=str(default_repo),
        remote_repo_url="https://github.com/default/repo.git",
        ai_provider="gemini",
        ai_model="gemini-1.5-flash",
    )
    config_mgr.save_config(settings)

    queue = JobQueue(db_path=db_file)
    payload = SubmissionPayload(
        job_id="JOB-TEST-5",
        platform="leetcode",
        problem=ProblemInfo(title="Two Sum", difficulty="Easy"),
        solution=SolutionInfo(language="python", code="def two_sum(): pass"),
        repository_path=str(custom_repo),
        remote_repo_url="https://github.com/custom/repo.git",
        ai_provider="groq",
        ai_model="llama-3.1-70b",
    )
    queue.enqueue(payload)

    worker = JobWorker(queue=queue, poll_interval=0.05, config_manager=config_mgr)

    expected_resp = AgentResponse(
        status="SUCCESS",
        job_id="JOB-TEST-5",
        repository_path=str(custom_repo),
        message="OK",
    )

    with patch("backend.jobs.worker.execute_agent", return_value=expected_resp) as mock_exec:
        worker.process_one_job()

    sent_payload: SubmissionPayload = mock_exec.call_args[0][0]
    assert sent_payload.repository_path == str(custom_repo)
    assert sent_payload.remote_repo_url == "https://github.com/custom/repo.git"
    assert sent_payload.ai_provider == "groq"
    assert sent_payload.ai_model == "llama-3.1-70b"


def test_mvp1_api_key_not_persisted_to_sqlite(tmp_path, monkeypatch):
    """6. API key is NOT persisted to SQLite database."""
    db_file = tmp_path / "test6.db"
    config_file = tmp_path / "config.json"

    monkeypatch.setenv("GEMINI_API_KEY", "super_secret_key_999")

    config_mgr = ConfigManager(config_path=config_file)
    settings = AppSettings(
        repository_path=str(tmp_path),
        ai_provider="gemini",
    )
    config_mgr.save_config(settings)

    queue = JobQueue(db_path=db_file)
    payload = _make_minimal_payload("JOB-TEST-6")
    queue.enqueue(payload)

    worker = JobWorker(queue=queue, poll_interval=0.05, config_manager=config_mgr)

    expected_resp = AgentResponse(
        status="SUCCESS",
        job_id="JOB-TEST-6",
        repository_path=str(tmp_path),
        message="OK",
    )

    with patch("backend.jobs.worker.execute_agent", return_value=expected_resp):
        worker.process_one_job()

    # Query DB directly to check persisted job payload
    job_rec = queue.get_job("JOB-TEST-6")
    assert job_rec is not None
    stored_payload = job_rec.get("payload", {})
    assert "api_key" not in stored_payload or stored_payload.get("api_key") == ""
    assert "super_secret_key_999" not in json.dumps(job_rec)


def test_mvp1_api_key_not_exposed_in_job_data(tmp_path, monkeypatch):
    """7. API key is NOT exposed in returned job data / queue APIs."""
    db_file = tmp_path / "test7.db"
    config_file = tmp_path / "config.json"

    monkeypatch.setenv("GEMINI_API_KEY", "secret_key_abc")

    config_mgr = ConfigManager(config_path=config_file)
    settings = AppSettings(
        repository_path=str(tmp_path),
        ai_provider="gemini",
    )
    config_mgr.save_config(settings)

    queue = JobQueue(db_path=db_file)
    payload = _make_minimal_payload("JOB-TEST-7")
    queue.enqueue(payload)

    worker = JobWorker(queue=queue, poll_interval=0.05, config_manager=config_mgr)

    expected_resp = AgentResponse(
        status="SUCCESS",
        job_id="JOB-TEST-7",
        repository_path=str(tmp_path),
        message="OK",
    )

    with patch("backend.jobs.worker.execute_agent", return_value=expected_resp):
        worker.process_one_job()

    # Check job dict returned by queue
    job_rec = queue.get_job("JOB-TEST-7")
    raw_str = json.dumps(job_rec)
    assert "secret_key_abc" not in raw_str


def test_mvp1_frozen_env_path_resolves_via_appdata(tmp_path, monkeypatch):
    """8. Frozen .env path resolves through APPDATA directory."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    appdata_dir = tmp_path / "GhostPush"
    appdata_dir.mkdir(parents=True, exist_ok=True)
    frozen_env_file = appdata_dir / ".env"
    frozen_env_file.write_text("OPENAI_API_KEY=frozen_appdata_key_777\n", encoding="utf-8")

    # Mock get_config_dir to point to appdata_dir
    with patch("backend.config.manager.get_config_dir", return_value=appdata_dir):
        config_mgr = ConfigManager(config_path=tmp_path / "config.json")
        key = config_mgr.get_api_key("openai")
        assert key == "frozen_appdata_key_777"


def test_mvp1_development_env_behaviour_unchanged(tmp_path, monkeypatch):
    """9. Development mode .env behaviour remains unchanged when APPDATA .env is absent."""
    appdata_dir = tmp_path / "EmptyGhostPush"
    appdata_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "dev_env_key_888")

    with patch("backend.config.manager.get_config_dir", return_value=appdata_dir):
        config_mgr = ConfigManager(config_path=tmp_path / "config.json")
        key = config_mgr.get_api_key("anthropic")
        assert key == "dev_env_key_888"


def test_mvp1_worker_calls_adapter_with_submission_payload(tmp_path):
    """10. Worker calls the existing adapter (execute_agent) with SubmissionPayload."""
    db_file = tmp_path / "test10.db"
    config_file = tmp_path / "config.json"

    config_mgr = ConfigManager(config_path=config_file)
    settings = AppSettings(
        repository_path=str(tmp_path),
        ai_provider="gemini",
        ai_model="gemini-1.5-flash",
    )
    config_mgr.save_config(settings)

    queue = JobQueue(db_path=db_file)
    payload = _make_minimal_payload("JOB-TEST-10")
    queue.enqueue(payload)

    worker = JobWorker(queue=queue, poll_interval=0.05, config_manager=config_mgr)

    expected_resp = AgentResponse(
        status="SUCCESS",
        job_id="JOB-TEST-10",
        repository_path=str(tmp_path),
        message="Executed via adapter",
    )

    with patch("backend.jobs.worker.execute_agent", return_value=expected_resp) as mock_exec:
        processed = worker.process_one_job()

    assert processed is True
    mock_exec.assert_called_once()
    arg = mock_exec.call_args[0][0]
    assert isinstance(arg, SubmissionPayload)
    assert arg.job_id == "JOB-TEST-10"
    assert arg.ai_provider == "gemini"
    assert arg.ai_model == "gemini-1.5-flash"
    assert arg.repository_path == str(tmp_path)
