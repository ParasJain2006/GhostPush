from enum import Enum


class Platform(str, Enum):
    LEETCODE = "leetcode"
    GFG = "gfg"
    CODEFORCES = "codeforces"
    HACKERRANK = "hackerrank"


class Language(str, Enum):
    PYTHON = "python"
    JAVA = "java"
    CPP = "cpp"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"


class JobStatus(str, Enum):
    CREATED = "CREATED"
    VALIDATING = "VALIDATING"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    GENERATING_README = "GENERATING_README"
    WRITING_FILES = "WRITING_FILES"
    COMMITTING = "COMMITTING"
    PUSHING = "PUSHING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
