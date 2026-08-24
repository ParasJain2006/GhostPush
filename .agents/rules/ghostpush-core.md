---
trigger: always_on
description: Essential permanent GhostPush development rules, ownership boundaries, and core constraints.
---

# GhostPush Core Rules

1. **Tav Ownership**: Tav owns `backend/`, `extension/`, `tray/`, `installer/scripts`, SQLite database, REST API, WebSocket hub, job queue, and configuration management.
2. **Paras Ownership**: Paras owns `agent/`, `mcp/`, LangGraph state machine, AI provider integration, prompt engineering, and Git/File/Notification MCP tools.
3. **Shared Layer**: `common/` is shared across modules and serves as the single source of truth for schemas, enums, constants, and errors.
4. **No Contract Duplication**: Never duplicate schemas, enums, constants, or error codes outside of `common/`.
5. **Paras Code Isolation**: Do not modify Paras-owned code (`agent/`, `mcp/`) unless explicitly requested for an integration change.
6. **API Version**: The current supported API version is `1.0`.
7. **Agent Integration Boundary**: The backend must communicate with Paras's agent strictly through the existing adapter: `backend/agent/adapter.py`.
8. **Network Binding**: The backend API server must bind to `127.0.0.1`.
9. **Secret Safety**: Secrets (e.g., API keys, passwords) must never be stored in `config.json`, SQLite, log output, or committed source code.
10. **Target Python Version**: The target Python runtime environment is Python 3.12.
11. **Testing Requirement**: Every feature or change must include corresponding tests.
12. **Scope Control**: Prefer small, focused modifications and do not touch unrelated files.
13. **Verification Step**: Run focused tests after code changes and execute the full test suite before completing any task.
