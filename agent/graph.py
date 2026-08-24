import datetime
from typing import Any, Dict, Optional, TypedDict
from langgraph.graph import END, StateGraph

from agent.prompts import README_GENERATION_PROMPT
from agent.providers import get_llm_provider
from common.enums import JobStatus, Platform
from common.errors import CPAssistantError, ErrorCode
from common.schemas import AgentResponse, SubmissionPayload
from mcp.file_tool import FileTool
from mcp.git_tool import GitTool
from mcp.notification_tool import NotificationTool


class AgentState(TypedDict):
    payload: Dict[str, Any]
    status: str
    current_step: str
    readme_content: str
    file_results: Dict[str, str]
    commit_hash: str
    push_success: bool
    error_message: str
    response: Dict[str, Any]


def validate_node(state: AgentState) -> AgentState:
    """Validate incoming payload parameters."""
    NotificationTool.notify_status(
        state["payload"].get("job_id", "UNKNOWN"),
        JobStatus.VALIDATING,
        "Validating submission payload",
    )
    state["status"] = JobStatus.VALIDATING
    state["current_step"] = "validate"

    try:
        payload_data = state["payload"]

        if not payload_data.get("job_id"):
            raise CPAssistantError(ErrorCode.INVALID_JSON, "Missing job_id in payload")

        platform_val = payload_data.get("platform")
        if not platform_val:
            raise CPAssistantError(ErrorCode.INVALID_PLATFORM, "Missing platform in payload")

        valid_platforms = {p.value for p in Platform}
        if platform_val not in valid_platforms:
            raise CPAssistantError(
                ErrorCode.INVALID_PLATFORM,
                f"Unsupported platform '{platform_val}'. Valid platforms: {sorted(valid_platforms)}",
            )

        problem = payload_data.get("problem", {})
        if not problem.get("title"):
            raise CPAssistantError(ErrorCode.INVALID_JSON, "Missing problem title")

        solution = payload_data.get("solution", {})
        if not solution.get("code"):
            raise CPAssistantError(ErrorCode.EMPTY_CODE, "Submission solution code is empty")

    except Exception as e:
        state["error_message"] = str(e)
        state["status"] = JobStatus.FAILED

    return state


def generate_readme_node(state: AgentState) -> AgentState:
    """Generate problem documentation README using configured AI model."""
    if state["status"] == JobStatus.FAILED:
        return state

    job_id = state["payload"].get("job_id", "")
    NotificationTool.notify_status(
        job_id, JobStatus.GENERATING_README, "Generating problem README via AI"
    )
    state["status"] = JobStatus.GENERATING_README
    state["current_step"] = "generate_readme"

    try:
        p_data = state["payload"]
        prob = p_data.get("problem", {})
        sol = p_data.get("solution", {})

        raw_tags = prob.get("tags", [])
        if isinstance(raw_tags, list):
            tags_str = ", ".join([str(t).strip() for t in raw_tags if str(t).strip()])
        elif isinstance(raw_tags, str):
            tags_str = ", ".join([t.strip() for t in raw_tags.split(",") if t.strip()])
        else:
            tags_str = str(raw_tags).strip() if raw_tags else ""

        prompt_input = README_GENERATION_PROMPT.format(
            platform=p_data.get("platform", ""),
            title=prob.get("title", ""),
            difficulty=prob.get("difficulty", "Easy"),
            url=prob.get("url", ""),
            tags=tags_str,
            language=sol.get("language", "text"),
            code=sol.get("code", ""),
        )

        llm = get_llm_provider(
            provider_name=p_data.get("ai_provider") or p_data.get("provider"),
            model_name=p_data.get("ai_model") or p_data.get("model"),
            api_key=p_data.get("api_key") or p_data.get("ai_api_key"),
        )
        response = llm.invoke(prompt_input)

        content_obj = getattr(response, "content", response)
        if isinstance(content_obj, list):
            text_parts = []
            for part in content_obj:
                if isinstance(part, str):
                    text_parts.append(part)
                elif isinstance(part, dict) and "text" in part:
                    text_parts.append(str(part["text"]))
                else:
                    text_parts.append(str(part))
            readme_str = "".join(text_parts)
        else:
            readme_str = str(content_obj)

        state["readme_content"] = readme_str.strip()

    except Exception as e:
        state["error_message"] = f"AI README generation failed: {str(e)}"
        state["status"] = JobStatus.FAILED

    return state


def write_files_node(state: AgentState) -> AgentState:
    """Write Solution, README.md, and metadata.json to repository directory."""
    if state["status"] == JobStatus.FAILED:
        return state

    job_id = state["payload"].get("job_id", "")
    NotificationTool.notify_status(
        job_id, JobStatus.WRITING_FILES, "Writing problem files to repository"
    )
    state["status"] = JobStatus.WRITING_FILES
    state["current_step"] = "write_files"

    try:
        p_data = state["payload"]
        prob = p_data.get("problem", {})
        sol = p_data.get("solution", {})
        repo_path = p_data.get("repository_path", "")

        metadata = {
            "job_id": job_id,
            "platform": p_data.get("platform"),
            "title": prob.get("title"),
            "difficulty": prob.get("difficulty"),
            "url": prob.get("url"),
            "tags": prob.get("tags", []),
            "language": sol.get("language"),
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        results = FileTool.write_problem_files(
            repo_path=repo_path,
            platform=p_data.get("platform", ""),
            title=prob.get("title", ""),
            language=sol.get("language", ""),
            code=sol.get("code", ""),
            readme_content=state.get("readme_content", "# Solution"),
            metadata=metadata,
        )
        state["file_results"] = results

    except Exception as e:
        state["error_message"] = f"File write tool failed: {str(e)}"
        state["status"] = JobStatus.FAILED

    return state


def commit_node(state: AgentState) -> AgentState:
    """Create Git commit for added solution files."""
    if state["status"] == JobStatus.FAILED:
        return state

    job_id = state["payload"].get("job_id", "")
    NotificationTool.notify_status(
        job_id, JobStatus.COMMITTING, "Committing solution to Git"
    )
    state["status"] = JobStatus.COMMITTING
    state["current_step"] = "commit"

    try:
        p_data = state["payload"]
        prob = p_data.get("problem", {})
        repo_path = p_data.get("repository_path", "")

        commit_hash = GitTool.commit(
            repo_path=repo_path,
            platform=p_data.get("platform", ""),
            title=prob.get("title", ""),
        )
        state["commit_hash"] = commit_hash

    except Exception as e:
        state["error_message"] = f"Git commit tool failed: {str(e)}"
        state["status"] = JobStatus.FAILED

    return state


def push_node(state: AgentState) -> AgentState:
    """Push commits to remote Git repository."""
    if state["status"] == JobStatus.FAILED:
        return state

    job_id = state["payload"].get("job_id", "")
    repo_path = state["payload"].get("repository_path", "")
    remote_repo_url = state["payload"].get("remote_repo_url", "")

    if not remote_repo_url or not remote_repo_url.strip():
        # No remote repository configured: solution is committed locally only
        NotificationTool.warning(
            job_id, "No remote repository configured. Solution committed locally only."
        )
        state["push_success"] = None
        return state

    NotificationTool.notify_status(
        job_id, JobStatus.PUSHING, "Pushing commits to remote Git repo"
    )
    state["status"] = JobStatus.PUSHING
    state["current_step"] = "push"

    try:
        pushed = GitTool.push(repo_path=repo_path, remote_url=remote_repo_url)
        if pushed:
            state["push_success"] = True
        else:
            state["push_success"] = False
            state["status"] = JobStatus.FAILED
            state["error_message"] = "Git push failed: No remote repository configured on target repository."
            NotificationTool.error(job_id, "Git push failed: No remote repository configured.")
    except Exception as e:
        state["push_success"] = False
        state["status"] = JobStatus.FAILED
        state["error_message"] = f"Git push failed: {str(e)}"
        NotificationTool.error(job_id, f"Git push failed: {str(e)}")

    return state


def finish_node(state: AgentState) -> AgentState:
    """Finalize agent execution and construct AgentResponse contract."""
    job_id = state["payload"].get("job_id", "")
    repo_path = state["payload"].get("repository_path", "")

    push_succ = state.get("push_success")

    if state["status"] == JobStatus.FAILED:
        NotificationTool.error(
            job_id, f"Job failed: {state.get('error_message', 'Unknown error')}"
        )
        resp = AgentResponse(
            status="FAILED",
            job_id=job_id,
            commit_hash=state.get("commit_hash", ""),
            repository_path=repo_path,
            message=state.get("error_message", "Job processing failed"),
            push_success=push_succ,
        )
    else:
        state["status"] = JobStatus.COMPLETED
        if push_succ is None:
            msg = "Successfully written files and created local Git commit (no remote configured)."
        else:
            msg = "Successfully written files and pushed Git commit."
        NotificationTool.success(job_id, "Job completed successfully")
        resp = AgentResponse(
            status="SUCCESS",
            job_id=job_id,
            commit_hash=state.get("commit_hash", ""),
            repository_path=repo_path,
            message=msg,
            push_success=push_succ,
        )

    state["response"] = resp.model_dump()
    return state


def should_continue(state: AgentState) -> str:
    """Conditional edge router: returns 'failed' or 'next'."""
    if state["status"] == JobStatus.FAILED:
        return "finish"
    return "next"


def create_agent_graph():
    """Build and compile the LangGraph StateGraph."""
    workflow = StateGraph(AgentState)

    workflow.add_node("validate", validate_node)
    workflow.add_node("generate_readme", generate_readme_node)
    workflow.add_node("write_files", write_files_node)
    workflow.add_node("commit", commit_node)
    workflow.add_node("push", push_node)
    workflow.add_node("finish", finish_node)

    workflow.set_entry_point("validate")

    workflow.add_conditional_edges(
        "validate",
        should_continue,
        {"next": "generate_readme", "finish": "finish"},
    )
    workflow.add_conditional_edges(
        "generate_readme",
        should_continue,
        {"next": "write_files", "finish": "finish"},
    )
    workflow.add_conditional_edges(
        "write_files",
        should_continue,
        {"next": "commit", "finish": "finish"},
    )
    workflow.add_conditional_edges(
        "commit",
        should_continue,
        {"next": "push", "finish": "finish"},
    )
    workflow.add_edge("push", "finish")
    workflow.add_edge("finish", END)

    return workflow.compile()
