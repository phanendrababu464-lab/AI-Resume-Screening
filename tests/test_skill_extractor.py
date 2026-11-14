"""Unit tests for the TechnicalSkillExtractor module."""

import json
from pathlib import Path
import pytest

from src.skill_extractor import TechnicalSkillExtractor


def test_extractor_with_custom_list(sample_skills_data: list[str]) -> None:
    """Verifies skill extraction using an explicit skill list."""
    extractor = TechnicalSkillExtractor(skills_list=sample_skills_data)
    text = "I have extensive background in Python, fastapi, and Docker along with react."

    extracted = extractor.extract_skills(text)
    assert "Python" in extracted
    assert "FastAPI" in extracted
    assert "Docker" in extracted
    assert "React" in extracted
    assert "Kubernetes" not in extracted


def test_extractor_case_insensitivity(sample_skills_data: list[str]) -> None:
    """Verifies that skills are recognized regardless of casing in the text."""
    extractor = TechnicalSkillExtractor(skills_list=sample_skills_data)
    text = "PYTHON, FastApi, and DOCKER are my core tools."

    extracted = extractor.extract_skills(text)
    assert extracted == ["Docker", "FastAPI", "Python"]


def test_extractor_multi_word_skill(sample_skills_data: list[str]) -> None:
    """Verifies extraction of multi-token technical skills."""
    extractor = TechnicalSkillExtractor(skills_list=sample_skills_data)
    text = "Built several Machine Learning pipelines."

    extracted = extractor.extract_skills(text)
    assert "Machine Learning" in extracted


def test_extractor_empty_input(sample_skills_data: list[str]) -> None:
    """Verifies extractor returns empty list for empty or non-string input."""
    extractor = TechnicalSkillExtractor(skills_list=sample_skills_data)
    assert extractor.extract_skills("") == []
    assert extractor.extract_skills(None) == []  # type: ignore[arg-type]


def test_extractor_with_default_taxonomy() -> None:
    """Verifies extractor loads properly from the default technical_skills.json file."""
    extractor = TechnicalSkillExtractor()
    text = "Proficient in Python, AWS, PostgreSQL, and Kubernetes."

    extracted = extractor.extract_skills(text)
    assert "Python" in extracted
    assert "AWS" in extracted
    assert "PostgreSQL" in extracted
    assert "Kubernetes" in extracted


def test_extractor_file_not_found(tmp_path: Path) -> None:
    """Verifies FileNotFoundError when non-existent path is passed."""
    non_existent = tmp_path / "does_not_exist.json"
    with pytest.raises(FileNotFoundError):
        TechnicalSkillExtractor(skills_path=non_existent)


def test_extractor_invalid_json(tmp_path: Path) -> None:
    """Verifies ValueError when JSON is malformed."""
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid JSON"):
        TechnicalSkillExtractor(skills_path=bad_json)


def test_extractor_missing_skills_key(tmp_path: Path) -> None:
    """Verifies ValueError when JSON lacks root 'skills' key."""
    empty_dict_json = tmp_path / "empty.json"
    empty_dict_json.write_text(json.dumps({"wrong_key": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="must contain a root 'skills' list"):
        TechnicalSkillExtractor(skills_path=empty_dict_json)


def test_calculate_skill_overlap() -> None:
    """Verifies overlap statistics, missing skills, and overlap ratio calculation."""
    resume_skills = ["Python", "Docker", "Git"]
    job_skills = ["Python", "Docker", "Kubernetes", "AWS"]

    overlap = TechnicalSkillExtractor.calculate_skill_overlap(resume_skills, job_skills)

    assert overlap["matched_skills"] == ["Docker", "Python"]
    assert overlap["missing_skills"] == ["AWS", "Kubernetes"]
    assert overlap["extra_skills"] == ["Git"]
    assert overlap["overlap_ratio"] == 0.5


def test_calculate_skill_overlap_empty_jd() -> None:
    """Verifies overlap ratio is 0.0 when job description has no skills."""
    overlap = TechnicalSkillExtractor.calculate_skill_overlap(["Python"], [])
    assert overlap["overlap_ratio"] == 0.0
    assert overlap["matched_skills"] == []
    assert overlap["missing_skills"] == []
