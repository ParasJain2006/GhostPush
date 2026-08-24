import json
import os

from common.constants import DEFAULT_SOLUTION_FILENAMES, LANGUAGE_EXTENSIONS, PLATFORM_DIR_NAMES
from common.errors import GhostPushError, ErrorCode


class FileTool:
    """Tool for managing repository folder structure and solution file creation."""

    @staticmethod
    def format_platform_name(platform: str) -> str:
        """Format platform name according to repository contract (e.g. leetcode -> LeetCode)."""
        platform_lower = platform.lower()
        return PLATFORM_DIR_NAMES.get(platform_lower, platform.capitalize())

    @staticmethod
    def get_extension_for_language(language: str) -> str:
        """Get standard file extension for a programming language."""
        lang_lower = language.lower().strip()
        ext = LANGUAGE_EXTENSIONS.get(lang_lower, "")
        if not ext:
            if lang_lower.startswith("."):
                ext = lang_lower
            else:
                ext = ".txt"
        return ext

    @classmethod
    def write_problem_files(
        cls,
        repo_path: str,
        platform: str,
        title: str,
        language: str,
        code: str,
        readme_content: str,
        metadata: dict,
    ) -> dict:
        """Writes solution, README.md, and metadata.json into the target problem directory.

        Returns a dictionary containing created file paths.
        """
        if not repo_path:
            raise GhostPushError(
                ErrorCode.FILE_WRITE_FAILED, "Repository path cannot be empty."
            )

        platform_folder = cls.format_platform_name(platform)
        problem_folder = title.strip()

        target_dir = os.path.join(repo_path, platform_folder, problem_folder)

        try:
            os.makedirs(target_dir, exist_ok=True)
        except Exception as e:
            raise GhostPushError(
                ErrorCode.FILE_WRITE_FAILED,
                f"Failed to create directory {target_dir}: {str(e)}",
            )

        ext = cls.get_extension_for_language(language)
        solution_filename = DEFAULT_SOLUTION_FILENAMES.get(ext, f"Solution{ext}")
        solution_filepath = os.path.join(target_dir, solution_filename)
        readme_filepath = os.path.join(target_dir, "README.md")
        metadata_filepath = os.path.join(target_dir, "metadata.json")

        try:
            # Write Solution File
            with open(solution_filepath, "w", encoding="utf-8") as f:
                f.write(code)

            # Write README.md
            with open(readme_filepath, "w", encoding="utf-8") as f:
                f.write(readme_content)

            # Write metadata.json
            with open(metadata_filepath, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

        except Exception as e:
            raise GhostPushError(
                ErrorCode.FILE_WRITE_FAILED,
                f"Failed to write problem files in {target_dir}: {str(e)}",
            )

        return {
            "target_dir": target_dir,
            "solution_filepath": solution_filepath,
            "readme_filepath": readme_filepath,
            "metadata_filepath": metadata_filepath,
        }
