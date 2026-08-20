---
name: backend-module
description: Concise workflow for developing GhostPush backend modules cleanly.
---

# Backend Module Development Workflow

Follow this concise workflow for building or modifying GhostPush backend modules:

1. **Inspect Relevant Files**: Locate and read the target files in `backend/` and related tests in `tests/`.
2. **Check Common Contracts**: Verify existing schemas, enums, constants, and error codes in `common/` without duplicating or mutating them.
3. **Implement Smallest Solution**: Write the minimal code required in `backend/`, respecting component ownership and relying on `backend/agent/adapter.py` for agent interactions.
4. **Add Tests**: Create or update unit tests in `tests/` covering the new backend functionality.
5. **Run Focused Tests**: Execute specific test files or functions related to the modified module to verify correctness.
6. **Run Full Test Suite**: Execute the full test suite (`pytest tests/`) to ensure no regressions were introduced.
7. **Report Changed Files**: Summarize all created or modified files cleanly.
