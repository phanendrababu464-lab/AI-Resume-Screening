"""Configuration settings and dynamic path definitions.

This module resolves all filesystem paths relative to the project root directory
to guarantee portability across environments without hard-coded paths.
"""

import os
from pathlib import Path

# Base project paths
BASE_DIR: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = BASE_DIR / "data"
SKILLS_DIR: Path = DATA_DIR / "skills"
DEFAULT_SKILLS_FILE: Path = SKILLS_DIR / "technical_skills.json"

# Automatically load local .env file if it exists
_env_path = BASE_DIR / ".env"
if _env_path.is_file():
    try:
        with open(_env_path, encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    os.environ.setdefault(_k.strip(), _v.strip().strip("'\""))
    except Exception:
        pass

# Model and inference configurations
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
TFIDF_MAX_NGRAM = int(os.getenv("TFIDF_MAX_NGRAM", "2"))
DEFAULT_DEVICE: str = "cpu"

# Supported resume file extensions
ALLOWED_EXTENSIONS: set[str] = {".pdf", ".docx"}

# Maximum batch and upload limits
MAX_RESUMES_PER_BATCH: int = int(os.getenv("MAX_RESUMES_PER_BATCH", "100"))
MAX_FILE_SIZE_BYTES: int = int(os.getenv("MAX_FILE_SIZE_BYTES", str(5 * 1024 * 1024)))  # 5 MB
MAX_BATCH_SIZE_BYTES: int = int(os.getenv("MAX_BATCH_SIZE_BYTES", str(25 * 1024 * 1024)))  # 25 MB

# Google Gemini API configuration
# Accepts either GEMINI_API_KEY (modern standard) or GOOGLE_API_KEY as fallback
GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Scoring weights for legacy 2-component ranker
DEFAULT_SEMANTIC_WEIGHT: float = 0.65
DEFAULT_SKILL_WEIGHT: float = 0.35

# 4-Component scoring weights (Requirement R4)
DEFAULT_REQUIRED_SKILL_WEIGHT: float = 0.5
DEFAULT_PREFERRED_SKILL_WEIGHT: float = 0.2
DEFAULT_SEMANTIC_SIMILARITY_WEIGHT: float = 0.2
DEFAULT_EXPERIENCE_WEIGHT: float = 0.1

# Minimum-experience gate penalty
DEFAULT_EXPERIENCE_PENALTY: float = 0.6

# Automatic weight redistribution for non-applicable components
DEFAULT_RENORMALIZE_WEIGHTS: bool = True

# Related skills mapping file
RELATED_SKILLS_FILE: Path = SKILLS_DIR / "related_skills.json"
