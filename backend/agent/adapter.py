"""Tav-owned adapter around Paras's existing agent entry point.

This module is the single boundary between the future Backend/Job system
(Tav-owned) and the existing LangGraph agent (Paras-owned). It deliberately
adds no FastAPI, SQLite, queue, configuration, or retry logic: it simply
forwards a validated SubmissionPayload to agent.runner.run_agent_job and
returns the resulting AgentResponse unchanged.

Error handling is intentionally left as-is for this first version: the
agent's existing exception behavior propagates naturally. The backend error
boundary will be added at the appropriate layer later.
"""

from common.schemas import SubmissionPayload, AgentResponse
from agent.runner import run_agent_job


def execute_agent(payload: SubmissionPayload) -> AgentResponse:
    """Execute the agent pipeline for a submission payload.

    Args:
        payload: validated SubmissionPayload (shared contract).

    Returns:
        The AgentResponse produced by agent.runner.run_agent_job, unchanged.
    """
    return run_agent_job(payload)
