from typing import List, Optional
from pydantic import BaseModel, Field
from common.constants import API_VERSION


class ProblemInfo(BaseModel):
    title: str = Field(..., description="Problem title, e.g. Two Sum")
    difficulty: str = Field(default="Easy", description="Difficulty level")
    url: str = Field(default="", description="Problem URL")
    tags: List[str] = Field(default_factory=list, description="Tags associated with problem")


class SolutionInfo(BaseModel):
    language: str = Field(..., description="Programming language, e.g. python, java, cpp")
    code: str = Field(..., description="Source code of solution")


class SubmissionPayload(BaseModel):
    api_version: str = Field(default=API_VERSION, description="API Version")
    job_id: str = Field(..., description="Unique job ID")
    platform: str = Field(..., description="Platform identifier, e.g. leetcode, gfg")
    problem: ProblemInfo
    solution: SolutionInfo
    repository_path: str = Field(default="", description="Absolute path to target local git repository")
    remote_repo_url: Optional[str] = Field(default="", description="Optional remote repository URL (e.g. https://github.com/user/repo.git)")
    ai_provider: Optional[str] = Field(default="", description="Optional AI Provider selected in Tray App (e.g. gemini, openai, anthropic, groq)")
    ai_model: Optional[str] = Field(default="", description="Optional AI Model selected in Tray App")
    api_key: Optional[str] = Field(default="", description="Optional AI API Key provided by Tray App configuration")


class AgentResponse(BaseModel):
    status: str = Field(..., description="Execution status: SUCCESS or FAILED")
    job_id: str = Field(..., description="Job ID")
    commit_hash: str = Field(default="", description="Git commit hash if committed")
    repository_path: str = Field(default="", description="Repository path where files were stored")
    message: str = Field(default="", description="Summary message or error description")
    push_success: Optional[bool] = Field(default=None, description="Git push status: True=succeeded, False=failed, None=no remote configured")
