"""Regression test suite for Phase 10.5 Debug fixes:

1. generate_readme_node list content response parsing ('list' object has no attribute 'strip' fix)
2. tags as list
3. tags as comma-separated string
4. tags empty/missing
5. Java language metadata propagation & file creation (Solution.java)
6. API key secret boundaries verification
"""

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent.graph import generate_readme_node
from common.enums import JobStatus
from common.schemas import ProblemInfo, SolutionInfo, SubmissionPayload
from mcp.file_tool import FileTool


class MockListLLM:
    """Mock LLM that returns response.content as a list of strings or dicts."""

    def __init__(self, content_list):
        self.content_list = content_list

    def invoke(self, prompt):
        class MockMessage:
            def __init__(self, content):
                self.content = content
        return MockMessage(self.content_list)


def test_generate_readme_node_handles_list_content_response():
    """Verify generate_readme_node handles LLM returning content as a list without raising AttributeError."""
    state = {
        "status": JobStatus.VALIDATING.value,
        "payload": {
            "job_id": "JOB-LIST-TEST-1",
            "platform": "leetcode",
            "problem": {"title": "Two Sum", "difficulty": "Easy", "tags": ["Array", "Hash Table"]},
            "solution": {"language": "java", "code": "public class Solution {}"},
            "ai_provider": "mock",
        },
        "current_step": "",
        "readme_content": "",
        "file_results": {},
        "commit_hash": "",
        "push_success": None,
        "error_message": "",
        "response": {},
    }

    mock_llm = MockListLLM(["# Two Sum\n\n", "## Problem Description\n\nGiven an array..."])

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("agent.graph.get_llm_provider", lambda **kwargs: mock_llm)
        res_state = generate_readme_node(state)

    assert res_state["status"] == JobStatus.GENERATING_README.value
    assert res_state["error_message"] == ""
    assert res_state["readme_content"].startswith("# Two Sum")


def test_tags_as_list_and_string_and_empty():
    """Verify generate_readme_node safely formats tags represented as list, string, or empty/None."""
    cases = [
        (["Array", "Hash Table"], "Array, Hash Table"),
        ("Array, Hash Table", "Array, Hash Table"),
        ([], ""),
        ("", ""),
        (None, ""),
    ]

    for input_tags, expected_str in cases:
        state = {
            "status": JobStatus.VALIDATING.value,
            "payload": {
                "job_id": "JOB-TAGS-TEST",
                "platform": "leetcode",
                "problem": {"title": "Test Problem", "tags": input_tags},
                "solution": {"language": "python", "code": "pass"},
            },
        }

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = "README content"

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("agent.graph.get_llm_provider", lambda **kwargs: mock_llm)
            res = generate_readme_node(state)

        assert res["status"] == JobStatus.GENERATING_README.value
        # Check that prompt formatting received expected_str for tags
        invoked_prompt = mock_llm.invoke.call_args[0][0]
        assert f"Tags: {expected_str}" in invoked_prompt


def test_java_language_file_tool_creation(tmp_path):
    """Verify FileTool creates Solution.java when language is 'java'."""
    repo = tmp_path / "repo"
    repo.mkdir()

    results = FileTool.write_problem_files(
        repo_path=str(repo),
        platform="leetcode",
        title="Two Sum",
        language="java",
        code="public class Solution {\n    public int[] twoSum() {}\n}",
        readme_content="# Two Sum",
        metadata={"job_id": "JOB-JAVA-1", "language": "java"},
    )

    sol_path = Path(results["solution_filepath"])
    assert sol_path.name == "Solution.java"
    assert sol_path.exists()
    assert "public class Solution" in sol_path.read_text(encoding="utf-8")


def test_api_key_secret_boundaries_preserved(tmp_path):
    """Verify API keys are never persisted in config.json or job repository DB."""
    from backend.config.manager import ConfigManager
    from backend.db.repository import JobRepository

    cfg_file = tmp_path / "config.json"
    mgr = ConfigManager(config_path=cfg_file)
    mgr.set_api_key("gemini", "AIzaSy-secret-key-boundary-test")
    mgr.update_config({"ai_provider": "gemini"})

    # Check config.json
    assert "AIzaSy-secret-key-boundary-test" not in cfg_file.read_text(encoding="utf-8")

    # Check JobRepository DB persistence
    db_file = tmp_path / "test.db"
    repo = JobRepository(db_path=db_file)
    payload = SubmissionPayload(
        job_id="JOB-BOUNDARY-1",
        platform="leetcode",
        problem=ProblemInfo(title="Two Sum"),
        solution=SolutionInfo(language="java", code="class Solution {}"),
        api_key="AIzaSy-secret-key-boundary-test",
    )
    repo.create_job(payload)
    persisted = repo.get_job("JOB-BOUNDARY-1")

    assert "api_key" not in persisted.get("payload", {})
    assert "AIzaSy-secret-key-boundary-test" not in str(persisted)
