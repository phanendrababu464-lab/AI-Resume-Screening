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

# Model and inference configurations
EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
DEFAULT_DEVICE: str = "cpu"

# Supported resume file extensions
ALLOWED_EXTENSIONS: set[str] = {".pdf", ".docx"}

# Maximum batch and upload limits
MAX_RESUMES_PER_BATCH: int = int(os.getenv("MAX_RESUMES_PER_BATCH", "100"))
MAX_FILE_SIZE_BYTES: int = int(os.getenv("MAX_FILE_SIZE_BYTES", str(5 * 1024 * 1024)))  # 5 MB
MAX_BATCH_SIZE_BYTES: int = int(os.getenv("MAX_BATCH_SIZE_BYTES", str(200 * 1024 * 1024)))  # 200 MB

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
