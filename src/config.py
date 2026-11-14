"""Configuration settings and dynamic path definitions.

This module resolves all filesystem paths relative to the project root directory
to guarantee portability across environments without hard-coded paths.
"""

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

# Scoring weights for legacy 2-component ranker
DEFAULT_SEMANTIC_WEIGHT: float = 0.65
DEFAULT_SKILL_WEIGHT: float = 0.35

# 4-Component scoring weights (Requirement R4)
DEFAULT_REQUIRED_SKILL_WEIGHT: float = 0.5
DEFAULT_PREFERRED_SKILL_WEIGHT: float = 0.2
DEFAULT_SEMANTIC_SIMILARITY_WEIGHT: float = 0.2
DEFAULT_EXPERIENCE_WEIGHT: float = 0.1
