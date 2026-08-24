# Architecture, Workflow & Technical Explanation

This document provides a comprehensive technical breakdown of **GhostPush (AI-powered Code Repository Sync Manager)** (Paras's Part: AI Agent & MCP Core). It covers the system architecture, component responsibilities, data flow, frozen contracts, and design patterns.

---

## 1. System Architecture Overview

The system follows a **layered, decoupled architecture** where business logic, AI decision-making, and file/git operations are isolated from external client interfaces.

```
       ┌─────────────────────────────────────────┐
       │   Browser Extension / Tray / Backend    │
       └────────────────────┬────────────────────┘
                            │ REST / Internal API (Payload Contract)
                            ▼
       ┌─────────────────────────────────────────┐
       │         Agent Runner Layer              │  (agent/runner.py)
       └────────────────────┬────────────────────┘
                            │ Initial State
                            ▼
       ┌─────────────────────────────────────────┐
       │         LangGraph StateGraph            │  (agent/graph.py)
       │ ┌──────────────┐      ┌───────────────┐ │
       │ │  Validate    ├─────►│Gen README(AI) │ │  (agent/providers.py & agent/prompts.py)
       │ └──────────────┘      └───────┬───────┘ │
       │                               │         │
       │ ┌──────────────┐      ┌───────▼───────┐ │
       │ │  Push Git    │◄─────┤ Write Files   │ │  (mcp/file_tool.py & mcp/git_tool.py)
       │ └──────┬───────┘      └───────────────┘ │
       │        │                                │
       │ ┌──────▼───────┐                        │
       │ │ Finish / Resp│                        │
       │ └──────────────┘                        │
       └────────────────────┬────────────────────┘
                            │ AgentResponse Contract
                            ▼
       ┌─────────────────────────────────────────┐
       │ Target Git Repository on Filesystem     │
       └─────────────────────────────────────────┘
```

---

## 2. Component Ownership & Boundaries

| Module Layer | Location | Key Responsibilities | Primary Owner |
| :--- | :--- | :--- | :--- |
| **Common** | `common/` | Enums, Pydantic JSON contracts, custom errors (`GhostPushError`), and constants. Shared across all services. | Paras & Tav |
| **MCP Execution** | `mcp/` | Direct file manipulation, Git repository management, and status notifications. | Paras |
| **AI Providers** | `agent/providers.py` | Multi-LLM provider abstraction (Gemini, OpenAI, Anthropic, etc.) reading from Tray App runtime payload with Mock fallback. | Paras |
| **Prompts** | `agent/prompts.py` | Prompt templates for markdown README generation. | Paras |
| **LangGraph Agent** | `agent/graph.py` | Graph state machine orchestrating nodes and conditional routing logic. | Paras |
| **Agent Runner** | `agent/runner.py` | Synchronous/asynchronous entry point executing graph jobs. | Paras |

---

## 3. Data Flow & Sequence Diagram

1. **Submission Ingestion**: Client submits structured JSON matching `SubmissionPayload`.
2. **Validation Node**: Validates platform, problem/task metadata, and solution code presence.
3. **AI Generation Node**: Invokes configured LLM via `providers.py` using `README_GENERATION_PROMPT` to produce a rich GitHub `README.md`.
4. **File Writing Node**: `FileTool` constructs directory structure `<RepositoryRoot>/<Platform>/<Title>/` and writes:
   - `Solution.<ext>`
   - `README.md`
   - `metadata.json`
5. **Git Commit Node**: `GitTool` stages all files and creates commit matching convention `feat(<platform>): add <title> solution`.
6. **Git Push Node**: `GitTool` configures or updates the `origin` remote if `remote_repo_url` is provided, then pushes commits to the remote repository (non-fatal if remote push fails or is unconfigured).
7. **Finish Node**: Constructs deterministic `AgentResponse` contract (`status="SUCCESS"` or `"FAILED"`, `job_id`, `commit_hash`, `repository_path`).

---

## 4. Frozen Specifications & Contracts

### 4.1 JSON Submission Payload Contract (`SubmissionPayload`)
```json
{
  "api_version": "1.0",
  "job_id": "JOB-12345",
  "platform": "leetcode",
  "problem": {
    "title": "Two Sum",
    "difficulty": "Easy",
    "url": "https://leetcode.com/problems/two-sum/",
    "tags": ["Array", "Hash Table"]
  },
  "solution": {
    "language": "python",
    "code": "class Solution: ..."
  },
  "repository_path": "C:/Users/.../my-code-repo",
  "remote_repo_url": "https://github.com/user/my-solutions.git",
  "ai_provider": "gemini",
  "ai_model": "gemini-1.5-flash",
  "api_key": "user_api_key_from_tray_app"
}
```

### 4.2 Agent Response Contract (`AgentResponse`)
```json
{
  "status": "SUCCESS",
  "job_id": "JOB-12345",
  "commit_hash": "a1b2c3d4e5...",
  "repository_path": "C:/Users/.../my-code-repo",
  "message": "Successfully written files and created Git commit."
}
```

### 4.3 Folder Hierarchy Contract
```text
<RepositoryRoot>/
└── LeetCode/
    └── Two Sum/
        ├── Solution.py
        ├── README.md
        └── metadata.json
```

### 4.4 Commit Message Convention
```text
feat(<platform>): add <title> solution
Example: feat(leetcode): add Two Sum solution
```

---

## 5. Job Lifecycle & State Transitions

```
[CREATED] ──► [VALIDATING] ──► [GENERATING_README] ──► [WRITING_FILES] ──► [COMMITTING] ──► [PUSHING] ──► [COMPLETED]
     │              │                     │                  │                 │              │
     └──────────────┴─────────────────────┴──────────────────┴─────────────────┴──────────────┴──► [FAILED]
```

Every node updates `AgentState["status"]` and logs progress via `NotificationTool`. If an exception occurs, conditional routing directs execution immediately to `finish_node` with status `FAILED`.

---

## 6. Phase 12A — Automatic LeetCode Accepted-Submission Sync (Extension)

**Scope:** LeetCode only. Automatic sync is an additional path; manual Extract / Push remains unchanged.

### 6.1 Desired Flow
```
LeetCode /problems/<slug>/ opens
  → content.js SubmissionMonitor auto-starts (singleton guard window.__ghostPushSubmissionMonitorStarted)
  → MAIN-world bridge patches fetch/XHR, distinguishes Submit vs Run
  → submit detected → pending state set (submissionId or flag + timestamp + problem URL)
  → wait for final check result
  → if Accepted (state SUCCESS + status_msg Accepted) + pending submit exists → extract + deduplicate + POST job
  → otherwise ignore (fail closed)
  → Run Code / "All test cases passed" NEVER triggers a job
```

### 6.2 Complete-Source Extraction (correctness over appearance)

Priority order (fail closed if incomplete):
1. LeetCode Monaco editor model API via MAIN world (`monaco.editor.getModels()[].getValue()`) — complete buffer.
2. Monaco model language ID (`getModeId` / `getLanguageId`) + LeetCode language selector button (`button[id*='headlessui-popover-button']`, `[data-cy='lang-select']`) for language.
3. Language heuristic `detectLanguageFromCode()` only as final fallback.
4. DOM `.view-lines .view-line` is **last resort fallback only**; if MAIN bridge returns null/empty the monitor refuses to sync and logs `Missing complete source — failing closed` rather than committing truncated code.

Communication between isolated content script and MAIN world uses `window.postMessage` with explicit source tags (`ghostpush-main` / `ghostpush-content`) and request IDs; no extension internals are exposed to the page.

### 6.3 Submission Detection (Submit vs Run)

- MAIN bridge inspects request URL/body: `/submit`, GraphQL `questionSubmit`/`submitCode` vs `interpret`/`runCode`/`testCase`.
- On submit response extracts `submission_id` / `submissionId` and posts `GP_SUBMIT_DETECTED`.
- On check response (`/check`, `/submissions/detail/<id>/check`, GraphQL `submissionDetails`) extracts `{state, status_msg, submissionId}` and posts `GP_SUBMISSION_RESULT`.
- Content monitor requires a **pending submit** (id-matched or recent flag within 5 min) before acting on any `Accepted`; this prevents Run Code pollution.
- Classification via `classifySubmissionStatus()` — only `status_msg === "Accepted" && state === "SUCCESS"` triggers sync; all of `Wrong Answer`, `Runtime Error`, `Compile Error`, `Time Limit Exceeded`, `Memory Limit Exceeded`, `Output Limit Exceeded`, `Pending`, `Running`, `Processing`, `Test Case Passed`/`All test cases passed`, `Unknown` are explicitly ignored.

### 6.4 SPA, Singleton & Deduplication

- **SPA:** patches `history.pushState`/`replaceState`, listens for `popstate` + `ghostpush_locationchange`, observes `<title>` mutations, and throttled 2 s URL poll; on canonical problem URL change (`/problems/<slug>`) clears pending state so `Two Sum → Add Two Numbers` cannot bleed.
- **Singleton:** `window.__ghostPushSubmissionMonitorStarted` guard + `window.__ghostPushContentScriptInjected` for extraction path.
- **Deduplication:** deterministic key `leetcode:<normalizedUrl>:<submissionId>` if ID available; else `leetcode:<normalizedUrl>:<language>:<sha256(completeCode)>` via `crypto.subtle.digest`. Stored in `chrome.storage.local` (`ghostpush_seen_submissions`) with 30-day prune, survives popup closure. Backend `409 Conflict` on duplicate `job_id` also marks seen. Never uses random `job_id` as dedup key.

### 6.5 Automatic Job Creation

On confident `Accepted` the monitor:
1. requests complete editor data via `GP_GET_EDITOR_DATA` bridge (2.5 s timeout),
2. validates title/url/language/code, normalizes URL (`/problems/<slug>` canonical), validates LeetCode problem page,
3. checks dedup storage,
4. builds frozen `SubmissionPayload` (`api_version 1.0`, random `JOB-EXT-<ts>-<rand>`, `platform leetcode`, `problem`, `solution`, `repository_path=""` filled by background) and sends `chrome.runtime.sendMessage({action:"ghostpush_auto_submit"})` to `background.js`,
5. `background.js` validates sender is LeetCode, fetches `repository_path` from `GET /api/v1/config` (cached in `chrome.storage.local`), then `POST /api/v1/jobs` using the existing job queue contract.

No new API endpoint, no SQLite schema change, no new `JobStatus`, no `agent/`/`mcp/` changes.

### 6.6 Logging & Fail-Closed Behavior

Logs use `[GhostPush][SubmissionMonitor]` with `timestamp`, `submissionId` when available, `status`, `durationMs`, `message`:
`Monitor started`, `Submit detected`, `Waiting for result`, `Rejected - ignored`, `Accepted`, `Extracted complete solution`, `Duplicate submission - ignored`, `Automatic job created`, `Abort` reasons. Excessive polling is avoided. If any of complete source / reliable language / problem identity / final Accepted status is unavailable, no job is created and no Git commit is made.

### 6.7 Known Limitations (Phase 12A)

- LeetCode-only; GFG/Codeforces/HackerRank remain manual.
- Requires LeetCode Monaco endpoint availability and fetch/XHR submission pattern stability; if LeetCode changes GraphQL operation names, the bridge needs updating (fail closed in interim).
- Strict CSP on future LeetCode redesign could block DOM `<script>` injection — fallback fails closed rather than syncing truncated code.
- `crypto.subtle` SHA-256 fallback uses non-cryptographic hash if unavailable; dedup still deterministic but weaker.

---

## 7. Key Design Patterns Applied

1. **Single Source of Truth**: All shared models live strictly in `common/`.
2. **Factory Pattern**: `agent/providers.py` abstracts LLM instantiation and API key resolution.
3. **Mock-First Architecture**: `MockLLM` allows instant testing and keyless development without API key errors.
4. **Tool Pattern (MCP)**: Operations (File, Git, Logging) are isolated into reusable static methods in `mcp/`.
5. **Deterministic Graph**: LangGraph explicit state graph ensures reproducible workflow execution.
