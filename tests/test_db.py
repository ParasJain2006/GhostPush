import json
import sqlite3
import pytest

from common.enums import JobStatus
from common.schemas import AgentResponse, ProblemInfo, SolutionInfo, SubmissionPayload
from backend.db.database import get_db_connection, init_db
from backend.db.repository import JobRepository
from backend.db.schema import create_tables


def test_schema_creation_and_repeatability(tmp_path):
    db_file = tmp_path / "test_ghostpush.db"
    
    # First initialization
    path1 = init_db(db_file)
    assert path1 == db_file
    assert db_file.exists()

    # Repeated initialization must be idempotent and safe
    path2 = init_db(db_file)
    assert path2 == db_file


def test_jobs_table_columns_and_indexes(tmp_path):
    db_file = tmp_path / "test_schema.db"
    init_db(db_file)

    conn = get_db_connection(db_file)
    try:
        # Check columns
        cur = conn.execute("PRAGMA table_info(jobs);")
        columns = {row["name"]: row["type"] for row in cur.fetchall()}

        expected_columns = {
            "job_id": "TEXT",
            "status": "TEXT",
            "platform": "TEXT",
            "title": "TEXT",
            "language": "TEXT",
            "payload_json": "TEXT",
            "response_json": "TEXT",
            "commit_hash": "TEXT",
            "error_message": "TEXT",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        }
        for col_name, col_type in expected_columns.items():
            assert col_name in columns
            assert columns[col_name].upper() == col_type

        # Check indexes
        cur_idx = conn.execute("PRAGMA index_list(jobs);")
        index_names = {row["name"] for row in cur_idx.fetchall()}
        assert "idx_jobs_status" in index_names
        assert "idx_jobs_created_at" in index_names
    finally:
        conn.close()


def test_job_repository_create_and_secret_stripping(tmp_path):
    db_file = tmp_path / "test_repo.db"
    repo = JobRepository(db_path=db_file)

    payload = SubmissionPayload(
        job_id="JOB-SEC-001",
        platform="leetcode",
        problem=ProblemInfo(title="Two Sum", difficulty="Easy"),
        solution=SolutionInfo(language="python", code="def two_sum(): pass"),
        repository_path=str(tmp_path),
        api_key="super_secret_api_key_12345",
    )

    job_rec = repo.create_job(payload)
    assert job_rec["job_id"] == "JOB-SEC-001"
    assert job_rec["status"] == JobStatus.QUEUED.value
    assert job_rec["platform"] == "leetcode"
    assert job_rec["title"] == "Two Sum"
    assert job_rec["language"] == "python"

    # Verify secret stripping in payload_json
    raw_payload_json = job_rec["payload_json"]
    assert "super_secret_api_key_12345" not in raw_payload_json
    assert "api_key" not in job_rec["payload"]

    # Direct SQL query check to be 100% sure secret never landed in DB
    conn = get_db_connection(db_file)
    try:
        row = conn.execute("SELECT payload_json FROM jobs WHERE job_id = 'JOB-SEC-001'").fetchone()
        assert "super_secret_api_key_12345" not in row["payload_json"]
    finally:
        conn.close()


def test_job_repository_get_list_and_queue(tmp_path):
    db_file = tmp_path / "test_queue.db"
    repo = JobRepository(db_path=db_file)

    payload1 = SubmissionPayload(
        job_id="JOB-001",
        platform="leetcode",
        problem=ProblemInfo(title="Problem 1"),
        solution=SolutionInfo(language="python", code="code1"),
        repository_path=str(tmp_path),
    )
    payload2 = SubmissionPayload(
        job_id="JOB-002",
        platform="gfg",
        problem=ProblemInfo(title="Problem 2"),
        solution=SolutionInfo(language="cpp", code="code2"),
        repository_path=str(tmp_path),
    )

    repo.create_job(payload1)
    repo.create_job(payload2)

    # Test get_job
    j1 = repo.get_job("JOB-001")
    assert j1 is not None
    assert j1["title"] == "Problem 1"

    # Test list_jobs
    all_jobs = repo.list_jobs()
    assert len(all_jobs) == 2

    # Test fetch_next_queued_job
    next_job = repo.fetch_next_queued_job()
    assert next_job is not None
    assert next_job["job_id"] == "JOB-001"


def test_job_repository_status_and_completion(tmp_path):
    db_file = tmp_path / "test_status.db"
    repo = JobRepository(db_path=db_file)

    payload = SubmissionPayload(
        job_id="JOB-COMPLETE-001",
        platform="leetcode",
        problem=ProblemInfo(title="Add Two Numbers"),
        solution=SolutionInfo(language="python", code="code"),
        repository_path=str(tmp_path),
    )
    repo.create_job(payload)

    # Transition to PROCESSING
    updated = repo.update_job_status("JOB-COMPLETE-001", JobStatus.PROCESSING)
    assert updated is True
    job_proc = repo.get_job("JOB-COMPLETE-001")
    assert job_proc["status"] == JobStatus.PROCESSING.value

    # Complete job with AgentResponse
    response = AgentResponse(
        status="SUCCESS",
        job_id="JOB-COMPLETE-001",
        commit_hash="git_hash_98765",
        repository_path=str(tmp_path),
        message="Job finished successfully",
    )

    completed = repo.complete_job("JOB-COMPLETE-001", response)
    assert completed is True

    final_job = repo.get_job("JOB-COMPLETE-001")
    assert final_job["status"] == JobStatus.COMPLETED.value
    assert final_job["commit_hash"] == "git_hash_98765"
    assert final_job["response"]["status"] == "SUCCESS"
