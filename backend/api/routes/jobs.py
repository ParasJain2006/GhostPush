from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query, Request, status

from common.errors import GhostPushError
from common.schemas import SubmissionPayload
from backend.jobs.queue import JobQueue

router = APIRouter(prefix="/jobs", tags=["Jobs"])


def _get_queue(request: Request) -> JobQueue:
    queue = getattr(request.app.state, "queue", None)
    if queue is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Job queue service unavailable.",
        )
    return queue


@router.post("", status_code=status.HTTP_201_CREATED)
def create_job(payload: SubmissionPayload, request: Request) -> Dict[str, Any]:
    """Enqueue a SubmissionPayload for processing."""
    queue = _get_queue(request)
    try:
        job_rec = queue.enqueue(payload)
    except GhostPushError as e:
        if "already exists" in e.message:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=e.message,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )
    return job_rec


@router.get("", status_code=status.HTTP_200_OK)
def list_jobs(
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> List[Dict[str, Any]]:
    """List jobs with pagination."""
    queue = _get_queue(request)
    return queue.list_jobs(limit=limit, offset=offset)


@router.get("/{job_id}", status_code=status.HTTP_200_OK)
def get_job(job_id: str, request: Request) -> Dict[str, Any]:
    """Retrieve a specific job by job_id."""
    queue = _get_queue(request)
    job_rec = queue.get_job(job_id)
    if not job_rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found.",
        )
    return job_rec
