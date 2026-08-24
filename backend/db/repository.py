"""JobRepository for SQLite persistence of SubmissionPayload and AgentResponse."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from common.enums import JobStatus
from common.errors import ErrorCode, GhostPushError
from common.schemas import AgentResponse, SubmissionPayload
from backend.db.database import get_db_connection, init_db


class JobRepository:
    """Data Access Object for Job record persistence in SQLite."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path
        init_db(self.db_path)

    def _get_connection(self) -> sqlite3.Connection:
        return get_db_connection(self.db_path)

    def create_job(
        self,
        payload: SubmissionPayload,
        status: JobStatus = JobStatus.QUEUED,
    ) -> Dict[str, Any]:
        """Ingest a SubmissionPayload, strip secret fields, and persist job record."""
        payload_dict = payload.model_dump()
        # Explicitly remove secret fields from stored payload JSON
        payload_dict.pop("api_key", None)

        payload_json = json.dumps(payload_dict, ensure_ascii=False)
        now_iso = datetime.now(timezone.utc).isoformat()

        job_id = payload.job_id
        platform = payload.platform
        title = payload.problem.title
        language = payload.solution.language

        query = """
        INSERT INTO jobs (
            job_id, status, platform, title, language,
            payload_json, response_json, commit_hash, error_message,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?)
        """

        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    query,
                    (
                        job_id,
                        status.value,
                        platform,
                        title,
                        language,
                        payload_json,
                        now_iso,
                        now_iso,
                    ),
                )
        except sqlite3.IntegrityError as e:
            raise GhostPushError(
                ErrorCode.SQLITE_ERROR,
                f"Job record with job_id '{job_id}' already exists.",
                details=str(e),
            )
        except Exception as e:
            raise GhostPushError(
                ErrorCode.SQLITE_ERROR,
                f"Failed to insert job record '{job_id}'.",
                details=str(e),
            )
        finally:
            conn.close()

        return self.get_job(job_id) or {}

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a job record by job_id."""
        query = "SELECT * FROM jobs WHERE job_id = ?"
        conn = self._get_connection()
        try:
            cur = conn.execute(query, (job_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_dict(row)
        finally:
            conn.close()

    def list_jobs(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """List job records sorted by creation date descending."""
        query = "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?"
        conn = self._get_connection()
        try:
            cur = conn.execute(query, (limit, offset))
            rows = cur.fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    def fetch_next_queued_job(self) -> Optional[Dict[str, Any]]:
        """Fetch the oldest queued job for worker execution."""
        query = "SELECT * FROM jobs WHERE status = ? ORDER BY created_at ASC LIMIT 1"
        conn = self._get_connection()
        try:
            cur = conn.execute(query, (JobStatus.QUEUED.value,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_dict(row)
        finally:
            conn.close()

    def claim_next_job(self) -> Optional[Dict[str, Any]]:
        """Atomically claim the oldest QUEUED job and transition its status to PROCESSING."""
        conn = self._get_connection()
        try:
            with conn:
                cur = conn.execute(
                    "SELECT job_id FROM jobs WHERE status = ? ORDER BY created_at ASC LIMIT 1",
                    (JobStatus.QUEUED.value,),
                )
                row = cur.fetchone()
                if not row:
                    return None

                job_id = row["job_id"]
                now_iso = datetime.now(timezone.utc).isoformat()

                cur_upd = conn.execute(
                    "UPDATE jobs SET status = ?, updated_at = ? WHERE job_id = ? AND status = ?",
                    (JobStatus.PROCESSING.value, now_iso, job_id, JobStatus.QUEUED.value),
                )
                if cur_upd.rowcount == 0:
                    return None
            return self.get_job(job_id)
        finally:
            conn.close()

    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update a job's status and updated_at timestamp."""
        now_iso = datetime.now(timezone.utc).isoformat()
        if error_message:
            query = "UPDATE jobs SET status = ?, error_message = ?, updated_at = ? WHERE job_id = ?"
            params = (status.value, error_message, now_iso, job_id)
        else:
            query = "UPDATE jobs SET status = ?, updated_at = ? WHERE job_id = ?"
            params = (status.value, now_iso, job_id)

        conn = self._get_connection()
        try:
            with conn:
                cur = conn.execute(query, params)
                return cur.rowcount > 0
        finally:
            conn.close()

    def complete_job(self, job_id: str, response: AgentResponse) -> bool:
        """Record the final AgentResponse and set terminal status."""
        now_iso = datetime.now(timezone.utc).isoformat()
        resp_dict = response.model_dump()
        resp_json = json.dumps(resp_dict, ensure_ascii=False)

        final_status = JobStatus.COMPLETED.value if response.status == "SUCCESS" else JobStatus.FAILED.value
        commit_hash = response.commit_hash or None
        error_msg = response.message if response.status != "SUCCESS" else None

        push_succ_val: Optional[int] = None
        if response.push_success is True:
            push_succ_val = 1
        elif response.push_success is False:
            push_succ_val = 0

        query = """
        UPDATE jobs
        SET status = ?, response_json = ?, commit_hash = ?, push_success = ?, error_message = ?, updated_at = ?
        WHERE job_id = ?
        """

        conn = self._get_connection()
        try:
            with conn:
                cur = conn.execute(
                    query,
                    (final_status, resp_json, commit_hash, push_succ_val, error_msg, now_iso, job_id),
                )
                return cur.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        if "push_success" in d:
            val = d["push_success"]
            if val == 1:
                d["push_success"] = True
            elif val == 0:
                d["push_success"] = False
            else:
                d["push_success"] = None

        if d.get("payload_json"):
            try:
                d["payload"] = json.loads(d["payload_json"])
            except Exception:
                d["payload"] = {}
        if d.get("response_json"):
            try:
                d["response"] = json.loads(d["response_json"])
            except Exception:
                d["response"] = None
        return d
