import json
import os
import tempfile
import pytest

from common.enums import Platform, Language, JobStatus
from common.schemas import SubmissionPayload, AgentResponse, ProblemInfo, SolutionInfo
from mcp.file_tool import FileTool
from mcp.git_tool import GitTool
from agent.runner import run_agent_job


def test_contracts_schema():
    payload = SubmissionPayload(
        job_id="TEST-001",
        platform="leetcode",
        problem=ProblemInfo(title="Two Sum", difficulty="Easy", url="https://leetcode.com", tags=["array"]),
        solution=SolutionInfo(language="python", code="print('hello')"),
        repository_path="/tmp/repo",
        remote_repo_url="https://github.com/example/repo.git",
    )
    assert payload.api_version == "1.0"
    assert payload.platform == "leetcode"
    assert payload.remote_repo_url == "https://github.com/example/repo.git"

    resp = AgentResponse(
        status="SUCCESS",
        job_id="TEST-001",
        commit_hash="abc1234",
        repository_path="/tmp/repo",
        message="Done",
    )
    assert resp.status == "SUCCESS"


def test_file_tool():
    with tempfile.TemporaryDirectory() as tmp_dir:
        res = FileTool.write_problem_files(
            repo_path=tmp_dir,
            platform="leetcode",
            title="Two Sum",
            language="python",
            code="def two_sum(): pass",
            readme_content="# Two Sum\nSolution readme",
            metadata={"test": "data"},
        )

        expected_dir = os.path.join(tmp_dir, "LeetCode", "Two Sum")
        assert os.path.exists(expected_dir)
        assert os.path.exists(os.path.join(expected_dir, "Solution.py"))
        assert os.path.exists(os.path.join(expected_dir, "README.md"))
        assert os.path.exists(os.path.join(expected_dir, "metadata.json"))

        with open(os.path.join(expected_dir, "metadata.json"), "r") as f:
            meta = json.load(f)
            assert meta["test"] == "data"


def test_git_tool():
    with tempfile.TemporaryDirectory() as tmp_dir:
        GitTool.init_or_open_repo(tmp_dir)

        # Create a file
        dummy_file = os.path.join(tmp_dir, "test.txt")
        with open(dummy_file, "w") as f:
            f.write("hello git")

        commit_hash = GitTool.commit(tmp_dir, platform="leetcode", title="Two Sum")
        assert commit_hash != ""
        assert commit_hash != "NO_CHANGES"


def test_git_tool_set_remote():
    with tempfile.TemporaryDirectory() as tmp_dir:
        GitTool.init_or_open_repo(tmp_dir)

        # Test adding remote
        remote_url = "https://github.com/example/test-repo.git"
        assert GitTool.set_remote(tmp_dir, remote_url) is True

        # Check git remote via subprocess
        code, stdout, stderr = GitTool._run_git_cmd(["remote", "-v"], tmp_dir)
        assert code == 0
        assert remote_url in stdout

        # Test updating remote
        new_remote_url = "https://github.com/example/updated-repo.git"
        assert GitTool.set_remote(tmp_dir, new_remote_url) is True

        code, stdout, stderr = GitTool._run_git_cmd(["remote", "-v"], tmp_dir)
        assert code == 0
        assert new_remote_url in stdout


def test_full_agent_job_success():
    with tempfile.TemporaryDirectory() as tmp_dir:
        payload = SubmissionPayload(
            job_id="JOB-101",
            platform="leetcode",
            problem=ProblemInfo(
                title="Reverse String",
                difficulty="Easy",
                url="https://leetcode.com/problems/reverse-string/",
                tags=["Two Pointers", "String"],
            ),
            solution=SolutionInfo(
                language="python",
                code="class Solution:\n    def reverseString(self, s: list[str]) -> None:\n        s.reverse()\n",
            ),
            repository_path=tmp_dir,
        )

        response = run_agent_job(payload)
        assert response.status == "SUCCESS"
        assert response.job_id == "JOB-101"
        assert response.commit_hash != ""

        # Verify created repository folder structure
        problem_dir = os.path.join(tmp_dir, "LeetCode", "Reverse String")
        assert os.path.exists(problem_dir)
        assert os.path.exists(os.path.join(problem_dir, "Solution.py"))
        assert os.path.exists(os.path.join(problem_dir, "README.md"))
        assert os.path.exists(os.path.join(problem_dir, "metadata.json"))


def test_agent_job_validation_failure():
    # Payload with empty code
    payload_data = {
        "api_version": "1.0",
        "job_id": "JOB-ERR-001",
        "platform": "leetcode",
        "problem": {"title": "Missing Code", "difficulty": "Medium"},
        "solution": {"language": "python", "code": ""},
        "repository_path": "/tmp/dummy",
    }

    response = run_agent_job(payload_data)
    assert response.status == "FAILED"
    assert response.job_id == "JOB-ERR-001"
    assert "empty" in response.message.lower()


def test_llm_provider_dynamic_config(monkeypatch):
    from agent.providers import get_llm_provider, MockLLM

    # 1. Ensure env variables (if any) are ignored when no runtime api_key is supplied
    monkeypatch.setenv("GEMINI_API_KEY", "env_gemini_key_should_be_ignored")
    monkeypatch.setenv("OPENAI_API_KEY", "env_openai_key_should_be_ignored")

    # Without runtime api_key, should fallback to MockLLM despite env vars
    llm_no_key = get_llm_provider(provider_name="gemini")
    assert isinstance(llm_no_key, MockLLM)
    assert "Mock Mode" in llm_no_key.provider

    # 2. Test passing custom provider and dummy key -> returns MockLLM
    llm_dummy = get_llm_provider(provider_name="openai", api_key="dummy_key_123")
    assert isinstance(llm_dummy, MockLLM)
    assert "openai" in llm_dummy.provider.lower()

    # 3. Test payload with dynamic AI provider in agent job execution
    with tempfile.TemporaryDirectory() as tmp_dir:
        payload = SubmissionPayload(
            job_id="JOB-AI-200",
            platform="leetcode",
            problem=ProblemInfo(title="Search Insert Position"),
            solution=SolutionInfo(language="python", code="def searchInsert(): pass"),
            repository_path=tmp_dir,
            ai_provider="anthropic",
            ai_model="claude-3-haiku-20240307",
            api_key="dummy_anthropic_key",
        )
        response = run_agent_job(payload)
        assert response.status == "SUCCESS"
        assert response.job_id == "JOB-AI-200"


