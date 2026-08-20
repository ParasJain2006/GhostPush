import os
import subprocess
from typing import Optional, Tuple

from common.errors import GhostPushError, ErrorCode


class GitTool:
    """Tool for managing Git operations such as commit, push, and rollback."""

    @staticmethod
    def _run_git_cmd(cmd: list, cwd: str) -> Tuple[int, str, str]:
        """Runs a git command in cwd using subprocess."""
        try:
            res = subprocess.run(
                ["git"] + cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False,
            )
            return res.returncode, res.stdout.strip(), res.stderr.strip()
        except Exception as e:
            return 1, "", str(e)

    @classmethod
    def init_or_open_repo(cls, repo_path: str) -> bool:
        """Ensures that repo_path is a valid Git repository."""
        if not os.path.exists(repo_path):
            os.makedirs(repo_path, exist_ok=True)

        git_dir = os.path.join(repo_path, ".git")
        if not os.path.exists(git_dir):
            code, stdout, stderr = cls._run_git_cmd(["init"], repo_path)
            if code != 0:
                raise GhostPushError(
                    ErrorCode.GIT_FAILED,
                    f"Failed to initialize Git repository at {repo_path}: {stderr}",
                )
        return True

    @classmethod
    def set_remote(
        cls, repo_path: str, remote_url: str, remote_name: str = "origin"
    ) -> bool:
        """Sets or updates the remote URL for the specified git repository."""
        cls.init_or_open_repo(repo_path)
        if not remote_url or not remote_url.strip():
            return False

        # Check existing remotes
        code, stdout, _ = cls._run_git_cmd(["remote"], repo_path)
        remotes = stdout.splitlines() if stdout else []

        if remote_name in remotes:
            code_set, _, stderr_set = cls._run_git_cmd(
                ["remote", "set-url", remote_name, remote_url.strip()], repo_path
            )
            if code_set != 0:
                raise GhostPushError(
                    ErrorCode.GIT_FAILED,
                    f"Failed to update remote {remote_name}: {stderr_set}",
                )
        else:
            code_add, _, stderr_add = cls._run_git_cmd(
                ["remote", "add", remote_name, remote_url.strip()], repo_path
            )
            if code_add != 0:
                raise GhostPushError(
                    ErrorCode.GIT_FAILED,
                    f"Failed to add remote {remote_name}: {stderr_add}",
                )
        return True

    @classmethod
    def commit(cls, repo_path: str, platform: str, title: str) -> str:
        """Stages files and creates a git commit using the required convention:

        feat(<platform>): add <title> solution
        Returns commit hash on success.
        """
        cls.init_or_open_repo(repo_path)

        # Stage all changes
        code, stdout, stderr = cls._run_git_cmd(["add", "."], repo_path)
        if code != 0:
            raise GhostPushError(
                ErrorCode.GIT_FAILED, f"Failed to stage git files: {stderr}"
            )

        commit_msg = f"feat({platform.lower()}): add {title} solution"

        # Check if anything is staged to commit
        code_diff, stdout_diff, stderr_diff = cls._run_git_cmd(
            ["status", "--porcelain"], repo_path
        )
        if not stdout_diff:
            # Nothing to commit, retrieve latest commit hash if present
            code_rev, stdout_rev, _ = cls._run_git_cmd(
                ["rev-parse", "HEAD"], repo_path
            )
            return stdout_rev if code_rev == 0 else "NO_CHANGES"

        # Execute commit
        code_commit, stdout_commit, stderr_commit = cls._run_git_cmd(
            ["commit", "-m", commit_msg], repo_path
        )
        if code_commit != 0:
            raise GhostPushError(
                ErrorCode.GIT_FAILED, f"Git commit failed: {stderr_commit}"
            )

        # Get latest commit hash
        code_rev, stdout_rev, stderr_rev = cls._run_git_cmd(
            ["rev-parse", "HEAD"], repo_path
        )
        if code_rev != 0:
            return "COMMITTED"
        return stdout_rev

    @classmethod
    def push(
        cls,
        repo_path: str,
        remote_url: Optional[str] = None,
        remote: str = "origin",
        branch: str = "main",
    ) -> bool:
        """Pushes local commits to remote repository."""
        cls.init_or_open_repo(repo_path)

        if remote_url and remote_url.strip():
            cls.set_remote(repo_path, remote_url=remote_url, remote_name=remote)

        code, stdout, stderr = cls._run_git_cmd(
            ["push", remote, branch], repo_path
        )

        if code != 0:
            # Check if remote exists before raising hard error
            code_remote, stdout_remote, _ = cls._run_git_cmd(
                ["remote", "-v"], repo_path
            )
            if not stdout_remote:
                # No remote configured yet, return false without raising fatal error
                return False
            raise GhostPushError(
                ErrorCode.GIT_FAILED, f"Git push failed: {stderr}"
            )
        return True

    @classmethod
    def rollback(cls, repo_path: str) -> bool:
        """Rolls back uncommitted changes or resets hard if a failure occurs."""
        if not os.path.exists(repo_path):
            return True
        code, stdout, stderr = cls._run_git_cmd(["reset", "--hard"], repo_path)
        code_clean, stdout_clean, stderr_clean = cls._run_git_cmd(
            ["clean", "-fd"], repo_path
        )
        return code == 0 and code_clean == 0
