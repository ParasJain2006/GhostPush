import time
from unittest.mock import patch, MagicMock

import pytest

from common.enums import JobStatus
from common.errors import ErrorCode, GhostPushError
from common.schemas import AgentResponse, ProblemInfo, SolutionInfo, SubmissionPayload
from backend.db.repository import JobRepository
from backend.jobs.queue import JobQueue
from backend.jobs.worker import JobWorker


def _make_payload(job_id: str = "JOB-TEST-001") -> SubmissionPayload:
    return SubmissionPayload(
        job_id=job_id,
        platform="leetcode",
        problem=ProblemInfo(title="Two Sum", difficulty="Easy"),
        solution=SolutionInfo(language="python", code="def two_sum(): pass"),
        repository_path="/tmp/test_repo",
    )


def test_queue_enqueue_payload(tmp_path):
    db_file = tmp_path / "test_queue.db"
    queue = JobQueue(db_path=db_file)

    payload = _make_payload("JOB-ENQ-1")
    job_rec = queue.enqueue(payload)

    assert job_rec["job_id"] == "JOB-ENQ-1"
    assert job_rec["status"] == JobStatus.QUEUED.value
    assert job_rec["platform"] == "leetcode"


def test_worker_claims_queued_job(tmp_path):
    db_file = tmp_path / "test_claim.db"
    queue = JobQueue(db_path=db_file)

    payload = _make_payload("JOB-CLAIM-1")
    queue.enqueue(payload)

    claimed = queue.claim_next_job()
    assert claimed is not None
    assert claimed["job_id"] == "JOB-CLAIM-1"
    assert claimed["status"] == JobStatus.PROCESSING.value

    # Submitting another claim when queue is empty returns None
    assert queue.claim_next_job() is None


def test_worker_calls_execute_agent(tmp_path):
    db_file = tmp_path / "test_exec.db"
    queue = JobQueue(db_path=db_file)
    payload = _make_payload("JOB-EXEC-1")
    queue.enqueue(payload)

    worker = JobWorker(queue=queue, poll_interval=0.05)

    expected_resp = AgentResponse(
        status="SUCCESS",
        job_id=payload.job_id,
        commit_hash="git_123",
        repository_path=payload.repository_path,
        message="Completed successfully",
    )

    with patch("backend.jobs.worker.execute_agent", return_value=expected_resp) as mock_exec:
        processed = worker.process_one_job()

    assert processed is True
    mock_exec.assert_called_once()
    assert mock_exec.call_args[0][0].job_id == "JOB-EXEC-1"

    job_rec = queue.get_job("JOB-EXEC-1")
    assert job_rec["status"] == JobStatus.COMPLETED.value
    assert job_rec["commit_hash"] == "git_123"


def test_successful_agent_response_results_in_completed(tmp_path):
    db_file = tmp_path / "test_succ.db"
    queue = JobQueue(db_path=db_file)
    payload = _make_payload("JOB-SUCC-1")
    queue.enqueue(payload)

    worker = JobWorker(queue=queue, poll_interval=0.05)

    success_resp = AgentResponse(
        status="SUCCESS",
        job_id="JOB-SUCC-1",
        commit_hash="hash999",
        repository_path=payload.repository_path,
        message="All good",
    )

    with patch("backend.jobs.worker.execute_agent", return_value=success_resp):
        worker.process_one_job()

    job_rec = queue.get_job("JOB-SUCC-1")
    assert job_rec["status"] == JobStatus.COMPLETED.value
    assert job_rec["commit_hash"] == "hash999"


def test_failed_agent_response_results_in_failed(tmp_path):
    db_file = tmp_path / "test_fail_resp.db"
    queue = JobQueue(db_path=db_file)
    payload = _make_payload("JOB-FAIL-1")
    queue.enqueue(payload)

    worker = JobWorker(queue=queue, poll_interval=0.05)

    failed_resp = AgentResponse(
        status="FAILED",
        job_id="JOB-FAIL-1",
        repository_path=payload.repository_path,
        message="AI generation timed out",
    )

    with patch("backend.jobs.worker.execute_agent", return_value=failed_resp):
        worker.process_one_job()

    job_rec = queue.get_job("JOB-FAIL-1")
    assert job_rec["status"] == JobStatus.FAILED.value
    assert "timed out" in job_rec["error_message"]


def test_ghostpush_error_does_not_kill_worker(tmp_path):
    db_file = tmp_path / "test_gperror.db"
    queue = JobQueue(db_path=db_file)
    payload = _make_payload("JOB-GPERR-1")
    queue.enqueue(payload)

    worker = JobWorker(queue=queue, poll_interval=0.05)

    gp_error = GhostPushError(ErrorCode.GIT_FAILED, "Git commit failed unexpectedly")

    with patch("backend.jobs.worker.execute_agent", side_effect=gp_error):
        processed = worker.process_one_job()

    assert processed is True
    job_rec = queue.get_job("JOB-GPERR-1")
    assert job_rec["status"] == JobStatus.FAILED.value
    assert "GIT_FAILED" in job_rec["error_message"]


def test_unexpected_exception_does_not_kill_worker(tmp_path):
    db_file = tmp_path / "test_exc.db"
    queue = JobQueue(db_path=db_file)
    payload = _make_payload("JOB-EXC-1")
    queue.enqueue(payload)

    worker = JobWorker(queue=queue, poll_interval=0.05)

    with patch("backend.jobs.worker.execute_agent", side_effect=RuntimeError("Unexpected LLM Crash")):
        processed = worker.process_one_job()

    assert processed is True
    job_rec = queue.get_job("JOB-EXC-1")
    assert job_rec["status"] == JobStatus.FAILED.value
    assert "Unexpected LLM Crash" in job_rec["error_message"]


def test_worker_continues_processing_after_failed_job(tmp_path):
    db_file = tmp_path / "test_continue.db"
    queue = JobQueue(db_path=db_file)

    payload1 = _make_payload("JOB-MULTI-1")
    payload2 = _make_payload("JOB-MULTI-2")
    queue.enqueue(payload1)
    queue.enqueue(payload2)

    worker = JobWorker(queue=queue, poll_interval=0.05)

    success_resp = AgentResponse(
        status="SUCCESS",
        job_id="JOB-MULTI-2",
        commit_hash="hash222",
        repository_path=payload2.repository_path,
        message="Success 2",
    )

    def mock_agent(payload):
        if payload.job_id == "JOB-MULTI-1":
            raise GhostPushError(ErrorCode.FILE_WRITE_FAILED, "File write error on job 1")
        return success_resp

    with patch("backend.jobs.worker.execute_agent", side_effect=mock_agent):
        worker.process_one_job()
        worker.process_one_job()

    job1 = queue.get_job("JOB-MULTI-1")
    job2 = queue.get_job("JOB-MULTI-2")

    assert job1["status"] == JobStatus.FAILED.value
    assert job2["status"] == JobStatus.COMPLETED.value


def test_worker_stop_cleanly_terminates(tmp_path):
    db_file = tmp_path / "test_stop.db"
    queue = JobQueue(db_path=db_file)
    worker = JobWorker(queue=queue, poll_interval=0.05)

    worker.start()
    assert worker.is_alive()

    worker.stop()
    worker.join(timeout=1.0)
    assert not worker.is_alive()


def test_two_workers_cannot_process_same_queued_job(tmp_path):
    db_file = tmp_path / "test_concurrency.db"
    queue = JobQueue(db_path=db_file)

    payload = _make_payload("JOB-SINGLE-CLAIM")
    queue.enqueue(payload)

    worker1 = JobWorker(queue=queue, poll_interval=0.05)
    worker2 = JobWorker(queue=queue, poll_interval=0.05)

    success_resp = AgentResponse(
        status="SUCCESS",
        job_id="JOB-SINGLE-CLAIM",
        commit_hash="single_hash",
        repository_path=payload.repository_path,
        message="Done",
    )

    with patch("backend.jobs.worker.execute_agent", return_value=success_resp) as mock_exec:
        # Worker 1 processes the job
        res1 = worker1.process_one_job()
        # Worker 2 attempts to process when queue is now empty
        res2 = worker2.process_one_job()

    assert res1 is True
    assert res2 is False
    # execute_agent is called exactly once
    assert mock_exec.call_count == 1
