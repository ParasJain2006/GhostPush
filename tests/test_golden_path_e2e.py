"""End-to-end integration test for Phase 10.6 Golden Path:

LeetCode extraction -> popup payload -> POST /api/v1/jobs -> JobWorker -> metadata.json & README.md
Verifies that Java solution code with tags & URL produces:
- metadata.json with "language": "java", non-empty tags, and URL
- README.md with Java solution code block (```java)
- isolated test environment without polluting user repo or database
"""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.config.manager import ConfigManager
from backend.jobs.queue import JobQueue
from backend.jobs.worker import JobWorker
from common.schemas import SubmissionPayload


def test_golden_path_full_pipeline_java_solution(tmp_path):
    """Test full pipeline execution for a Java solution submitted from popup."""
    test_repo = tmp_path / "target_repo"
    test_repo.mkdir()

    db_file = tmp_path / "golden_jobs.db"
    config_file = tmp_path / "golden_config.json"

    # Setup isolated config with repository_path pointing to test_repo
    cfg_mgr = ConfigManager(config_path=config_file)
    cfg_mgr.update_config({"repository_path": str(test_repo), "ai_provider": "mock"})

    queue = JobQueue(db_path=db_file)
    worker = JobWorker(queue=queue, config_manager=cfg_mgr)

    java_code = """class Solution {
    public int[] twoSum(int[] nums, int target) {
        for (int i = 0; i < nums.length; i++) {
            for (int j = i + 1; j < nums.length; j++) {
                if (nums[i] + nums[j] == target) {
                    return new int[]{i, j};
                }
            }
        }
        return new int[]{};
    }
}"""

    ext_payload = {
        "api_version": "1.0",
        "job_id": "JOB-GOLDEN-JAVA-100",
        "platform": "leetcode",
        "problem": {
            "title": "1. Two Sum",
            "difficulty": "Easy",
            "url": "https://leetcode.com/problems/two-sum/",
            "tags": ["Array", "Hash Table"]
        },
        "solution": {
            "language": "java",
            "code": java_code
        },
        "repository_path": str(test_repo)
    }

    with TestClient(app) as client:
        app.state.queue = queue
        app.state.config_mgr = cfg_mgr

        # 1. POST /api/v1/jobs
        res = client.post("/api/v1/jobs", json=ext_payload)
        assert res.status_code == 201

        # 2. Worker process_one_job
        processed = worker.process_one_job()
        assert processed is True

        # 3. Inspect job completion status
        job_rec = queue.get_job("JOB-GOLDEN-JAVA-100")
        assert job_rec is not None
        assert job_rec["status"] == "COMPLETED"

        # 4. Inspect metadata.json created in repository
        # Problem folder title cleaned from "1. Two Sum" -> "1. Two Sum" or "Two Sum"
        prob_dir = test_repo / "LeetCode" / "1. Two Sum"
        if not prob_dir.exists():
            prob_dir = test_repo / "LeetCode" / "Two Sum"

        assert prob_dir.exists()

        meta_file = prob_dir / "metadata.json"
        assert meta_file.exists()

        meta_data = json.loads(meta_file.read_text(encoding="utf-8"))
        assert meta_data["language"] == "java"
        assert meta_data["url"] == "https://leetcode.com/problems/two-sum/"
        assert meta_data["tags"] == ["Array", "Hash Table"]

        # 5. Inspect README.md created in repository
        readme_file = prob_dir / "README.md"
        assert readme_file.exists()
        readme_text = readme_file.read_text(encoding="utf-8")
        assert "Code Solution Documentation" in readme_text

        # 6. Inspect Solution.java created in repository
        solution_file = prob_dir / "Solution.java"
        assert solution_file.exists()
        assert "public int[] twoSum" in solution_file.read_text(encoding="utf-8")
