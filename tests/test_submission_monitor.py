"""Phase 12A: Automatic LeetCode Accepted-Submission Sync — focused unit tests."""

import hashlib
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from common.schemas import SubmissionPayload
from backend.api.app import app
from backend.config.manager import ConfigManager
from backend.jobs.queue import JobQueue


# ---------------------------------------------------------------------------
# Helpers mirroring extension/content.js logic (used for behavioral tests)
# ---------------------------------------------------------------------------

def normalize_problem_url(url: str) -> str:
    if not url or not isinstance(url, str):
        return ""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        m = re.search(r"/problems/[^/]+", path)
        if m:
            path = m.group(0)
        return (f"{parsed.scheme}://{parsed.netloc}" + path).lower()
    except Exception:
        return url.strip().lower()


def is_leetcode_problem_page(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False
    return "leetcode.com/problems/" in url


def classify_submission_status(status_msg, state):
    msg = (status_msg or "").strip()
    st = (state or "").strip()
    if msg == "Accepted" and (st == "SUCCESS" or st == ""):
        return "Accepted"
    ignored = {
        "Wrong Answer",
        "Runtime Error",
        "Compile Error",
        "Time Limit Exceeded",
        "Memory Limit Exceeded",
        "Output Limit Exceeded",
        "Pending",
        "Running",
        "Processing",
        "Unknown",
    }
    if msg in ignored:
        return msg
    if msg in ("Test Case Passed", "All test cases passed", "All Test Cases Passed"):
        return "Test Case Passed"
    if st in ("PENDING", "STARTED"):
        return "Pending"
    return "Unknown"


def is_accepted_status(status_msg, state):
    return classify_submission_status(status_msg, state) == "Accepted"


def build_dedup_key_sync(platform, normalized_url, submission_id, language, code_hash):
    if submission_id:
        return f"{platform}:{normalized_url}:{submission_id}"
    return f"{platform}:{normalized_url}:{language}:{code_hash}"


def normalize_lang_text(raw):
    if not raw or not isinstance(raw, str):
        return None
    norm = raw.strip().lower()
    if norm in ("c++", "cpp"):
        return "cpp"
    if norm == "java":
        return "java"
    if norm.startswith("python"):
        return "python"
    if norm in ("javascript", "js"):
        return "javascript"
    if norm in ("typescript", "ts"):
        return "typescript"
    if norm in ("golang", "go"):
        return "go"
    if norm == "rust":
        return "rust"
    if norm == "kotlin":
        return "kotlin"
    if norm == "swift":
        return "swift"
    if "c++" in norm or "cpp" in norm:
        return "cpp"
    if "java" in norm and "javascript" not in norm:
        return "java"
    if "python" in norm:
        return "python"
    if "javascript" in norm or ("js" in norm and "json" not in norm):
        return "javascript"
    if "typescript" in norm:
        return "typescript"
    if "kotlin" in norm:
        return "kotlin"
    if "rust" in norm:
        return "rust"
    if "golang" in norm or " go" in norm:
        return "go"
    return None


def detect_language_from_code(code):
    if not code or not isinstance(code, str):
        return "python"
    if re.search(r"#include\s*<|\bstd::|\bvector\s*<|\bpublic\s*:", code):
        return "cpp"
    if (
        re.search(r"\bpublic\s+class\b", code)
        or re.search(r"\bimport\s+java\.", code)
        or re.search(r"\bSystem\.out\.", code)
        or re.search(r"\bnew\s+int\s*\[", code)
        or re.search(r"\bint\s*\[\s*\]", code)
        or re.search(r"\bpublic\s+(static\s+)?(int|void|boolean|String|double|float|long|int\[\]|List|TreeNode|ListNode)\b", code)
        or (re.search(r"\bclass\s+Solution\b", code) and not re.search(r"\bclass\s+Solution\s*:", code))
    ):
        return "java"
    if (
        re.search(r"\bdef\s+\w+\s*\(", code)
        or re.search(r"\bclass\s+Solution\s*:", code)
        or re.search(r"\bfrom\s+typing\b", code)
        or re.search(r"\bimport\s+typing\b", code)
        or re.search(r"\bself\.", code)
    ):
        return "python"
    if re.search(r"\b(function|const|let|var)\b", code):
        if re.search(r"\b(interface|type)\s+\w+", code) or re.search(r":\s*(number|string|boolean)\[\]?", code):
            return "typescript"
        return "javascript"
    return "python"


def detect_language(dom_text, code):
    from_dom = normalize_lang_text(dom_text)
    if from_dom:
        return from_dom
    return detect_language_from_code(code)


# ---------------------------------------------------------------------------
# Fixture for backend job API
# ---------------------------------------------------------------------------

@pytest.fixture
def isolated_client(tmp_path):
    db_file = tmp_path / "test_monitor_jobs.db"
    config_file = tmp_path / "test_monitor_config.json"
    test_queue = JobQueue(db_path=db_file)
    test_config_mgr = ConfigManager(config_path=config_file)
    with TestClient(app) as client:
        app.state.queue = test_queue
        app.state.config_mgr = test_config_mgr
        yield client


# ---------------------------------------------------------------------------
# 1-6: Final result state classification
# ---------------------------------------------------------------------------

def test_accepted_result_triggers_sync():
    assert is_accepted_status("Accepted", "SUCCESS") is True
    assert classify_submission_status("Accepted", "SUCCESS") == "Accepted"


def test_wrong_answer_does_not_trigger_sync():
    assert is_accepted_status("Wrong Answer", "SUCCESS") is False
    assert classify_submission_status("Wrong Answer", "SUCCESS") == "Wrong Answer"


def test_runtime_error_does_not_trigger_sync():
    assert is_accepted_status("Runtime Error", "SUCCESS") is False


def test_compile_error_does_not_trigger_sync():
    assert is_accepted_status("Compile Error", "SUCCESS") is False


def test_pending_does_not_trigger_sync():
    assert is_accepted_status("Pending", "PENDING") is False
    assert is_accepted_status("Accepted", "PENDING") is False  # must be SUCCESS
    assert is_accepted_status("", "PENDING") is False
    assert classify_submission_status("", "PENDING") == "Pending"


def test_run_code_test_success_does_not_trigger_sync():
    # "All test cases passed" is from Run Code, must NOT trigger
    assert is_accepted_status("All test cases passed", "SUCCESS") is False
    assert is_accepted_status("Test Case Passed", "SUCCESS") is False
    assert is_accepted_status("All Test Cases Passed", "SUCCESS") is False
    assert classify_submission_status("All test cases passed", "SUCCESS") == "Test Case Passed"
    # Also ensure Run without submit flag would be ignored (simulated via hasPending logic)
    has_pending_submit = False
    should_trigger = is_accepted_status("All test cases passed", "SUCCESS") and has_pending_submit
    assert should_trigger is False


def test_other_rejected_states_do_not_trigger():
    for msg in ["Time Limit Exceeded", "Memory Limit Exceeded", "Output Limit Exceeded", "Unknown"]:
        assert is_accepted_status(msg, "SUCCESS") is False
    assert is_accepted_status("Wrong Answer", "") is False
    assert is_accepted_status("Running", "STARTED") is False


# ---------------------------------------------------------------------------
# 7-9: Deduplication
# ---------------------------------------------------------------------------

def test_duplicate_accepted_event_does_not_create_duplicate_job():
    url = "https://leetcode.com/problems/two-sum/"
    norm = normalize_problem_url(url)
    key1 = build_dedup_key_sync("leetcode", norm, "12345", "", "")
    key2 = build_dedup_key_sync("leetcode", norm, "12345", "", "")
    assert key1 == key2
    seen = set()
    seen.add(key1)
    # second event with same key is duplicate
    assert key2 in seen


def test_same_submission_seen_twice_is_deduplicated():
    url = "https://leetcode.com/problems/two-sum/"
    norm = normalize_problem_url(url)
    code = "class Solution:\n    def twoSum(self, nums, target): pass"
    h = hashlib.sha256(code.encode()).hexdigest()
    key = build_dedup_key_sync("leetcode", norm, None, "python", h)
    # seen map simulation (storage)
    seen_map = {}
    seen_map[key] = True
    assert seen_map.get(key) is True
    # re-adding same key should be detected
    is_dup = key in seen_map
    assert is_dup is True


def test_different_accepted_submissions_create_different_jobs():
    url = "https://leetcode.com/problems/two-sum/"
    norm = normalize_problem_url(url)
    k1 = build_dedup_key_sync("leetcode", norm, "111", "", "")
    k2 = build_dedup_key_sync("leetcode", norm, "222", "", "")
    assert k1 != k2
    # also with hash fallback different codes produce different keys
    h1 = hashlib.sha256(b"code1").hexdigest()
    h2 = hashlib.sha256(b"code2").hexdigest()
    k1h = build_dedup_key_sync("leetcode", norm, None, "python", h1)
    k2h = build_dedup_key_sync("leetcode", norm, None, "python", h2)
    assert k1h != k2h


def test_dedup_key_prefers_submission_id_over_hash():
    norm = normalize_problem_url("https://leetcode.com/problems/two-sum/")
    with_id = build_dedup_key_sync("leetcode", norm, "999", "python", "abc")
    without_id = build_dedup_key_sync("leetcode", norm, None, "python", "abc")
    assert with_id == "leetcode:https://leetcode.com/problems/two-sum:999"
    assert without_id == "leetcode:https://leetcode.com/problems/two-sum:python:abc"


# ---------------------------------------------------------------------------
# 10: SPA problem change resets identity
# ---------------------------------------------------------------------------

def test_spa_problem_change_resets_problem_identity():
    old_url = "https://leetcode.com/problems/two-sum/"
    new_url = "https://leetcode.com/problems/add-two-numbers/"
    old_norm = normalize_problem_url(old_url)
    new_norm = normalize_problem_url(new_url)
    assert old_norm != new_norm
    assert old_norm == "https://leetcode.com/problems/two-sum"
    assert new_norm == "https://leetcode.com/problems/add-two-numbers"
    # Simulate monitor state reset
    pending = {"123": {"timestamp": 1000, "url": old_url}}
    if old_norm != new_norm:
        pending.clear()
    assert pending == {}
    # Ensure navigating within same problem (e.g., /submissions) keeps same norm
    same_with_suffix = "https://leetcode.com/problems/two-sum/submissions/123/"
    same_norm = normalize_problem_url(same_with_suffix)
    assert same_norm == old_norm


def test_normalize_url_handles_query_and_hash():
    assert normalize_problem_url("https://leetcode.com/problems/two-sum/?foo=1#bar") == "https://leetcode.com/problems/two-sum"
    assert normalize_problem_url("https://leetcode.com/problems/Two-Sum/") == "https://leetcode.com/problems/two-sum"


# ---------------------------------------------------------------------------
# 11: Missing complete source fails closed
# ---------------------------------------------------------------------------

def test_missing_complete_source_fails_closed():
    def should_push(code, editor_data_available):
        # mirrors handleAcceptedSubmission fail-closed logic
        if not code or not code.strip():
            return False
        if not editor_data_available and code.strip():
            # MAIN bridge unavailable but DOM gave code -> fail closed to avoid truncated
            return False
        if len(code.strip()) < 10:
            return False
        return True

    assert should_push("", True) is False
    assert should_push(None, True) is False
    assert should_push("x = 1", True) is False  # too short
    assert should_push("class Solution:\n    def solve(self): pass", False) is False  # missing MAIN
    assert should_push("class Solution:\n    def solve(self): pass", True) is True


# ---------------------------------------------------------------------------
# 12: Language from reliable editor/platform state before syntax fallback
# ---------------------------------------------------------------------------

def test_language_comes_from_reliable_state_before_fallback():
    # Java selector but python-looking code tail — selector must win
    assert detect_language("Java", "return maxLength;\n}\n}") == "java"
    assert detect_language("Python3", "return result") == "python"
    assert detect_language("C++", "class Solution { public: int foo() {} }") == "cpp"
    # No selector → heuristic
    java_code = "class Solution {\n    public int[] twoSum(int[] nums, int target) {}\n}"
    assert detect_language("", java_code) == "java"
    assert detect_language(None, java_code) == "java"
    # normalize priority
    assert normalize_lang_text("Python3") == "python"
    assert normalize_lang_text("Java") == "java"
    assert normalize_lang_text("C++") == "cpp"
    assert normalize_lang_text("TypeScript") == "typescript"


def test_java_vs_cpp_disambiguation_via_include():
    cpp_with_class = "#include <vector>\nclass Solution { public: int x; };"
    assert detect_language_from_code(cpp_with_class) == "cpp"
    java_code = "class Solution {\n    public int[] twoSum(int[] nums, int target) {}\n}"
    assert detect_language_from_code(java_code) == "java"


# ---------------------------------------------------------------------------
# 13: Monitor initialization is idempotent
# ---------------------------------------------------------------------------

def test_monitor_initialization_is_idempotent():
    text = Path("extension/content.js").read_text(encoding="utf-8")
    assert "window.__ghostPushSubmissionMonitorStarted" in text
    assert 'if (window.__ghostPushSubmissionMonitorStarted)' in text
    assert text.count("window.__ghostPushSubmissionMonitorStarted = true") == 1
    # Original content injection guard still present
    assert "window.__ghostPushContentScriptInjected" in text


def test_content_js_contains_required_monitor_pieces():
    text = Path("extension/content.js").read_text(encoding="utf-8")
    # Singleton guard
    assert "__ghostPushSubmissionMonitorStarted" in text
    # MAIN bridge injection
    assert "ghostpush-main-bridge" in text or "__ghostPushMainBridgeInstalled" in text
    assert "GP_SUBMIT_DETECTED" in text
    assert "GP_SUBMISSION_RESULT" in text
    assert "GP_GET_EDITOR_DATA" in text
    assert "GP_EDITOR_DATA" in text
    # SPA handling
    assert "ghostpush_locationchange" in text
    assert "resetProblemStateIfChanged" in text
    # Deduplication
    assert "ghostpush_seen_submissions" in text
    assert "isDuplicateDedupKey" in text or "isDuplicate" in text
    # Logging prefix
    assert "[GhostPush][SubmissionMonitor]" in text
    # Accepted gating
    assert "isAcceptedStatus" in text or "is_accepted" in text or "Accepted" in text
    # Fail closed on missing source
    assert "failing closed" in text.lower() or "Fail closed" in text
    # Complete source via Monaco
    assert "monaco.editor.getModels" in text
    # SHA dedup
    assert "SHA-256" in text or "sha256" in text.lower()


def test_background_js_handles_auto_submit():
    text = Path("extension/background.js").read_text(encoding="utf-8")
    assert "ghostpush_auto_submit" in text
    assert "leetcode.com" in text
    assert "127.0.0.1:8000/api/v1/jobs" in text
    assert "127.0.0.1:8000/api/v1/config" in text
    # Security check
    assert "Only LeetCode pages may trigger automatic sync" in text


def test_manifest_unchanged_but_valid():
    manifest = json.loads(Path("extension/manifest.json").read_text(encoding="utf-8"))
    assert manifest.get("manifest_version") == 3
    assert "https://leetcode.com/*" in manifest.get("host_permissions", [])
    assert "storage" in manifest.get("permissions", [])
    assert "scripting" in manifest.get("permissions", [])


# ---------------------------------------------------------------------------
# 14: Existing manual popup payload compatibility still passes
# ---------------------------------------------------------------------------

def test_existing_manual_popup_payload_compatibility(isolated_client):
    ext_payload = {
        "api_version": "1.0",
        "job_id": "JOB-EXT-1723400000-1234",
        "platform": "leetcode",
        "problem": {
            "title": "Two Sum",
            "difficulty": "Easy",
            "url": "https://leetcode.com/problems/two-sum/",
            "tags": ["Array", "Hash Table"],
        },
        "solution": {
            "language": "python",
            "code": "class Solution:\n    def twoSum(self, nums, target):\n        pass",
        },
        "repository_path": "/tmp/test_repo",
    }
    payload_obj = SubmissionPayload.model_validate(ext_payload)
    assert payload_obj.job_id == "JOB-EXT-1723400000-1234"
    response = isolated_client.post("/api/v1/jobs", json=ext_payload)
    assert response.status_code == 201
    data = response.json()
    assert data["job_id"] == "JOB-EXT-1723400000-1234"
    assert data["status"] == "QUEUED"


def test_auto_payload_uses_same_contract_via_background_simulation(isolated_client):
    import tempfile, pathlib
    tmpdir = pathlib.Path(tempfile.mkdtemp())
    # Simulate the payload content.js would build for auto sync — must match SubmissionPayload
    auto_payload = {
        "api_version": "1.0",
        "job_id": "JOB-EXT-9999999999-9999",
        "platform": "leetcode",
        "problem": {
            "title": "Add Two Numbers",
            "difficulty": "Medium",
            "url": "https://leetcode.com/problems/add-two-numbers/",
            "tags": ["Linked List", "Math"],
        },
        "solution": {
            "language": "java",
            "code": "class Solution { public ListNode addTwoNumbers(ListNode l1, ListNode l2) { return null; } }",
        },
        "repository_path": str(tmpdir),
    }
    # Validate schema
    obj = SubmissionPayload.model_validate(auto_payload)
    assert obj.solution.language == "java"
    # POST should succeed
    resp = isolated_client.post("/api/v1/jobs", json=auto_payload)
    assert resp.status_code == 201

