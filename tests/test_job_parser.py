"""Comprehensive unit tests for job description parsing and skill requirement splitting."""

from __future__ import annotations

import pytest

from src.job_parser import (
    extract_min_experience_years,
    parse_job_description,
)


def test_parse_job_description_empty_and_whitespace() -> None:
    """Verifies that empty string or whitespace inputs return valid empty structures."""
    empty_res = parse_job_description("")
    assert empty_res == {
        "raw_text": "",
        "required_skills": [],
        "preferred_skills": [],
        "all_skills": [],
        "min_experience_years": None,
    }

    whitespace_res = parse_job_description("   \n\t  ")
    assert whitespace_res["required_skills"] == []
    assert whitespace_res["preferred_skills"] == []
    assert whitespace_res["all_skills"] == []
    assert whitespace_res["min_experience_years"] is None


def test_parse_job_description_section_headers() -> None:
    """Verifies parsing skills split by standard section headers."""
    jd_text = """
Job Title: Senior Backend Developer

Required Skills:
- 3+ years of Python and SQL
- Experience with Docker and PostgreSQL

Preferred Skills:
- Familiarity with AWS and Kubernetes
- Redis experience
"""
    parsed = parse_job_description(jd_text)

    assert "Python" in parsed["required_skills"]
    assert "SQL" in parsed["required_skills"]
    assert "Docker" in parsed["required_skills"]
    assert "PostgreSQL" in parsed["required_skills"]

    assert "AWS" in parsed["preferred_skills"]
    assert "Kubernetes" in parsed["preferred_skills"]
    assert "Redis" in parsed["preferred_skills"]

    # Disjointness and union check
    assert set(parsed["required_skills"]).isdisjoint(set(parsed["preferred_skills"]))
    assert parsed["all_skills"] == sorted(set(parsed["required_skills"]) | set(parsed["preferred_skills"]))
    assert parsed["min_experience_years"] == 3.0


def test_parse_job_description_alternative_section_headers() -> None:
    """Tests alternative section headers like Minimum Qualifications and Bonus / Nice to Have."""
    jd_text = """
Staff Software Engineer

Minimum Qualifications:
- 5+ years of experience with Go and Linux
- Microservices architecture experience

Nice to Have:
- Experience with Terraform and RabbitMQ
"""
    parsed = parse_job_description(jd_text)

    assert "Go" in parsed["required_skills"]
    assert "Linux" in parsed["required_skills"]
    assert "Terraform" in parsed["preferred_skills"]
    assert "RabbitMQ" in parsed["preferred_skills"]
    assert parsed["min_experience_years"] == 5.0


def test_parse_job_description_inline_cue_phrases() -> None:
    """Tests in-line cue phrases for required ('must have', 'required', 'essential') and preferred ('plus', 'optional', 'bonus')."""
    jd_text = """
We are looking for a Full Stack Engineer.
- Must have solid experience with TypeScript and React.
- Python is required for backend services.
- Docker knowledge is essential.
- Experience with AWS is a plus.
- GraphQL is nice to have.
- Knowledge of MongoDB is optional.
"""
    parsed = parse_job_description(jd_text)

    # Required cue matches
    assert "TypeScript" in parsed["required_skills"]
    assert "React" in parsed["required_skills"]
    assert "Python" in parsed["required_skills"]
    assert "Docker" in parsed["required_skills"]

    # Preferred cue matches
    assert "AWS" in parsed["preferred_skills"]
    assert "GraphQL" in parsed["preferred_skills"]
    assert "MongoDB" in parsed["preferred_skills"]

    assert set(parsed["required_skills"]).isdisjoint(set(parsed["preferred_skills"]))


def test_parse_job_description_precedence_required_overrides_preferred() -> None:
    """Tests that if a skill has conflicting evidence (both required and preferred cues), required wins."""
    jd_text = """
Required:
- Python and Docker

Preferred:
- Python and Kubernetes
"""
    parsed = parse_job_description(jd_text)

    # Python is in required, so it must not be in preferred
    assert "Python" in parsed["required_skills"]
    assert "Docker" in parsed["required_skills"]
    assert "Python" not in parsed["preferred_skills"]
    assert "Kubernetes" in parsed["preferred_skills"]


def test_parse_job_description_no_preferred_only_required() -> None:
    """Tests job description with only required qualifications."""
    jd_text = """
Requirements:
- 4+ years of Java and Spring Boot
- SQL and Git required
"""
    parsed = parse_job_description(jd_text)

    assert "Java" in parsed["required_skills"]
    assert "Spring Boot" in parsed["required_skills"]
    assert "SQL" in parsed["required_skills"]
    assert "Git" in parsed["required_skills"]
    assert parsed["preferred_skills"] == []
    assert parsed["min_experience_years"] == 4.0


def test_parse_job_description_only_preferred_skills() -> None:
    """Tests job description that only lists optional / bonus skills."""
    jd_text = """
Bonus Points:
- Experience with Rust
- Docker and Kubernetes are a plus
"""
    parsed = parse_job_description(jd_text)

    assert parsed["required_skills"] == []
    assert "Rust" in parsed["preferred_skills"]
    assert "Docker" in parsed["preferred_skills"]
    assert "Kubernetes" in parsed["preferred_skills"]


def test_parse_job_description_plain_text_defaults_to_required() -> None:
    """Tests unformatted job description without section headers or cue phrases defaults skills to required."""
    jd_text = "Looking for a software engineer skilled in Python, FastAPI, Docker, and PostgreSQL."
    parsed = parse_job_description(jd_text)

    assert "Python" in parsed["required_skills"]
    assert "FastAPI" in parsed["required_skills"]
    assert "Docker" in parsed["required_skills"]
    assert "PostgreSQL" in parsed["required_skills"]
    assert parsed["preferred_skills"] == []
    assert parsed["all_skills"] == sorted(parsed["required_skills"])


def test_extract_min_experience_years_various_patterns() -> None:
    """Tests various regex patterns for minimum years of experience."""
    assert extract_min_experience_years("3+ years of experience") == 3.0
    assert extract_min_experience_years("At least 5 years of professional software engineering") == 5.0
    assert extract_min_experience_years("3-5 years of industry experience") == 3.0
    assert extract_min_experience_years("3 to 5 years experience required") == 3.0
    assert extract_min_experience_years("Minimum of 4 years experience with distributed systems") == 4.0
    assert extract_min_experience_years("Requires 2.5+ years of experience in Python") == 2.5
    assert extract_min_experience_years("7+ yrs of full-stack development") == 7.0
    assert extract_min_experience_years("experience: 6+ years") == 6.0
    assert extract_min_experience_years("Entry-level role, 0 years of experience required") == 0.0


def test_extract_min_experience_years_guards_and_negatives() -> None:
    """Verifies that non-experience mentions like candidate age or unrelated numbers are not misclassified."""
    assert extract_min_experience_years("Candidate must be at least 21 years old") is None
    assert extract_min_experience_years("No prior experience required for this junior role") is None
    assert extract_min_experience_years("Competitive 401k with 5 percent match") is None
    assert extract_min_experience_years("") is None


def test_parse_job_description_new_req_cues() -> None:
    """Verifies newly expanded required cue patterns: 'must be proficient', 'proficiency', 'a must'."""
    jd_1 = "Candidate must be proficient in Python. Knowledge of Redis is a plus."
    p1 = parse_job_description(jd_1)
    assert "Python" in p1["required_skills"]
    assert "Redis" in p1["preferred_skills"]

    jd_2 = "Strong proficiency in Java is expected; Scala is nice to have."
    p2 = parse_job_description(jd_2)
    assert "Java" in p2["required_skills"]
    assert "Scala" in p2["preferred_skills"]

    jd_3 = "Knowledge of AWS is a must. Docker experience is advantageous."
    p3 = parse_job_description(jd_3)
    assert "AWS" in p3["required_skills"]
    assert "Docker" in p3["preferred_skills"]


def test_parse_job_description_complex_mixed_cues_contrasting_conjunction() -> None:
    """Tests clause splitting across contrasting conjunctions (while, whereas, although, but)."""
    jd_1 = "Must be proficient in Python, while knowledge of Docker and Kubernetes is a big plus."
    p1 = parse_job_description(jd_1)
    assert "Python" in p1["required_skills"]
    assert "Docker" in p1["preferred_skills"]
    assert "Kubernetes" in p1["preferred_skills"]
    assert set(p1["required_skills"]).isdisjoint(set(p1["preferred_skills"]))

    jd_2 = "Experience with AWS is advantageous, whereas Terraform is mandatory."
    p2 = parse_job_description(jd_2)
    assert "Terraform" in p2["required_skills"]
    assert "AWS" in p2["preferred_skills"]

    jd_3 = "Knowledge of SQL is optional, but Python is required for backend services."
    p3 = parse_job_description(jd_3)
    assert "Python" in p3["required_skills"]
    assert "SQL" in p3["preferred_skills"]


def test_parse_job_description_semicolon_clause_splitting_lowercase() -> None:
    """Verifies clause splitting on semicolons regardless of following capitalization."""
    jd_text = "Strong proficiency in Java is required; familiarity with Scala is a plus."
    p = parse_job_description(jd_text)
    assert "Java" in p["required_skills"]
    assert "Scala" in p["preferred_skills"]
    assert set(p["required_skills"]).isdisjoint(set(p["preferred_skills"]))


def test_parse_job_description_key_responsibilities_section_override() -> None:
    """Tests that Key Responsibilities / Duties / Responsibilities resets section to required."""
    jd_text_1 = """
Preferred Qualifications:
- Familiarity with AWS and Kubernetes

Key Responsibilities:
- Develop scalable backend microservices using Python and PostgreSQL.
"""
    p1 = parse_job_description(jd_text_1)
    assert "Python" in p1["required_skills"]
    assert "PostgreSQL" in p1["required_skills"]
    assert "AWS" in p1["preferred_skills"]
    assert "Kubernetes" in p1["preferred_skills"]

    jd_text_2 = """
Nice to Have:
- Experience with Redis

Duties:
- Maintain core data pipelines in Go and Docker.
"""
    p2 = parse_job_description(jd_text_2)
    assert "Go" in p2["required_skills"]
    assert "Docker" in p2["required_skills"]
    assert "Redis" in p2["preferred_skills"]


def test_extract_min_experience_years_candidate_age_guard() -> None:
    """Verifies that candidate age expressions like '25 years of age' do not mask or masquerade as experience."""
    text_mixed = "Candidate must have 5+ years of experience and be at least 25 years of age"
    assert extract_min_experience_years(text_mixed) == 5.0

    text_age_only = "Candidate must be at least 25 years of age"
    assert extract_min_experience_years(text_age_only) is None

    text_range_and_age = "Must have 3-5 years of software development experience and be 21 years of age or older"
    assert extract_min_experience_years(text_range_and_age) == 3.0

    text_plus_and_old = "Candidate should have 4+ years experience and be at least 21 years old"
    assert extract_min_experience_years(text_plus_and_old) == 4.0

