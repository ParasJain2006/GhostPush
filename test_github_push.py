import os
import tempfile
from agent.runner import run_agent_job
from common.schemas import SubmissionPayload

# 1. Replace with your target GitHub repository URL
# Example: "https://github.com/your-username/your-repo.git" or "git@github.com:your-username/your-repo.git"
TARGET_GITHUB_REPO = "https://github.com/ParasJain2006/GhostPush_Testing_push.git"

# 2. Configure AI Provider and your API Key (e.g. "gemini", "openai", "anthropic", "groq")
# Paste your actual API key in AI_API_KEY to test live AI README generation.
# If left empty (""), the agent cleanly uses the MockLLM fallback.
AI_PROVIDER = "groq"         # Options: "gemini", "openai", "anthropic", "groq"
AI_MODEL = "llama-3.3-70b-versatile"  # Options: "gemini-1.5-flash", "gpt-4o-mini", "claude-3-haiku-20240307", etc.
# Fetch API key from environment variable or set manually
AI_API_KEY = os.getenv("AI_API_KEY", os.getenv("GROQ_API_KEY", ""))                # Set environment variable AI_API_KEY or GROQ_API_KEY

if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as temp_repo:
        print(f"Testing agent git push on repository path: {temp_repo}")
        print(f"AI Settings -> Provider: '{AI_PROVIDER}', Model: '{AI_MODEL}'")
        if AI_API_KEY and AI_API_KEY.strip():
            print("API Key supplied -> Live AI LLM call will generate the README.")
        else:
            print("No API Key supplied -> MockLLM fallback will generate the README.")
        
        payload = SubmissionPayload(
            job_id="PUSH-TEST-001",
            platform="leetcode",
            problem={
                "title": "Reverse Linked List",
                "difficulty": "Easy",
                "url": "https://leetcode.com/problems/reverse-linked-list/",
                "tags": ["Linked List"]
            },
            solution={
                "language": "python",
                "code": "class Solution:\n    def reverseList(self, head):\n        prev = None\n        curr = head\n        while curr:\n            nxt = curr.next\n            curr.next = prev\n            prev = curr\n            curr = nxt\n        return prev\n"
            },
            repository_path=temp_repo,
            remote_repo_url=TARGET_GITHUB_REPO,
            ai_provider=AI_PROVIDER,
            ai_model=AI_MODEL,
            api_key=AI_API_KEY,
        )

        response = run_agent_job(payload)
        print("\n--- Agent Execution Response ---")
        print(response.model_dump_json(indent=2))

