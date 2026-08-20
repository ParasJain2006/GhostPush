# Graph Report - .  (2026-08-20)

## Corpus Check
- 42 files · ~21,859 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 569 nodes · 1082 edges · 36 communities (27 shown, 9 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 59 edges (avg confidence: 0.69)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Agent Graph Execution|Agent Graph Execution]]
- [[_COMMUNITY_FastAPI Backend App & Websocket|FastAPI Backend App & Websocket]]
- [[_COMMUNITY_SQLite Database Layer|SQLite Database Layer]]
- [[_COMMUNITY_Websocket Notification Handler|Websocket Notification Handler]]
- [[_COMMUNITY_GhostPush Core Rules|GhostPush Core Rules]]
- [[_COMMUNITY_Scripts & Environment Setup|Scripts & Environment Setup]]
- [[_COMMUNITY_Agent Providers & Runner|Agent Providers & Runner]]
- [[_COMMUNITY_Tray App Behavior Tests|Tray App Behavior Tests]]
- [[_COMMUNITY_Config Manager Tests|Config Manager Tests]]
- [[_COMMUNITY_Tray Config UI & Helper|Tray Config UI & Helper]]
- [[_COMMUNITY_Backend Launcher Tests|Backend Launcher Tests]]
- [[_COMMUNITY_Config Path Resolution|Config Path Resolution]]
- [[_COMMUNITY_Extension Manifest|Extension Manifest]]
- [[_COMMUNITY_Tray App Core|Tray App Core]]
- [[_COMMUNITY_Config API Routes|Config API Routes]]
- [[_COMMUNITY_Jobs API Routes|Jobs API Routes]]
- [[_COMMUNITY_Tray App Actions & Menu|Tray App Actions & Menu]]
- [[_COMMUNITY_Config Manager Persistence|Config Manager Persistence]]
- [[_COMMUNITY_Extension Popup Logic|Extension Popup Logic]]
- [[_COMMUNITY_AppSettings Validation|AppSettings Validation]]
- [[_COMMUNITY_BackendLauncher Lifecycle|BackendLauncher Lifecycle]]
- [[_COMMUNITY_Tray Icon & Menu Build|Tray Icon & Menu Build]]
- [[_COMMUNITY_PyInstaller Build Script|PyInstaller Build Script]]
- [[_COMMUNITY_Graphify Config|Graphify Config]]
- [[_COMMUNITY_Scripts Init|Scripts Init]]
- [[_COMMUNITY_Tests Init|Tests Init]]
- [[_COMMUNITY_Arch Workflow Doc|Arch Workflow Doc]]
- [[_COMMUNITY_System Architecture Doc|System Architecture Doc]]
- [[_COMMUNITY_Paras Dep Gaps Doc|Paras Dep Gaps Doc]]
- [[_COMMUNITY_Paras Tav Roadmap Doc|Paras Tav Roadmap Doc]]
- [[_COMMUNITY_Recreation Guide Doc|Recreation Guide Doc]]

## God Nodes (most connected - your core abstractions)
1. `ConfigManager` - 33 edges
2. `JobQueue` - 33 edges
3. `TrayApp` - 30 edges
4. `JobWorker` - 22 edges
5. `ConnectionManager` - 21 edges
6. `JobRepository` - 21 edges
7. `BackendLauncher` - 19 edges
8. `AgentState` - 17 edges
9. `SubmissionPayload` - 17 edges
10. `TrayConfigHelper` - 16 edges

## Surprising Connections (you probably didn't know these)
- `Component Ownership & Ownership Boundaries` --references--> `run_agent_job()`  [EXTRACTED]
  docs/PARAS_ARCHITECTURE_REPORT.md → agent/runner.py
- `SubmissionPayload Wire Contract` --conceptually_related_to--> `SubmissionPayload`  [EXTRACTED]
  docs/ARCHITECTURE_AND_WORKFLOW.md → common/schemas.py
- `AgentResponse Wire Contract` --conceptually_related_to--> `AgentResponse`  [EXTRACTED]
  docs/ARCHITECTURE_AND_WORKFLOW.md → common/schemas.py
- `AgentState` --uses--> `AgentResponse`  [INFERRED]
  agent/graph.py → common/schemas.py
- `AgentState` --uses--> `SubmissionPayload`  [INFERRED]
  agent/graph.py → common/schemas.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Backend Module Development Workflow Steps** — agents_skills_backend_module_skill_inspect_files, agents_skills_backend_module_skill_check_common_contracts, agents_skills_backend_module_skill_implement_smallest, agents_skills_backend_module_skill_add_tests, agents_skills_backend_module_skill_run_focused_tests, agents_skills_backend_module_skill_run_full_test_suite, agents_skills_backend_module_skill_report_changed_files [EXTRACTED 1.00]
- **GhostPush Core Governance Constraints** — agents_rules_ghostpush_core_shared_layer, agents_rules_ghostpush_core_no_contract_duplication, agents_rules_ghostpush_core_agent_adapter_boundary, agents_rules_ghostpush_core_local_network_binding, agents_rules_ghostpush_core_secret_safety, agents_rules_ghostpush_core_testing_requirement, agents_rules_ghostpush_core_scope_control, agents_rules_ghostpush_core_verification_step [EXTRACTED 1.00]
- **Popup Submission and Job Monitoring Flow** — extension_popup_submission_form, extension_popup_autofill_button, extension_popup_submit_button, extension_popup_progress_container, extension_popup_backend_status [INFERRED 0.75]

## Communities (36 total, 9 thin omitted)

### Community 0 - "Agent Graph Execution"
Cohesion: 0.06
Nodes (47): AgentState, commit_node(), finish_node(), generate_readme_node(), push_node(), Write Solution, README.md, and metadata.json to repository directory., Create Git commit for added solution files., Push commits to remote Git repository. (+39 more)

### Community 1 - "FastAPI Backend App & Websocket"
Cohesion: 0.05
Nodes (44): lifespan(), WebSocket, WebSocket endpoint that streams NotificationTool events to connected clients., Run the FastAPI application with uvicorn on localhost., run_api(), websocket_notifications(), WebSocket connection manager and synchronous-to-async notification bridge.  Arch, Logging handler that bridges NotificationTool log records to WebSocket clients. (+36 more)

### Community 2 - "SQLite Database Layer"
Cohesion: 0.07
Nodes (38): get_db_connection(), get_db_dir(), get_default_db_path(), init_db(), Connection, Path, SQLite database connection management and pragmas for GhostPush backend., Return the cross-platform database directory. (+30 more)

### Community 3 - "Websocket Notification Handler"
Cohesion: 0.06
Nodes (30): AbstractEventLoop, ConnectionManager, LogRecord, WebSocket, Tracks active WebSocket connections and broadcasts JSON events., Broadcast a JSON-safe dict to all connected clients.          Disconnected clien, _capture_log, _ListHandler (+22 more)

### Community 4 - "GhostPush Core Rules"
Cohesion: 0.08
Nodes (43): Agent Integration Boundary (backend/agent/adapter.py), GhostPush Core Rules, Local Network Binding (127.0.0.1), No Contract Duplication, Paras Ownership (agent, mcp, LangGraph state machine, AI provider, MCP tools), Target Python 3.12 Runtime, Scope Control, Secret Safety (+35 more)

### Community 5 - "Scripts & Environment Setup"
Cohesion: 0.10
Nodes (35): main(), Official GhostPush Application Entrypoint.  Validates runtime environment, sets, Main launcher entrypoint., check_dependencies(), check_python_version(), ensure_env_file(), get_project_root(), get_target_env_dir() (+27 more)

### Community 6 - "Agent Providers & Runner"
Cohesion: 0.13
Nodes (28): create_agent_graph(), Build and compile the LangGraph StateGraph., LangGraph Agent package containing AI providers, prompts, agent state graph, and, get_llm_provider(), MockLLM, Any, Factory function that returns a LangChain Chat Model based on Tray App runtime c, Fallback LLM used when no valid external API key is supplied in runtime configur (+20 more)

### Community 7 - "Tray App Behavior Tests"
Cohesion: 0.08
Nodes (24): TrayApp constructs with defaults without requiring a desktop., TrayApp accepts injected launcher and config_helper., action_start_backend() calls launcher.start()., action_stop_backend() calls launcher.stop()., action_exit() stops the backend and then stops the tray icon., action_exit() does not crash when _icon is None (before run())., action_open_config() spawns a daemon thread and does not block., run() raises RuntimeError when pystray/Pillow are not installed. (+16 more)

### Community 8 - "Config Manager Tests"
Cohesion: 0.17
Nodes (10): ConfigManager, Resolve API key for a provider from process environment without persisting or lo, Manages application configuration persistence and secret resolution., isolated_client(), test_api_key_loaded_from_environment(), test_api_key_not_present_in_config_json(), test_config_manager_save_and_load_round_trip(), test_config_manager_update_config() (+2 more)

### Community 9 - "Tray Config UI & Helper"
Cohesion: 0.15
Nodes (10): test_tray_config_helper_load_settings(), test_tray_config_helper_rejects_invalid_configuration(), test_tray_config_helper_rejects_secret_field_injection(), test_tray_config_helper_update_valid_settings(), Any, AppSettings, Headless controller for managing configuration loads and updates for the tray ap, Return the current validated AppSettings model. (+2 more)

### Community 10 - "Backend Launcher Tests"
Cohesion: 0.23
Nodes (12): action_start_backend and action_stop_backend refresh the menu via update_menu()., test_launcher_accepts_localhost_variants(), test_launcher_dev_mode_uses_string_target(), test_launcher_frozen_mode_uses_app_instance(), test_launcher_initial_state(), test_launcher_rejects_non_localhost_host(), test_launcher_start_failure_handling(), test_launcher_start_lifecycle_and_duplicate_protection() (+4 more)

### Community 11 - "Config Path Resolution"
Cohesion: 0.24
Nodes (9): Path, Configuration manager for loading, persisting, and updating AppSettings., get_config_dir(), get_config_file_path(), Path, Configuration constants and path resolution for GhostPush backend., Return the cross-platform application configuration directory.      Windows: %AP, Return the full path to config.json. (+1 more)

### Community 12 - "Extension Manifest"
Cohesion: 0.15
Nodes (12): action, default_popup, default_title, background, service_worker, content_scripts, description, host_permissions (+4 more)

### Community 14 - "Tray App Core"
Cohesion: 0.23
Nodes (7): test_tray_config_dialog_raises_when_tkinter_unavailable(), Backend server launcher for GhostPush tray application.  Manages starting, stopp, Configuration UI helper and tkinter dialog for GhostPush system tray application, Tkinter-based GUI configuration dialog for GhostPush tray app., Open the modal configuration dialog window., TrayConfigDialog, GhostPush System Tray Application.  Creates a system tray icon with a menu for c

### Community 15 - "Config API Routes"
Cohesion: 0.27
Nodes (9): get_config(), _get_config_manager(), Any, AppSettings, Request, Retrieve the current non-secret application configuration., Update non-secret application configuration fields., update_config() (+1 more)

### Community 16 - "Jobs API Routes"
Cohesion: 0.33
Nodes (10): create_job(), get_job(), _get_queue(), list_jobs(), Any, Request, SubmissionPayload, Enqueue a SubmissionPayload for processing. (+2 more)

### Community 17 - "Tray App Actions & Menu"
Cohesion: 0.20
Nodes (5): Stop the backend cleanly, then stop the tray icon., Stop the tray icon programmatically (useful for tests and clean shutdown)., Refresh tray menu so status and item text reflect current state immediately., Start the FastAPI backend via BackendLauncher., Stop the FastAPI backend via BackendLauncher.

### Community 18 - "Config Manager Persistence"
Cohesion: 0.31
Nodes (5): Any, AppSettings, Save non-secret AppSettings to config.json., Apply non-secret updates, validate, and persist new settings., Load and validate configuration from config.json or return defaults.

### Community 19 - "Extension Popup Logic"
Cohesion: 0.28
Nodes (3): generateJobId(), handleFormSubmit(), showProgress()

### Community 21 - "BackendLauncher Lifecycle"
Cohesion: 0.33
Nodes (3): Return True if the backend server thread is active., Start the FastAPI backend server in a background thread., Signal the background backend server to shut down cleanly.

### Community 22 - "Tray Icon & Menu Build"
Cohesion: 0.33
Nodes (4): _create_tray_icon_image(), Construct and return the pystray tray menu., Create and run the system tray icon (blocking call on the calling thread)., Generate a simple GhostPush tray icon image using Pillow.      Returns a square

### Community 24 - "PyInstaller Build Script"
Cohesion: 0.50
Nodes (3): build_executable(), Automated PyInstaller Executable Builder for GhostPush.  Runs PyInstaller using, Execute PyInstaller build and verify artifact output.

## Knowledge Gaps
- **23 isolated node(s):** `SubmissionPayload Wire Contract`, `AgentResponse Wire Contract`, `Job Lifecycle & State Transitions`, `Tav Infrastructure Integration Roadmap`, `Step-by-Step Recreation Guide` (+18 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ConfigManager` connect `Config Manager Tests` to `FastAPI Backend App & Websocket`, `Tray Config UI & Helper`, `Backend Launcher Tests`, `Config Path Resolution`, `API Route Tests`, `Tray App Core`, `Config API Routes`, `Config Manager Persistence`?**
  _High betweenness centrality (0.172) - this node is a cross-community bridge._
- **Why does `JobQueue` connect `FastAPI Backend App & Websocket` to `Jobs API Routes`, `Config Manager Tests`, `SQLite Database Layer`, `API Route Tests`?**
  _High betweenness centrality (0.104) - this node is a cross-community bridge._
- **Why does `TrayApp` connect `Tray App Behavior Tests` to `Scripts & Environment Setup`, `Tray Config UI & Helper`, `Backend Launcher Tests`, `Tray App Core`, `Tray App Actions & Menu`, `Tray Icon & Menu Build`?**
  _High betweenness centrality (0.089) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `ConfigManager` (e.g. with `TrayConfigDialog` and `TrayConfigHelper`) actually correct?**
  _`ConfigManager` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `JobQueue` (e.g. with `JobRepository` and `JobWorker`) actually correct?**
  _`JobQueue` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `TrayApp` (e.g. with `BackendLauncher` and `TrayConfigDialog`) actually correct?**
  _`TrayApp` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `ConnectionManager` (e.g. with `_capture_log` and `_ListHandler`) actually correct?**
  _`ConnectionManager` has 2 INFERRED edges - model-reasoned connections that need verification._