"""Focused tests for the Tav-owned agent adapter (backend.agent.adapter).

These tests mock the agent entry point (agent.runner.run_agent_job) instead of
executing the real LangGraph agent.
"""

from unittest.mock import patch

from common.schemas import SubmissionPayload, AgentResponse, ProblemInfo, SolutionInfo
from backend.agent.adapter import execute_agent


def _make_payload(job_id: str = "ADAPTER-TEST-001") -> SubmissionPayload:
    return SubmissionPayload(
        job_id=job_id,
        platform="leetcode",
        problem=ProblemInfo(title="Two Sum", difficulty="Easy"),
        solution=SolutionInfo(language="python", code="def two_sum(): pass"),
        repository_path="/tmp/repo",
    )


def test_execute_agent_forwards_payload_and_returns_response_unchanged():
    payload = _make_payload()
    expected = AgentResponse(
        status="SUCCESS",
        job_id=payload.job_id,
        commit_hash="abc123",
        repository_path=payload.repository_path,
        message="Done",
    )

    # The adapter binds run_agent_job at import time via
    # `from agent.runner import run_agent_job`, so the local binding in
    # backend.agent.adapter is patched to intercept the call without running
    # the real LangGraph graph.
    with patch("backend.agent.adapter.run_agent_job", return_value=expected) as mock_run:
        result = execute_agent(payload)

    # run_agent_job is called exactly once, with the payload passed through.
    mock_run.assert_called_once_with(payload)
    # The exact AgentResponse returned by run_agent_job is returned unchanged.
    assert result is expected
