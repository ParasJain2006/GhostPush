# GhostPush — Paras Architecture & Integration Report

**Scope:** Reverse-engineering of Developer B (Paras)'s existing implementation as it actually exists in the repository.
**Audience:** Developer A (Tav), who must build the surrounding infrastructure (backend, REST, WebSocket, SQLite, job queue, config, tray, extension, installer, repo initialization) against this code.
**Ground truth:** Source files only. Where `docs/ARCHITECTURE_AND_WORKFLOW.md` / `docs/RECREATION_GUIDE.md` disagree with code, the code wins and the discrepancy is flagged.

---

## 0. Repository Inventory

```
GhostPush-main/
├── .env.example              # Documented env vars (API keys, default AI settings)
├── .gitignore                # .env, __pycache__, pytest cache, IDE dirs
├── LICENSE                   # EMPTY (0 bytes)
├── README.md                 # EMPTY (0 bytes)
├── requirements.txt          # Dependency floor constraints only
├── test_github_push.py       # Standalone manual push test against a real GitHub repo URL
│
├── agent/                    # Paras: LangGraph agent core (COMPLETE)
│   ├── __init__.py           # Re-exports get_llm_provider, README_GENERATION_PROMPT, create_agent_graph, run_agent_job
│   ├── graph.py              # LangGraph StateGraph: 6 nodes, conditional routing, compile()
│   ├── prompts.py            # README_GENERATION_PROMPT (langchain_core PromptTemplate)
│   ├── providers.py          # get_llm_provider factory + MockLLM fallback
│   └── runner.py             # run_agent_job() — the ONLY external entry point
│
├── backend/                  # Tav: EMPTY (.gitkeep only)
├── extension/                # Tav: EMPTY (.gitkeep only)
├── tray/                     # Tav: EMPTY (.gitkeep only)
├── scripts/                  # EMPTY (.gitkeep only)
│
├── common/                   # Shared (docs list "Paras & Tav")
│   ├── __init__.py           # Re-exports all shared symbols
│   ├── constants.py          # API_VERSION, LANGUAGE_EXTENSIONS, PLATFORM_DIR_NAMES, DEFAULT_SOLUTION_FILENAMES
│   ├── enums.py              # Platform, Language, JobStatus
│   ├── errors.py             # ErrorCode, GhostPushError (alias CPAssistantError)
│   └── schemas.py            # ProblemInfo, SolutionInfo, SubmissionPayload, AgentResponse
│
├── docs/                     # ARCHITECTURE_AND_WORKFLOW.md, RECREATION_GUIDE.md (Paras design docs)
├── mcp/                      # Paras: "MCP" tools (COMPLETE)
│   ├── __init__.py           # Re-exports FileTool, GitTool, NotificationTool
│   ├── file_tool.py          # FileTool — repo folder structure + file writing
│   ├── git_tool.py           # GitTool — subprocess git wrapper
│   └── notification_tool.py  # NotificationTool — logging-based status events
│
└── tests/                    # test_agent.py (7 tests) + __init__.py
```

**Important note on the "MCP" directory:** `mcp/` is a naming convention only. There is **no MCP SDK/server, no `mcp` package dependency, no tool schema metadata (inputSchema/outputSchema), no FastMCP** anywhere. The classes are plain static-method Python utilities.

**Runtime environment observed during analysis:** Python 3.14.6 installed; **zero project dependencies installed** (langgraph, langchain-core, pydantic, pytest all `ModuleNotFoundError`). No `pyproject.toml`, `setup.py`, `conftest.py`, CI, lint, or typecheck config exists.

---

## 1. Dependency Declarations (`requirements.txt`)

All are floor constraints (`>=`); **no pins**, so exact resolved versions are not determinable from the repo.

| Declared dependency | Constraint | Where actually imported |
|---|---|---|
| `langchain` | `>=0.2.0` | never directly imported |
| `langgraph` | `>=0.1.0` | `agent/graph.py:3` (`StateGraph`, `END`) |
| `langchain-core` | `>=0.2.0` | `agent/prompts.py:1` (`PromptTemplate`) |
| `langchain-google-genai` | `>=1.0.0` | `agent/providers.py:61` (`ChatGoogleGenerativeAI`) |
| `langchain-openai` | `>=0.1.0` | `agent/providers.py:75,102` (`ChatOpenAI`) |
| `pydantic` | `>=2.0.0` | `common/schemas.py:2` |
| `python-dotenv` | `>=1.0.0` | **never imported** (declared only) |
| `GitPython` | `>=3.1.0` | **never imported** (git ops are subprocess-based) |
| `pytest` | `>=8.0.0` | `tests/test_agent.py:4` |

**Dependency gaps found in code but NOT declared:**
- `langchain_community` — `agent/providers.py:89` imports `from langchain_community.chat_models import ChatAnthropic`. **Not in requirements.txt.** Consequence: the `anthropic` provider can only ever fall back to `MockLLM` unless this package is added.
- Standard library used: `os`, `json`, `logging`, `datetime`, `subprocess`, `typing`, `enum`, `tempfile`.

**Version caveats:**
- Docs state Python 3.10+ (`docs/RECREATION_GUIDE.md`). Installed interpreter is 3.14.6; LangGraph ≥0.1.0 / LangChain ≥0.2.0 compatibility with 3.14 is unverified.
- No frontend/JS tech anywhere. `extension/` and `tray/` are empty placeholders. No `package.json`, manifest, or HTML.

---

## 2. Shared Layer (`common/`)

### 2.1 `common/constants.py`
- `API_VERSION = "1.0"`
- `LANGUAGE_EXTENSIONS` — maps `python/py→.py`, `java→.java`, `cpp/c++→.cpp`, `javascript/js→.js`, `typescript/ts→.ts`
- `PLATFORM_DIR_NAMES` — `leetcode→LeetCode`, `gfg→GFG`, `codeforces→Codeforces`, `hackerrank→HackerRank`
- `DEFAULT_SOLUTION_FILENAMES` — `.py→Solution.py`, `.java→Solution.java`, `.cpp→Solution.cpp`, `.js→Solution.js`, `.ts→Solution.ts`

### 2.2 `common/enums.py`
- `Platform(str, Enum)`: `LEETCODE="leetcode"`, `GFG="gfg"`, `CODEFORCES="codeforces"`, `HACKERRANK="hackerrank"`
- `Language(str, Enum)`: `PYTHON="python"`, `JAVA="java"`, `CPP="cpp"`, `JAVASCRIPT="javascript"`, `TYPESCRIPT="typescript"`
- `JobStatus(str, Enum)`: `CREATED`, `VALIDATING`, `QUEUED`, `PROCESSING`, `GENERATING_README`, `WRITING_FILES`, `COMMITTING`, `PUSHING`, `COMPLETED`, `FAILED`
  - **Note:** `QUEUED` and `PROCESSING` are declared but **never emitted by the agent graph**. They appear reserved for Tav's queue/backend lifecycle.

### 2.3 `common/errors.py`
- `ErrorCode(str, Enum)`: `INVALID_PLATFORM`, `INVALID_JSON`, `EMPTY_CODE`, `GIT_FAILED`, `AI_TIMEOUT`, `FILE_WRITE_FAILED`, `SQLITE_ERROR`, `NETWORK_ERROR`
  - **Note:** `SQLITE_ERROR` and `NETWORK_ERROR` are declared but never raised — placeholders for Tav.
- `GhostPushError(Exception)` — `__init__(self, code: ErrorCode, message: str, details: Optional[str] = None)`; exposes `.code`, `.message`, `.details`, `.to_dict() -> {"error_code","message","details"}`.
- `CPAssistantError = GhostPushError` (backward-compat alias, `common/errors.py:34`).

### 2.4 `common/schemas.py` (Pydantic v2) — THE WIRE CONTRACT

```python
class ProblemInfo(BaseModel):
    title: str = Field(..., ...)
    difficulty: str = Field(default="Easy")
    url: str = Field(default="")
    tags: List[str] = Field(default_factory=list)

class SolutionInfo(BaseModel):
    language: str = Field(..., ...)
    code: str = Field(..., ...)

class SubmissionPayload(BaseModel):
    api_version: str = Field(default=API_VERSION)          # "1.0"
    job_id: str = Field(..., ...)                          # REQUIRED
    platform: str = Field(..., ...)                        # REQUIRED
    problem: ProblemInfo
    solution: SolutionInfo
    repository_path: str = Field(default="")               # absolute path to target local git repo
    remote_repo_url: Optional[str] = Field(default="")     # e.g. https://github.com/user/repo.git
    ai_provider: Optional[str] = Field(default="")         # gemini | openai | anthropic | groq
    ai_model: Optional[str] = Field(default="")
    api_key: Optional[str] = Field(default="")

class AgentResponse(BaseModel):
    status: str = Field(..., ...)        # "SUCCESS" | "FAILED" — FREE STRING, not JobStatus
    job_id: str = Field(..., ...)
    commit_hash: str = Field(default="")
    repository_path: str = Field(default="")
    message: str = Field(default="")
```

`common/__init__.py` re-exports: `Platform, Language, JobStatus, SubmissionPayload, ProblemInfo, SolutionInfo, AgentResponse, ErrorCode, GhostPushError, CPAssistantError, API_VERSION, LANGUAGE_EXTENSIONS, PLATFORM_DIR_NAMES`.

---

## 3. Agent Entry Point (the ONLY external interface)

**Module:** `agent/runner.py`
**Function:** `run_agent_job`
**Exact signature:** `run_agent_job(payload: Union[SubmissionPayload, Dict[str, Any]]) -> AgentResponse`
**File/line:** `agent/runner.py:6`

Behavior (`agent/runner.py:15-36`):
1. Coerces `SubmissionPayload` → dict via `.model_dump()`; a raw dict is used as-is (no schema validation on the dict path).
2. Builds `initial_state` dict with keys: `payload, status="CREATED", current_step="init", readme_content="", file_results={}, commit_hash="", push_success=False, error_message="", response={}`.
3. `graph = create_agent_graph()` then `final_state = graph.invoke(initial_state)` — **synchronous**.
4. Returns `AgentResponse(**final_state.get("response", {}))`.

**Key facts for Tav:**
- **Synchronous, blocking.** It blocks until the LLM call and git operations complete. A Background Service must invoke it off the event loop (thread/process pool).
- **No async variant exists** (no `ainvoke`, `astream`).
- **No top-level try/except around `graph.invoke`** (`agent/runner.py:32-33`). Logical job failures return `AgentResponse(status="FAILED", ...)` (never raise), but unexpected library/LangGraph exceptions **propagate to the caller**.
- **No DB, no queue, no config-file coupling.** Pure function.
- `create_agent_graph()` is recompiled on every call.

**Example invocation** (from `test_github_push.py:27-49`): build `SubmissionPayload(...)` and call `response = run_agent_job(payload)`; print `response.model_dump_json(indent=2)`.

Also present: `if __name__ == "__main__"` demo in `agent/runner.py:39-64` (temp-dir Two Sum run).

---

## 4. LangGraph Flow (`agent/graph.py`)

### 4.1 State
`AgentState` is a `TypedDict` (`agent/graph.py:15-24`):
```python
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
```

### 4.2 Graph construction (`create_agent_graph`, `agent/graph.py:245-281`)
- `StateGraph(AgentState)`; nodes: `validate`, `generate_readme`, `write_files`, `commit`, `push`, `finish`.
- `set_entry_point("validate")`.
- Conditional edges (`should_continue`, `agent/graph.py:238-242` → returns `"finish"` if `status == JobStatus.FAILED` else `"next"`) at `validate`, `generate_readme`, `write_files`, `commit`, each with map `{"next": <next_node>, "finish": "finish"}`.
- Plain edges: `push → finish`, `finish → END`.
- `return workflow.compile()` — **NO checkpointer.** No persistence, no `thread_id`, no resume.

### 4.3 Node-by-node behavior

| Node | File:Line | Signature | Work | Failure behavior |
|---|---|---|---|---|
| `validate_node` | `agent/graph.py:27` | `(state: AgentState) -> AgentState` | Notify VALIDATING; require `payload.job_id`, `payload.platform`, `problem.title`, `solution.code` (presence only — **does not check enums**). | Raises `CPAssistantError(INVALID_JSON/INVALID_PLATFORM/EMPTY_CODE)`; caught → `status=FAILED`, `error_message` |
| `generate_readme_node` | `agent/graph.py:61` | `(state: AgentState) -> AgentState` | Notify GENERATING_README; format `README_GENERATION_PROMPT`; `llm = get_llm_provider(provider_name=payload.ai_provider or payload.provider, model_name=payload.ai_model or payload.model, api_key=payload.api_key or payload.ai_api_key)`; `response = llm.invoke(prompt)`; `readme_content = getattr(response, "content", str(response)).strip()`. | On exception → FAILED, message `"AI README generation failed: ..."` |
| `write_files_node` | `agent/graph.py:104` | `(state: AgentState) -> AgentState` | Notify WRITING_FILES; build `metadata` dict (`job_id, platform, title, difficulty, url, tags, language, created_at` UTC ISO); `results = FileTool.write_problem_files(repo_path, platform, title, language, code, readme_content or "# Solution", metadata)`; store in `file_results`. | On exception → FAILED, message `"File write tool failed: ..."` |
| `commit_node` | `agent/graph.py:151` | `(state: AgentState) -> AgentState` | Notify COMMITTING; `commit_hash = GitTool.commit(repo_path, platform, title)`. | On exception → FAILED, message `"Git commit tool failed: ..."` |
| `push_node` | `agent/graph.py:182` | `(state: AgentState) -> AgentState` | Notify PUSHING; `pushed = GitTool.push(repo_path, remote_url=payload.remote_repo_url)`; store in `push_success`. | On exception → **warning only** (`NotificationTool.warning`), `push_success=False`; **job does NOT fail** |
| `finish_node` | `agent/graph.py:207` | `(state: AgentState) -> AgentState` | If FAILED → `AgentResponse(status="FAILED", ...)` + `NotificationTool.error`; else set `COMPLETED`, `AgentResponse(status="SUCCESS", commit_hash=..., message="Successfully written files and created Git commit.")`; store `resp.model_dump()` in `state["response"]`. | n/a |

### 4.4 Normal path
`validate → generate_readme → write_files → commit → push → finish → END`

### 4.5 Input/Output format
- **Input:** full `AgentState` dict with `payload` populated (`runner.py` seeds `status="CREATED"`).
- **Output:** final `AgentState`; the meaningful payload is `state["response"]` — a dict that round-trips into `AgentResponse`.

---

## 5. MCP Tools (Paras-owned)

**Important:** these are plain Python classes, not MCP-schema tools. `inputSchema`/`outputSchema` are the Python signatures below. Exceptions are `GhostPushError` with `ErrorCode.GIT_FAILED` or `FILE_WRITE_FAILED`.

### 5.1 `mcp/file_tool.py` — `FileTool`

| Member | Signature | Purpose | Returns | Errors | Side effects |
|---|---|---|---|---|---|
| `format_platform_name` | `@staticmethod (platform: str) -> str` | Platform id → dir name via `PLATFORM_DIR_NAMES`; fallback `platform.capitalize()` | str | none | none |
| `get_extension_for_language` | `@staticmethod (language: str) -> str` | Language → extension via `LANGUAGE_EXTENSIONS`; if unknown and starts with `.` passthrough, else `".txt"` | str | none | none |
| `write_problem_files` | `@classmethod (cls, repo_path: str, platform: str, title: str, language: str, code: str, readme_content: str, metadata: dict) -> dict` | Creates `<repo_path>/<PlatformDir>/<title.strip()>/` and writes `Solution.<ext>`, `README.md`, `metadata.json` | dict `{target_dir, solution_filepath, readme_filepath, metadata_filepath}` | `GhostPushError(FILE_WRITE_FAILED)` on empty repo_path, mkdir failure, or write failure | Creates dirs; **silently overwrites** existing files |

**Path construction (`file_tool.py:49-52`):** `os.path.join(repo_path, format_platform_name(platform), title.strip())`.
**File naming (`file_tool.py:62-67`):** `ext = get_extension_for_language(language)`; `solution_filename = DEFAULT_SOLUTION_FILENAMES.get(ext, f"Solution{ext}")`.
**Writing (`file_tool.py:68-79`):** solution code written verbatim; `README.md` written verbatim (fallback `"# Solution"` if AI returned empty); `metadata.json` via `json.dump(metadata, indent=2, ensure_ascii=False)`.

**Path-safety gaps (Tav awareness):** no normalization, no `..` traversal check, no Windows-illegal-character check, no symlink check, no existence/conflict detection.

### 5.2 `mcp/git_tool.py` — `GitTool`

All git ops shell out via `subprocess.run(["git", ...], cwd, capture_output=True, text=True, check=False)`; `_run_git_cmd(cmd: list, cwd: str) -> Tuple[int, str, str]` returns `(returncode, stdout.strip(), stderr.strip())`; a raised `Exception` returns `(1, "", str(e))`.

| Member | Signature | Purpose | Returns | Errors | Side effects |
|---|---|---|---|---|---|
| `_run_git_cmd` | `@staticmethod (cmd: list, cwd: str) -> Tuple[int,str,str]` | run git subprocess | (rc, stdout, stderr) | none (swallows exceptions) | executes git |
| `init_or_open_repo` | `@classmethod (cls, repo_path: str) -> bool` | `os.makedirs(exist_ok=True)`; `git init` if `.git` absent | bool | `GhostPushError(GIT_FAILED)` on init failure | creates dirs / `.git` |
| `set_remote` | `@classmethod (cls, repo_path: str, remote_url: str, remote_name: str = "origin") -> bool` | add or `git remote set-url` | `False` if no url; else bool | `GhostPushError(GIT_FAILED)` | mutates git config |
| `commit` | `@classmethod (cls, repo_path: str, platform: str, title: str) -> str` | `git add .`; if `status --porcelain` empty → return HEAD rev or `"NO_CHANGES"`; else `git commit -m "feat(<platform>): add <title> solution"`; return HEAD rev or `"COMMITTED"` | str | `GhostPushError(GIT_FAILED)` on add or commit failure | **stages the entire repo** (`.`), creates commit |
| `push` | `@classmethod (cls, repo_path: str, remote_url: Optional[str] = None, remote: str = "origin", branch: str = "main") -> bool` | set remote if url, then `git push origin main` | bool | `GhostPushError(GIT_FAILED)` if push fails **and a remote exists**; `False` (non-error) if no remote | pushes to remote |
| `rollback` | `@classmethod (cls, repo_path: str) -> bool` | `git reset --hard` + `git clean -fd` | bool | none | **destroys uncommitted work**; never called by the graph |

**Git behavior facts / assumptions:**
- **Requires the `git` binary on PATH.**
- **Requires git identity (`user.name`/`user.email`) already configured globally** — `git commit` fails otherwise; the tool does not set identity.
- **Push branch hard-coded default `"main"`; no `--set-upstream`** — pushing a brand-new local `main` to an empty remote fails.
- **No authentication logic of any kind.** No token handling, no SSH setup. Relies on ambient git credential helpers or a token embedded in `remote_repo_url`.
- **No branch creation/checkout.** Only the `branch` parameter of `push`.
- **`rollback` is dead code** from the agent's perspective (never invoked).
- **`git add .` may stage unrelated user files** in the repo.
- No public "status" API other than the internal `--porcelain` check inside `commit`.

### 5.3 `mcp/notification_tool.py` — `NotificationTool`

```python
logger = logging.getLogger("GhostPush.NotificationTool")  # setLevel(INFO), NO handler attached
@staticmethod notify_status(job_id: str, status: str, message: str) -> dict
@staticmethod success(job_id: str, message: str) -> dict      # wraps notify_status("SUCCESS")
@staticmethod warning(job_id: str, message: str) -> dict      # wraps notify_status("WARNING")
@staticmethod error(job_id: str, message: str) -> dict        # wraps notify_status("ERROR")
```

- Returns dict `{job_id, status, message}` and logs `logger.info(...)`.
- **No handler is attached** (`notification_tool.py:4-5`). Under Python's default logging config, INFO records are dropped (only the `lastResort` WARNING+ handler surfaces anything). Status events effectively vanish unless Tav configures logging or provides an adapter.
- **No webhook / WebSocket / callback / persistence.** Event types emitted by the graph: `VALIDATING`, `GENERATING_README`, `WRITING_FILES`, `COMMITTING`, `PUSHING` (via `notify_status`) and `SUCCESS`/`WARNING`/`ERROR`.

---

## 6. AI Provider Layer (`agent/providers.py`) — Paras-owned

### 6.1 `get_llm_provider`
`get_llm_provider(provider_name: Optional[str] = None, model_name: Optional[str] = None, api_key: Optional[str] = None, temperature: float = 0.2) -> Any` (`providers.py:33`)

Returns a LangChain chat model (`.invoke(...)` compatible) **or** `MockLLM`.

**Supported providers (lowercased):** `gemini`, `openai`, `anthropic`, `groq`. Anything else → `MockLLM`.

| Provider | Branch | Library/Class | Default model | Failure mode |
|---|---|---|---|---|
| `gemini` | `providers.py:57` | `langchain_google_genai.ChatGoogleGenerativeAI` | `gemini-1.5-flash` | only `ImportError` → MockLLM; **real API errors propagate** and fail the job |
| `openai` | `providers.py:71` | `langchain_openai.ChatOpenAI` | `gpt-4o-mini` | broad `Exception` → MockLLM |
| `anthropic` | `providers.py:85` | `langchain_community.chat_models.ChatAnthropic` | `claude-3-haiku-20240307` | broad `Exception` → MockLLM; **package undeclared → always MockLLM as shipped** |
| `groq` | `providers.py:98` | `langchain_openai.ChatOpenAI` with `openai_api_base="https://api.groq.com/openai/v1"` | `llama3-8b-8192` | broad `Exception` → MockLLM |

### 6.2 API-key handling
- `resolved_key = (api_key and api_key.strip()) or ""` (`providers.py:55`). **The factory reads NO environment variables** (`os` imported at `providers.py:1` but unused). Env-based defaults in `docs/RECREATION_GUIDE.md` are **stale vs. the code**.
- `is_dummy_key(key)` (`providers.py:49-53`): empty, contains `"dummy"`, contains `"your_"`, or equals `"change_me"` → treated as placeholder → `MockLLM`.

### 6.3 `MockLLM`
`MockLLM(provider: str = "mock")` with `invoke(prompt: Any) -> Any` returning an object with `.content` (a canned README markdown).

### 6.4 Missing capabilities (for Tav's awareness)
- **No streaming interface** used anywhere.
- **No health/liveness interface.**
- **No model discovery / listing.**
- **No `openrouter` provider**, despite `.env.example` listing `OPENROUTER_API_KEY`.
- Temperature is always `0.2` (graph never overrides).

---

## 7. Prompts (`agent/prompts.py`) — Paras-owned

`README_GENERATION_PROMPT = PromptTemplate(input_variables=["platform","title","difficulty","url","tags","language","code"], template=...)` — single README-generation prompt. The interface Tav relies on: `README_GENERATION_PROMPT.format(**kwargs)` produces a string; the graph already handles formatting at `agent/graph.py:78-86`. Tav must not alter it.

---

## 8. Configuration & Secrets — actual state

**`.env.example` documents** (never read by agent code):

| Name | Required | Default | Actually used by | Secret? |
|---|---|---|---|---|
| `GEMINI_API_KEY` | No | — | **nothing in runtime code** (providers.py ignores env) | Yes |
| `OPENAI_API_KEY` | No | — | nothing | Yes |
| `ANTHROPIC_API_KEY` | No | — | nothing | Yes |
| `GROQ_API_KEY` | No | — | `test_github_push.py:16` (fallback only) | Yes |
| `OPENROUTER_API_KEY` | No | — | nothing (no openrouter provider) | Yes |
| `DEFAULT_AI_PROVIDER` | No | — | nothing (provider defaults to `"gemini"` inside `get_llm_provider` when name empty) | No |
| `DEFAULT_AI_MODEL` | No | — | nothing | No |
| `AI_API_KEY` | No | — | `test_github_push.py:16` only | Yes |

**Runtime configuration channel is the payload itself:** `SubmissionPayload.ai_provider`, `.ai_model`, `.api_key`, `.repository_path`, `.remote_repo_url`. There are **no settings classes, no config files, no dotenv loading** in the runtime path.

**Tav implication:** configuration management is 100% greenfield. The payload fields are the agreed slots for Tray-app-supplied AI settings.

---

## 9. Repository / File Expectations (compare to contract)

**Actual structure produced** (`mcp/file_tool.py:49-66`):

```
<repository_path>/
└── <PlatformDir>/            ← PLATFORM_DIR_NAMES (leetcode→LeetCode), else platform.capitalize()
    └── <problem.title.strip()>/   ← raw title, spaces preserved, NOT sanitized
        ├── Solution.<ext>     ← DEFAULT_SOLUTION_FILENAMES else f"Solution{ext}"
        ├── README.md          ← AI-generated (fallback "# Solution")
        └── metadata.json      ← job_id, platform, title, difficulty, url, tags, language, created_at
```

**Contract example `LeetCode/Two Sum/Solution.java` + `README.md` + `metadata.json`:**
- **Matches** for python/java/cpp/js/ts (`.java → Solution.java`).
- Differences/assumptions Tav must honor:
  1. `.git` repo is NOT assumed pre-existing — `GitTool.init_or_open_repo` lazily `git init`s during commit/push.
  2. `repository_path` is caller-required and must be writable; empty → job fails at write stage (`FILE_WRITE_FAILED`).
  3. Problem title is used raw for the directory name → titles with `/`, `..`, or Windows-illegal chars (`: * ? " < > |`) misbehave or crash on Windows.
  4. Unknown language → `.txt`; unknown platform → `platform.capitalize()`; validation does not enforce the `Platform`/`Language` enums.
  5. `metadata.json` schema is exactly the dict at `agent/graph.py:122-131`.
  6. Repository init (git init) is already handled inside GitTool — Tav's "Repository Initialization" responsibility reduces to supplying/registering a writable `repository_path` and optionally setting the remote.

---

## 10. Tests (`tests/test_agent.py`) — Paras-owned

7 tests: `test_contracts_schema`, `test_file_tool`, `test_git_tool`, `test_git_tool_set_remote`, `test_full_agent_job_success`, `test_agent_job_validation_failure`, `test_llm_provider_dynamic_config`. All use `tempfile.TemporaryDirectory()`; no real network push is exercised. `test_llm_provider_dynamic_config` explicitly asserts env vars are ignored when no runtime `api_key` is supplied (confirms §8).

---

## 11. External Interfaces — complete inventory

Everything a component outside `agent/`/`mcp/` can call today:

| Interface | Input | Output | Errors | Auth | Side effects |
|---|---|---|---|---|---|
| `agent.runner.run_agent_job(payload)` | `SubmissionPayload` or matching dict | `AgentResponse` | returns FAILED response; unexpected lib errors propagate | none | writes files, git init/add/commit/push, logs |
| `FileTool.write_problem_files(...)` | 7 params | dict of 4 paths | `GhostPushError(FILE_WRITE_FAILED)` | none | creates/overwrites 3 files |
| `GitTool.commit / push / init_or_open_repo / set_remote / rollback` | path (+platform/title/url) | str / bool | `GhostPushError(GIT_FAILED)` | git ambient creds | mutates git repo |
| `NotificationTool.*` | job_id, status, message | dict | none | none | log line (dropped w/o handler) |
| `agent.providers.get_llm_provider(...)` | provider/model/key/temperature | ChatModel or MockLLM | ImportError→Mock (gemini) / broad Exception→Mock | none | external LLM calls on invoke |

**There is NO HTTP, NO WebSocket, NO CLI (besides `__main__` demos), NO queue, NO DB, NO extension/tray API.** The only integration seam is calling `run_agent_job` in-process.

---

## 12. Compatibility vs. the Ownership Contract

Contract: **Tav owns** Browser Extension, Background Service, Installer, SQLite, REST, WebSocket, Configuration, Job Queue, Repository Initialization. **Paras owns** LangGraph, MCP, Git, File Tool, Notification Tool, AI Providers, Prompt Engineering, Repository Writing Logic.

### A. Compatible areas
- `common/` is documented as co-owned; Tav may extend it.
- `SubmissionPayload` → `AgentResponse` is a clean, versioned, Pydantic-validated contract ready for REST/WS.
- `run_agent_job` is stateless + synchronous → trivially wrappable by a queue worker.
- File/Git writing and commit/push already exist; `GitTool.init_or_open_repo` covers repo init; Tav only supplies the path.
- `JobStatus.QUEUED`/`PROCESSING` are pre-reserved for Tav's lifecycle.

### B. Missing interfaces (Tav must add)
REST submit endpoint; WS event channel; job queue + worker; SQLite job store; config store/loader; extension↔backend messaging; tray↔backend IPC; installer; repo-location registry.

### C. Contract mismatches
1. **`status` is a free string** (`"SUCCESS"/"FAILED"`), not `JobStatus` — Tav's DB/WS must map between the graph's granular statuses and the final response status.
2. **No `Job` entity** — `process_job(job: Job) -> JobResult` ≠ `run_agent_job(payload: SubmissionPayload) -> AgentResponse`; the agent is not DB-coupled.
3. **Synchronous only** — no async entry point.
4. **Push failure is non-fatal** — job reports SUCCESS even if nothing was pushed.
5. **No streaming** — WS can only carry discrete status snapshots.

### D. Assumptions Tav must satisfy
- Writable absolute `repository_path` in every payload.
- `git` on PATH; `user.name`/`user.email` configured (or Tav configures before commit).
- `api_key` travels inside the payload → TLS + protected storage are Tav's responsibility.
- Agent blocks the calling thread.
- Remote push requires git auth (credential helper or token URL) — Tav's responsibility; Paras's code has none.

### E. Things Tav must NOT implement
LangGraph, MCP tool framework, git logic, FileTool, NotificationTool internals, AI provider layer, prompt engineering, LLM communication, repo file-writing logic.

### F. What Paras's code assumes Tav will provide (from code + schema docstrings)
- A "Tray App" supplying `ai_provider` / `ai_model` / `api_key` at runtime (`common/schemas.py:26-28` field descriptions).
- A caller supplying `job_id`, `repository_path`, `remote_repo_url`.
- A job/queue layer persisting state (`JobStatus.QUEUED/PROCESSING` reserved but unused).
- Real-time consumption of the events `NotificationTool` currently only logs.

### G. Things requiring an adapter
- `NotificationTool` → real-time event stream (Paras-owned; **no hook point exists today** — needs a shared callback or a logging observation adapter).
- Granular graph statuses → DB/WS schema mapping.
- Sync `run_agent_job` → async worker.
- `AgentResponse` FAILED / `JobStatus.FAILED` / `ErrorCode` → unified error model.

### H. Things requiring discussion
1. Default/registered `repository_path` location (DB registry vs Tray config).
2. Git identity & auth strategy (user.name/email, token storage, branch, `--set-upstream`).
3. Should push failure remain non-fatal?
4. Canonical status/event contract + WS message mapping.
5. Adding a real notification hook to `NotificationTool` (or an adapter).
6. `langchain-community` (anthropic) — add to requirements or drop the provider.
7. Env-var config vs payload config (`.env.example` is currently dead config).
8. `repository_path`/title path-safety (FileTool has no sanitization).

---

## 13. What Tav Must Implement to Make This Runnable

**P0 — required for basic execution**
1. Resolve runtime env: install/verify deps (add `langchain-community` or accept anthropic=Mock; verify LangGraph/LangChain compatibility with the chosen Python, prefer 3.10–3.12 over 3.14).
2. **Configuration management** — load settings; supply `ai_provider/ai_model/api_key` and the active `repository_path`/`remote_repo_url`.
3. **SQLite database** — jobs table keyed by `job_id` (payload JSON, status, `AgentResponse` JSON, timestamps), settings table.
4. **Repository init service** — resolve/persist `repository_path`, ensure writable (git init is handled by GitTool), optionally set remote.
5. **Job queue + worker** — enqueue submissions; run `run_agent_job` off the event loop; persist result.
6. **Minimal FastAPI REST** — `POST /api/v1/jobs` (accept `SubmissionPayload`, return job id or `AgentResponse`), `GET /api/v1/jobs/{job_id}`; use `API_VERSION="1.0"`.
7. Baseline verification: `pytest tests/` green; `test_github_push.py` with MockLLM.

**P1 — MVP**
8. **WebSocket** status channel + adapter bridging the graph's `NotificationTool` events.
9. **Browser Extension** — capture submission (title/url/language/code) and POST.
10. **Tray App** — provider/model/API-key settings, repo remote config, job status view.
11. **Installer** — packaging for extension + tray + backend (+ bundled git), env bootstrap.

**P2 — later**
12. REST auth + TLS, encrypted credential storage, multi-repo, retry/cancel, telemetry, CI, cross-platform (Windows/macOS/Linux) verification.

---

## 14. Integration Sequence (recommended)

```
Baseline smoke (pytest + MockLLM push test)
→ Config loader + env
→ SQLite schema + job store
→ Repository init service
→ Worker/queue + Agent adapter (run_agent_job wrapper + status mapping)
→ FastAPI REST (submit + status)
→ WebSocket + NotificationTool bridge
→ Browser Extension
→ Tray App
→ Installer
→ Integration tests
```

Deviations from any sample sequence: `common/` already exists (skip); the agent adapter precedes the queue because the graph is synchronous and has no DB/queue hooks; the notification bridge precedes WebSocket because no event hook exists; a baseline smoke test should run first to establish ground truth.

---

## 15. Risks & Gaps

- **Empty `README.md`/`LICENSE`** — no project docs/licensing.
- **Dependencies never installed; Python 3.14.6 present** — compatibility unverified; nothing pinned.
- **`langchain-community` undeclared** → anthropic provider dead as shipped.
- **`.env.example` is dead config** — providers.py reads no env vars; dotenv never loaded; OPENROUTER unimplemented.
- **Git identity assumption** — commit fails in fresh environments without `user.name`/`user.email`.
- **Push branch `main`, no `--set-upstream`** — new-branch pushes to empty remotes fail.
- **Non-fatal push failure** — silent SUCCESS on failed push.
- **FileTool path safety** — raw title in paths (traversal / nested-dir injection / Windows-illegal chars / silent overwrite).
- **`git add .` stages everything** in the repo.
- **NotificationTool has no handler** — INFO status events dropped by default; no real-time delivery hook.
- **No checkpointer / timeouts** — no resume; `AI_TIMEOUT`/`NETWORK_ERROR` unused; a hung LLM blocks the worker.
- **API key in payload** — plaintext over Tav's transport; needs TLS + encrypted storage.
- **Status vocabulary mismatch** — free-string `status` vs `JobStatus` enum vs `ErrorCode`.
- **`run_agent_job` propagates unexpected exceptions** (no top-level guard).
- **Windows-specific assumptions** — paths via `os.path.join`, git on PATH, title chars; untested on macOS/Linux.
- **Untested code paths** — `rollback` (never called), real push success, live LLM calls, openai/anthropic live, `remote_repo_url` update branch.

---

## 16. Executive Summary

1. **What Paras has completed:** a self-contained, testable AI agent core — `run_agent_job(SubmissionPayload) -> AgentResponse` (sync), a 6-node LangGraph state machine with conditional failure routing, a 4-provider LLM factory with Mock fallback, File/Git/Notification tools, the full Pydantic wire contract, and a 7-test suite. It can generate a README, write `LeetCode/<Title>/` files, and git commit/push.
2. **What is missing:** everything outside the agent core — no backend, REST, WebSocket, SQLite, queue, config loading, extension, tray, installer, scripts, auth, CI, packaging; README/LICENSE empty; `backend/`, `extension/`, `tray/`, `scripts/` are empty placeholders.
3. **What Tav must build:** FastAPI REST + WebSocket, SQLite job store, job queue/worker, configuration management, repository-path/init orchestration, browser extension, tray app, installer, repo bootstrap, plus runtime env fixes (deps/Python, git identity, security).
4. **What interfaces already exist:** `run_agent_job`, `FileTool.*`, `GitTool.*`, `NotificationTool.*`, `get_llm_provider`, and the `common/schemas.py` contract.
5. **What interfaces are missing:** any HTTP/WS endpoint, queue/worker entry, DB interface, notification delivery beyond logging, extension/tray API, config loader.
6. **What must be agreed before integration:** `repository_path` ownership; git identity + auth + branch strategy; push-failure severity; canonical status/event mapping; how Tav gets real-time events from `NotificationTool`; env-var vs payload AI config; `langchain-community` dependency; FileTool path-sanitization ownership.
7. **Recommended first implementation task:** a thin **agent adapter + smoke test** — a minimal `POST /api/v1/jobs` that validates a `SubmissionPayload`, persists it to SQLite, runs `run_agent_job` (MockLLM, local temp repo), and returns/stores the `AgentResponse` — proving the entire Paras→Tav seam (schema, sync call, DB, REST) before any UI work.
