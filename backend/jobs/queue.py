"""Durable SQLite-backed Job Queue abstraction for GhostPush backend."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from common.enums import JobStatus
from common.schemas import AgentResponse, SubmissionPayload
from backend.db.repository import JobRepository


class JobQueue:
    """Queue abstraction operating on SQLite JobRepository as source of truth."""

    def __init__(
        self,
        repository: Optional[JobRepository] = None,
        db_path: Optional[Path] = None,
    ):
        self.repository = repository or JobRepository(db_path=db_path)

    def enqueue(self, payload: SubmissionPayload) -> Dict[str, Any]:
        """Enqueue a SubmissionPayload into SQLite as a QUEUED job."""
        return self.repository.create_job(payload, status=JobStatus.QUEUED)

    def claim_next_job(self) -> Optional[Dict[str, Any]]:
        """Atomically claim the oldest QUEUED job and transition status to PROCESSING."""
        return self.repository.claim_next_job()

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a job by job_id."""
        return self.repository.get_job(job_id)

    def list_jobs(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """List job records sorted by creation timestamp descending."""
        return self.repository.list_jobs(limit=limit, offset=offset)

    def complete_job(self, job_id: str, response: AgentResponse) -> bool:
        """Record the final AgentResponse and set job status to COMPLETED or FAILED."""
        return self.repository.complete_job(job_id, response)

    def fail_job(self, job_id: str, error_message: str) -> bool:
        """Transition job status to FAILED and record error message."""
        return self.repository.update_job_status(
            job_id=job_id,
            status=JobStatus.FAILED,
            error_message=error_message,
        )
