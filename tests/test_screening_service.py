"""Comprehensive unit tests for the UI-free service layer (Milestone M4).

Tests:
- Job description analysis (analyze_job) across valid, empty, and edge inputs.
- Resume ingestion (parse_resumes) across formats, streams, and corrupted inputs.
- Multi-component ranking (rank) with 4-component weights and TF-IDF baseline.
- Pydantic v2 schemas serialization, validation, and defaults.
- End-to-end screening convenience pipeline (screen).
"""

import io
import math
from pathlib import Path
import pytest
from pydantic import ValidationError

from src.schemas import (
    CandidateRanking,
    ComponentScores,
    JobAnalysis,
    ParsedResume,
    ResumeSections,
    ScreeningResult,
    WeightConfig,
)
from src.services.screening_service import (
    analyze_job,
    extract_candidate_experience_years,
    parse_resumes,
    rank,
    screen,
)


# ==============================================================================
# 1. Job Description Analysis Tests
# ==============================================================================

def test_analyze_job_valid_text() -> None:
    """Verifies analyze_job correctly extracts required/preferred skills and experience."""
    jd_text = (
        "Senior Cloud Engineer\n\n"
        "Requirements (Must Have):\n"
        "- Minimum 5 years of software engineering experience\n"
        "- Production proficiency with Python, Docker, and Kubernetes\n\n"
        "Preferred Qualifications (Nice to Have):\n"
        "- Hands-on experience with AWS and Terraform\n"
        "- Familiarity with PostgreSQL"
    )
    analysis = analyze_job(jd_text)
    assert isinstance(analysis, JobAnalysis)
    assert analysis.raw_text == jd_text
    assert len(analysis.cleaned_text) > 0
    assert analysis.min_experience_years == 5.0

    # Required skills
    assert "Python" in analysis.required_skills
    assert "Docker" in analysis.required_skills
    assert "Kubernetes" in analysis.required_skills

    # Preferred skills
    assert "AWS" in analysis.preferred_skills
    assert "Terraform" in analysis.preferred_skills

    # All skills union
    assert set(analysis.all_skills) >= {"Python", "Docker", "Kubernetes", "AWS", "Terraform", "PostgreSQL"}


def test_analyze_job_empty_and_whitespace() -> None:
    """Verifies analyze_job handles empty and whitespace inputs gracefully."""
    empty_res = analyze_job("")
    assert isinstance(empty_res, JobAnalysis)
    assert empty_res.raw_text == ""
    assert empty_res.required_skills == []
    assert empty_res.preferred_skills == []
    assert empty_res.all_skills == []
    assert empty_res.min_experience_years is None

    ws_res = analyze_job("   \n\t   ")
    assert isinstance(ws_res, JobAnalysis)
    assert ws_res.required_skills == []
    assert ws_res.preferred_skills == []
    assert ws_res.min_experience_years is None


def test_analyze_job_plain_text_defaults_to_required() -> None:
    """Verifies that unstructured plain text job descriptions default skills to required."""
    text = "We are seeking a developer skilled in Python, Django, and PostgreSQL."
    analysis = analyze_job(text)
    assert "Python" in analysis.required_skills
    assert "Django" in analysis.required_skills
    assert "PostgreSQL" in analysis.required_skills
    assert analysis.preferred_skills == []


# ==============================================================================
# 2. Candidate Experience Extraction Tests
# ==============================================================================

def test_extract_candidate_experience_years_patterns() -> None:
    """Verifies candidate experience regex patterns across varied phrasing."""
    assert extract_candidate_experience_years("6 years building distributed systems in Python.") == 6.0
    assert extract_candidate_experience_years("3 years developing backend scripts with Docker.") == 3.0
    assert extract_candidate_experience_years("5 years as DevOps Lead building K8s clusters.") == 5.0
    assert extract_candidate_experience_years("5 years in machine learning and data science.") == 5.0
    assert extract_candidate_experience_years("4 years experience in React and TypeScript.") == 4.0
    assert extract_candidate_experience_years("Over the past 5 years, candidate has developed...") == 5.0
    assert extract_candidate_experience_years("No numeric experience mentioned.") is None
    assert extract_candidate_experience_years("") is None


# ==============================================================================
# 3. Resume Ingestion (parse_resumes) Tests
# ==============================================================================

def test_parse_resumes_empty_list() -> None:
    """Verifies parse_resumes returns an empty list when given an empty input."""
    assert parse_resumes([]) == []


def test_parse_resumes_corrupted_stream_raises_value_error() -> None:
    """Verifies parse_resumes raises ValueError on corrupted binary streams."""
    corrupted = io.BytesIO(b"GARBAGE_NOT_A_VALID_PDF_OR_DOCX")
    corrupted.name = "corrupt.pdf"
    with pytest.raises(ValueError):
        parse_resumes([corrupted])


def test_parse_resumes_in_memory_docx(tmp_path: Path) -> None:
    """Verifies parse_resumes successfully parses a valid in-memory DOCX stream."""
    import docx

    doc = docx.Document()
    doc.add_heading("Alice Candidate", level=1)
    doc.add_heading("EXPERIENCE", level=2)
    doc.add_paragraph("5 years of experience building Python and FastAPI backend services.")
    doc.add_heading("SKILLS", level=2)
    doc.add_paragraph("Python, FastAPI, Docker, PostgreSQL")

    stream = io.BytesIO()
    doc.save(stream)
    stream.seek(0)
    stream.name = "alice.docx"

    parsed = parse_resumes([stream])
    assert len(parsed) == 1
    resume = parsed[0]
    assert isinstance(resume, ParsedResume)
    assert resume.filename == "alice.docx"
    assert "Python" in resume.raw_text
    assert "Python" in resume.skills
    assert "FastAPI" in resume.skills
    assert resume.experience_years == 5.0
    assert isinstance(resume.sections, ResumeSections)
    assert len(resume.anonymized_text) > 0


# ==============================================================================
# 4. Multi-Component Ranking (rank) Tests
# ==============================================================================

def test_rank_with_default_weights() -> None:
    """Verifies ranking candidates with default WeightConfig."""
    jd = analyze_job("Senior Python Engineer. Required: Python, FastAPI. Preferred: Docker. 4 years exp.")
    c1 = ParsedResume(
        filename="c1.txt",
        raw_text="Python and FastAPI senior engineer with 5 years experience.",
        cleaned_text="Python and FastAPI senior engineer with 5 years experience.",
        skills=["Python", "FastAPI"],
        experience_years=5.0,
    )
    c2 = ParsedResume(
        filename="c2.txt",
        raw_text="Junior developer with HTML and CSS and 1 year experience.",
        cleaned_text="Junior developer with HTML and CSS and 1 year experience.",
        skills=["HTML", "CSS"],
        experience_years=1.0,
    )

    rankings = rank(job=jd, resumes=[c1, c2])
    assert len(rankings) == 2
    assert rankings[0].rank == 1 and rankings[1].rank == 2
    assert rankings[0].candidate == "c1.txt"
    assert rankings[0].match_score > rankings[1].match_score
    assert rankings[0].component_scores.required_skill_score == 1.0
    assert rankings[0].component_scores.experience_score == 1.0
    assert rankings[0].component_scores.tfidf_baseline_score is not None


def test_rank_empty_resumes_returns_empty_list() -> None:
    """Verifies rank returns an empty list when candidate resumes list is empty."""
    jd = analyze_job("Senior Engineer")
    assert rank(job=jd, resumes=[]) == []


def test_rank_zero_weights_avoids_zero_division() -> None:
    """Verifies rank handles all-zero weights without ZeroDivisionError."""
    jd = analyze_job("Backend Engineer. Required: Python, Docker.")
    cand = ParsedResume(
        filename="c.txt",
        raw_text="Python and Docker engineer.",
        cleaned_text="Python and Docker engineer.",
        skills=["Python", "Docker"],
        experience_years=3.0,
    )
    zero_weights = WeightConfig(
        required_skill_weight=0.0,
        preferred_skill_weight=0.0,
        semantic_weight=0.0,
        experience_weight=0.0,
    )
    rankings = rank(job=jd, resumes=[cand], weights=zero_weights)
    assert len(rankings) == 1
    assert rankings[0].match_score == 0.0
    assert rankings[0].component_scores.required_skill_score == 1.0


def test_rank_empty_candidate_text_scores_zero() -> None:
    """Verifies candidate with empty text scores 0.0 across all components."""
    jd = analyze_job("Python Developer. Required: Python.")
    empty_cand = ParsedResume(filename="empty.txt", raw_text="", cleaned_text="", skills=[], experience_years=0.0)
    valid_cand = ParsedResume(filename="valid.txt", raw_text="Python dev.", cleaned_text="Python dev.", skills=["Python"], experience_years=3.0)

    rankings = rank(job=jd, resumes=[empty_cand, valid_cand])
    empty_r = [r for r in rankings if r.candidate == "empty.txt"][0]
    assert empty_r.match_score == 0.0
    assert empty_r.component_scores.semantic_score == 0.0
    assert empty_r.component_scores.tfidf_baseline_score == 0.0
    assert empty_r.component_scores.required_skill_score == 0.0
    assert empty_r.rank == 2


def test_rank_identical_job_and_candidate_text() -> None:
    """Verifies identical JD and resume text results in near-perfect semantic and tfidf scores."""
    text = "Senior Python and FastAPI Backend Engineer with Docker and PostgreSQL."
    jd = analyze_job(text)
    cand = ParsedResume(
        filename="identical.txt",
        raw_text=text,
        cleaned_text=text,
        skills=["Python", "FastAPI", "Docker", "PostgreSQL"],
        experience_years=5.0,
    )
    rankings = rank(job=jd, resumes=[cand])
    assert len(rankings) == 1
    r = rankings[0]
    assert r.component_scores.semantic_score >= 0.99
    assert r.component_scores.tfidf_baseline_score >= 0.99
    assert r.component_scores.required_skill_score == 1.0


def test_rank_accepts_raw_string_and_dict_resumes() -> None:
    """Verifies rank accepts plain strings for job and raw dictionaries for resumes."""
    jd_str = "Python Engineer. Required: Python."
    dict_cand = {
        "name": "dict_dev.txt",
        "text": "Experienced Python engineer with 4 years experience.",
        "skills": ["Python"],
        "experience_years": 4.0,
    }
    rankings = rank(job=jd_str, resumes=[dict_cand])
    assert len(rankings) == 1
    assert rankings[0].candidate == "dict_dev.txt"
    assert "Python" in rankings[0].matched_required_skills


def test_pipeline_demographic_evaluation_invariance() -> None:
    """Verifies complete demographic evaluation invariance between candidates differing only in PII."""
    import docx

    def _create_resume_docx(
        name: str, email: str, phone: str, pronoun_subj: str, pronoun_poss: str
    ) -> io.BytesIO:
        doc = docx.Document()
        doc.add_heading(name, level=1)
        doc.add_paragraph(f"Email: {email} | Phone: {phone}")
        doc.add_paragraph(f"{pronoun_subj.capitalize()} is a dedicated engineer with 6 years of experience.")
        doc.add_paragraph(
            f"Throughout {pronoun_poss} career, {pronoun_subj} has developed scalable microservices in Python, Docker, and Kubernetes."
        )
        doc.add_heading("Experience", level=2)
        doc.add_paragraph("Senior Backend Developer (2018 - 2024, 6 years)")
        doc.add_paragraph("Proficient with AWS, PostgreSQL, Docker, and Python.")
        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        buf.name = f"{name.replace(' ', '_')}.docx"
        return buf

    stream1 = _create_resume_docx("David Miller", "david.miller@example.com", "(555) 123-4567", "he", "his")
    stream2 = _create_resume_docx("Fatima Al-Mansoor", "fatima.almansoor@example.com", "+1 555-987-6543", "she", "her")

    parsed_resumes = parse_resumes([stream1, stream2])
    assert len(parsed_resumes) == 2

    job_description = (
        "Senior Python Engineer\n\n"
        "Requirements:\n"
        "- 5 years of software engineering experience\n"
        "- Python, Docker, Kubernetes\n\n"
        "Preferred Qualifications:\n"
        "- AWS, PostgreSQL"
    )

    rankings = rank(job=job_description, resumes=parsed_resumes)
    assert len(rankings) == 2
    assert rankings[0].match_score == rankings[1].match_score
    assert abs(rankings[0].match_score - rankings[1].match_score) == 0.0
    assert rankings[0].component_scores.semantic_score == rankings[1].component_scores.semantic_score
    assert rankings[0].component_scores.tfidf_baseline_score == rankings[1].component_scores.tfidf_baseline_score
    assert rankings[0].component_scores.required_skill_score == rankings[1].component_scores.required_skill_score
    assert rankings[0].component_scores.preferred_skill_score == rankings[1].component_scores.preferred_skill_score
    assert rankings[0].component_scores.experience_score == rankings[1].component_scores.experience_score


# ==============================================================================
# 5. Schema Validation, Defaults, and Serialization Tests
# ==============================================================================

def test_weight_config_defaults_and_validation() -> None:
    """Verifies WeightConfig default values and bounds validation."""
    wc = WeightConfig()
    assert wc.required_skill_weight == 0.5
    assert wc.preferred_skill_weight == 0.2
    assert wc.semantic_weight == 0.2
    assert wc.experience_weight == 0.1
    assert math.isclose(
        wc.required_skill_weight + wc.preferred_skill_weight + wc.semantic_weight + wc.experience_weight,
        1.0,
    )

    # Rejection of out-of-bounds weights
    with pytest.raises(ValidationError):
        WeightConfig(required_skill_weight=-0.1)
    with pytest.raises(ValidationError):
        WeightConfig(semantic_weight=1.5)


def test_candidate_ranking_serialization() -> None:
    """Verifies CandidateRanking serializes and deserializes accurately with Pydantic v2."""
    cr = CandidateRanking(
        rank=1,
        candidate="Dev One",
        match_score=92.5,
        component_scores=ComponentScores(
            required_skill_score=1.0,
            preferred_skill_score=0.5,
            semantic_score=0.85,
            experience_score=1.0,
            tfidf_baseline_score=0.80,
        ),
        matched_skills=["Python", "Docker"],
        missing_skills=[],
        matched_required_skills=["Python"],
        matched_preferred_skills=["Docker"],
        missing_required_skills=[],
    )
    dumped = cr.model_dump()
    assert dumped["candidate"] == "Dev One"
    assert dumped["match_score"] == 92.5
    assert dumped["component_scores"]["required_skill_score"] == 1.0

    restored = CandidateRanking.model_validate(dumped)
    assert restored.candidate == "Dev One"
    assert restored.match_score == 92.5


# ==============================================================================
# 6. Screening Result & Pipeline (screen) Tests
# ==============================================================================

def test_screen_pipeline_returns_screening_result() -> None:
    """Verifies the convenience screen() function coordinates analysis, parsing, and ranking."""
    jd = "Software Engineer. Required: Python."
    # Passing empty list of files
    result = screen(job=jd, files=[])
    assert isinstance(result, ScreeningResult)
    assert isinstance(result.job, JobAnalysis)
    assert result.rankings == []
    assert result.total_resumes == 0
