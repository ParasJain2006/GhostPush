import json
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from common.enums import JobStatus
from common.errors import ErrorCode, GhostPushError
from common.schemas import AgentResponse, ProblemInfo, SolutionInfo, SubmissionPayload
from backend.config.manager import ConfigManager
from backend.config.models import AppSettings
from backend.db.database import get_db_connection
from backend.db.repository import JobRepository
from backend.db.schema import create_tables
from backend.jobs.queue import JobQueue
from backend.jobs.worker import JobWorker
from agent.graph import create_agent_graph


def _make_payload(job_id: str, repo_path: str, remote_url: str = "") -> SubmissionPayload:
    return SubmissionPayload(
        job_id=job_id,
        platform="leetcode",
        problem=ProblemInfo(title="Two Sum", difficulty="Easy"),
        solution=SolutionInfo(language="python", code="def two_sum(): pass"),
        repository_path=repo_path,
        remote_repo_url=remote_url,
    )


def test_mvp2_successful_git_push(tmp_path):
    """1. Successful Git push sets push_success=True and status COMPLETED."""
    db_file = tmp_path / "test1.db"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    config_mgr = ConfigManager(config_path=tmp_path / "config.json")
    settings = AppSettings(
        repository_path=str(repo_dir),
        remote_repo_url="https://github.com/test/repo.git",
        ai_provider="gemini",
    )
    config_mgr.save_config(settings)

    queue = JobQueue(db_path=db_file)
    payload = _make_payload("JOB-PUSH-SUCCESS", str(repo_dir), "https://github.com/test/repo.git")
    queue.enqueue(payload)

    worker = JobWorker(queue=queue, poll_interval=0.05, config_manager=config_mgr)

    expected_resp = AgentResponse(
        status="SUCCESS",
        job_id="JOB-PUSH-SUCCESS",
        commit_hash="commit_hash_123",
        repository_path=str(repo_dir),
        message="Successfully written files and pushed Git commit.",
        push_success=True,
    )

    with patch("backend.jobs.worker.execute_agent", return_value=expected_resp):
        worker.process_one_job()

    job_rec = queue.get_job("JOB-PUSH-SUCCESS")
    assert job_rec["status"] == JobStatus.COMPLETED.value
    assert job_rec["push_success"] is True
    assert job_rec["response"]["push_success"] is True


def test_mvp2_configured_remote_push_failure(tmp_path):
    """2. Configured remote + push failure sets push_success=False and status FAILED."""
    db_file = tmp_path / "test2.db"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    config_mgr = ConfigManager(config_path=tmp_path / "config.json")
    settings = AppSettings(
        repository_path=str(repo_dir),
        remote_repo_url="https://github.com/invalid/repo.git",
        ai_provider="gemini",
    )
    config_mgr.save_config(settings)

    queue = JobQueue(db_path=db_file)
    payload = _make_payload("JOB-PUSH-FAIL", str(repo_dir), "https://github.com/invalid/repo.git")
    queue.enqueue(payload)

    worker = JobWorker(queue=queue, poll_interval=0.05, config_manager=config_mgr)

    failed_resp = AgentResponse(
        status="FAILED",
        job_id="JOB-PUSH-FAIL",
        commit_hash="local_commit_999",
        repository_path=str(repo_dir),
        message="Git push failed: Could not resolve host",
        push_success=False,
    )

    with patch("backend.jobs.worker.execute_agent", return_value=failed_resp):
        worker.process_one_job()

    job_rec = queue.get_job("JOB-PUSH-FAIL")
    assert job_rec["status"] == JobStatus.FAILED.value
    assert job_rec["push_success"] is False
    assert job_rec["response"]["push_success"] is False
    assert "Git push failed" in job_rec["error_message"]


def test_mvp2_no_configured_remote(tmp_path):
    """3. No configured remote sets push_success=None and job status COMPLETED."""
    db_file = tmp_path / "test3.db"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    config_mgr = ConfigManager(config_path=tmp_path / "config.json")
    settings = AppSettings(
        repository_path=str(repo_dir),
        remote_repo_url="",
        ai_provider="gemini",
    )
    config_mgr.save_config(settings)

    queue = JobQueue(db_path=db_file)
    payload = _make_payload("JOB-NO-REMOTE", str(repo_dir), "")
    queue.enqueue(payload)

    worker = JobWorker(queue=queue, poll_interval=0.05, config_manager=config_mgr)

    no_remote_resp = AgentResponse(
        status="SUCCESS",
        job_id="JOB-NO-REMOTE",
        commit_hash="commit_hash_no_remote",
        repository_path=str(repo_dir),
        message="Successfully written files and created local Git commit (no remote configured).",
        push_success=None,
    )

    with patch("backend.jobs.worker.execute_agent", return_value=no_remote_resp):
        worker.process_one_job()

    job_rec = queue.get_job("JOB-NO-REMOTE")
    assert job_rec["status"] == JobStatus.COMPLETED.value
    assert job_rec["push_success"] is None
    assert job_rec["response"]["push_success"] is None


def test_mvp2_distinguish_local_commit_from_push(tmp_path):
    """4. Local commit is recorded even when push_success is False or None."""
    db_file = tmp_path / "test4.db"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    queue = JobQueue(db_path=db_file)
    payload = _make_payload("JOB-COMMIT-ONLY", str(repo_dir), "https://github.com/test/repo.git")
    queue.enqueue(payload)

    resp = AgentResponse(
        status="FAILED",
        job_id="JOB-COMMIT-ONLY",
        commit_hash="abc123commit",
        repository_path=str(repo_dir),
        message="Git push failed: Remote rejected",
        push_success=False,
    )

    queue.complete_job("JOB-COMMIT-ONLY", resp)
    job_rec = queue.get_job("JOB-COMMIT-ONLY")

    # Local commit hash is preserved
    assert job_rec["commit_hash"] == "abc123commit"
    # But push_success indicates failure
    assert job_rec["push_success"] is False


def test_mvp2_rest_job_result_exposes_push_success(tmp_path):
    """5. REST API / repository exposes push_success in job records."""
    db_file = tmp_path / "test5.db"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    queue = JobQueue(db_path=db_file)
    payload = _make_payload("JOB-REST-TEST", str(repo_dir))
    queue.enqueue(payload)

    resp = AgentResponse(
        status="SUCCESS",
        job_id="JOB-REST-TEST",
        commit_hash="git_hash_777",
        repository_path=str(repo_dir),
        message="All done",
        push_success=True,
    )

    queue.complete_job("JOB-REST-TEST", resp)

    job_rec = queue.get_job("JOB-REST-TEST")
    assert "push_success" in job_rec
    assert job_rec["push_success"] is True

    # List jobs also includes push_success
    jobs_list = queue.list_jobs()
    assert len(jobs_list) == 1
    assert jobs_list[0]["push_success"] is True


def test_mvp2_database_schema_migration(tmp_path):
    """6. Database migration safely adds push_success column to pre-existing SQLite DBs."""
    db_file = tmp_path / "legacy.db"

    # Create legacy table without push_success column
    conn = sqlite3.connect(str(db_file))
    with conn:
        conn.execute("""
        CREATE TABLE jobs (
            job_id TEXT PRIMARY KEY NOT NULL,
            status TEXT NOT NULL,
            platform TEXT NOT NULL,
            title TEXT NOT NULL,
            language TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            response_json TEXT,
            commit_hash TEXT,
            error_message TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """)
    conn.close()

    # Now initialize schema/repo which triggers migration
    repo = JobRepository(db_path=db_file)
    conn = repo._get_connection()
    cur = conn.execute("PRAGMA table_info(jobs)")
    columns = [row[1] for row in cur.fetchall()]
    conn.close()

    assert "push_success" in columns


def test_mvp2_worker_continues_after_git_failure(tmp_path):
    """7. Worker continues processing subsequent jobs after a Git push failure."""
    db_file = tmp_path / "test7.db"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    queue = JobQueue(db_path=db_file)
    p1 = _make_payload("JOB-FAIL-PUSH", str(repo_dir), "https://github.com/bad/repo.git")
    p2 = _make_payload("JOB-PASS-PUSH", str(repo_dir), "https://github.com/good/repo.git")
    queue.enqueue(p1)
    queue.enqueue(p2)

    config_mgr = ConfigManager(config_path=tmp_path / "config.json")
    worker = JobWorker(queue=queue, poll_interval=0.05, config_manager=config_mgr)

    resp1 = AgentResponse(
        status="FAILED",
        job_id="JOB-FAIL-PUSH",
        commit_hash="c1",
        repository_path=str(repo_dir),
        message="Git push failed: Auth error",
        push_success=False,
    )
    resp2 = AgentResponse(
        status="SUCCESS",
        job_id="JOB-PASS-PUSH",
        commit_hash="c2",
        repository_path=str(repo_dir),
        message="OK",
        push_success=True,
    )

    def mock_agent(payload):
        if payload.job_id == "JOB-FAIL-PUSH":
            return resp1
        return resp2

    with patch("backend.jobs.worker.execute_agent", side_effect=mock_agent):
        worker.process_one_job()
        worker.process_one_job()

    j1 = queue.get_job("JOB-FAIL-PUSH")
    j2 = queue.get_job("JOB-PASS-PUSH")

    assert j1["status"] == JobStatus.FAILED.value
    assert j1["push_success"] is False
    assert j2["status"] == JobStatus.COMPLETED.value
    assert j2["push_success"] is True


def test_mvp2_secret_safety_preserved(tmp_path, monkeypatch):
    """8. API keys remain absent from stored SQLite database records."""
    db_file = tmp_path / "test8.db"
    config_file = tmp_path / "config.json"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("GEMINI_API_KEY", "secret_gemini_key_99999")

    config_mgr = ConfigManager(config_path=config_file)
    settings = AppSettings(
        repository_path=str(repo_dir),
        ai_provider="gemini",
    )
    config_mgr.save_config(settings)

    queue = JobQueue(db_path=db_file)
    payload = _make_payload("JOB-SECRET-CHECK", str(repo_dir))
    queue.enqueue(payload)

    worker = JobWorker(queue=queue, poll_interval=0.05, config_manager=config_mgr)

    resp = AgentResponse(
        status="SUCCESS",
        job_id="JOB-SECRET-CHECK",
        commit_hash="c_sec",
        repository_path=str(repo_dir),
        message="OK",
        push_success=True,
    )

    with patch("backend.jobs.worker.execute_agent", return_value=resp):
        worker.process_one_job()

    job_rec = queue.get_job("JOB-SECRET-CHECK")
    raw_json = json.dumps(job_rec)
    assert "secret_gemini_key_99999" not in raw_json


def test_mvp2_graph_push_node_behaviour(tmp_path):
    """9. Test graph push_node sets FAILED status when configured push fails."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    # State with remote_repo_url configured, but GitTool.push raises exception
    state = {
        "payload": {
            "job_id": "JOB-GRAPH-TEST",
            "repository_path": str(repo_dir),
            "remote_repo_url": "https://github.com/fail/repo.git",
        },
        "status": JobStatus.COMMITTING,
        "current_step": "commit",
        "readme_content": "# README",
        "file_results": {},
        "commit_hash": "commit123",
        "push_success": False,
        "error_message": "",
        "response": {},
    }

    from agent.graph import push_node, finish_node

    with patch("mcp.git_tool.GitTool.push", side_effect=RuntimeError("Connection reset by peer")):
        state_after_push = push_node(state)
        state_after_finish = finish_node(state_after_push)

    assert state_after_push["push_success"] is False
    assert state_after_push["status"] == JobStatus.FAILED
    assert "Connection reset by peer" in state_after_push["error_message"]

    resp = AgentResponse.model_validate(state_after_finish["response"])
    assert resp.status == "FAILED"
    assert resp.push_success is False
