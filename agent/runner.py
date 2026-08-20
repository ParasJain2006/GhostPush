from typing import Union, Dict, Any
from common.schemas import SubmissionPayload, AgentResponse
from agent.graph import create_agent_graph


def run_agent_job(payload: Union[SubmissionPayload, Dict[str, Any]]) -> AgentResponse:
    """Entry point to execute the LangGraph Agent pipeline for a submission payload.

    Args:
        payload: SubmissionPayload object or raw dict matching the JSON contract.

    Returns:
        AgentResponse object adhering strictly to the response contract.
    """
    if isinstance(payload, SubmissionPayload):
        payload_dict = payload.model_dump()
    else:
        payload_dict = payload

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

    response_dict = final_state.get("response", {})
    return AgentResponse(**response_dict)


if __name__ == "__main__":
    import tempfile
    import os

    # Example standalone run for demonstration / testing
    with tempfile.TemporaryDirectory() as tmp_dir:
        sample_payload = SubmissionPayload(
            job_id="JOB-DEMO-001",
            platform="leetcode",
            problem={
                "title": "Two Sum",
                "difficulty": "Easy",
                "url": "https://leetcode.com/problems/two-sum/",
                "tags": ["Array", "Hash Table"],
            },
            solution={
                "language": "python",
                "code": "class Solution:\n    def twoSum(self, nums: list[int], target: int) -> list[int]:\n        seen = {}\n        for i, n in enumerate(nums):\n            diff = target - n\n            if diff in seen:\n                return [seen[diff], i]\n            seen[n] = i\n        return []\n",
            },
            repository_path=tmp_dir,
        )

        print("Executing agent run with sample payload...")
        result = run_agent_job(sample_payload)
        print("Agent Response Contract Result:")
        print(result.model_dump_json(indent=2))
