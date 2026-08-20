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

## 6. Key Design Patterns Applied

1. **Single Source of Truth**: All shared models live strictly in `common/`.
2. **Factory Pattern**: `agent/providers.py` abstracts LLM instantiation and API key resolution.
3. **Mock-First Architecture**: `MockLLM` allows instant testing and keyless development without API key errors.
4. **Tool Pattern (MCP)**: Operations (File, Git, Logging) are isolated into reusable static methods in `mcp/`.
5. **Deterministic Graph**: LangGraph explicit state graph ensures reproducible workflow execution.
