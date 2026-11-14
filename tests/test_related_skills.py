"""Unit and integration tests for Related-Skill Partial Credit (Requirement 2).

Validates:
1. Related-only candidate earns partial credit in required/preferred skill coverage.
2. Exact match always scores 1.0 and beats related match.
3. Multiple related skills present selects the highest related-skill credit.
4. Unmatched skills with related matches are reported in related_skills_matched.
5. Exact matches always score 1.0 and do not double count related skills.
6. Scoring weights sum to 1.0.
"""

from __future__ import annotations

import math
import pytest

from src.schemas import CandidateRanking, JobAnalysis, ParsedResume, WeightConfig
from src.services.screening_service import analyze_job, rank


def test_related_only_candidate_gets_partial_credit() -> None:
    """Verifies a candidate with only related skills earns partial credit and appears in related_skills_matched."""
    job = analyze_job("Database Administrator. Required: PostgreSQL.")
    assert "PostgreSQL" in job.required_skills

    # Candidate has MySQL (0.5 related weight to PostgreSQL), but NOT PostgreSQL
    cand = ParsedResume(
        filename="mysql_dev.txt",
        raw_text="Database administrator specializing in MySQL performance tuning. 5 years experience.",
        cleaned_text="Database administrator specializing in MySQL performance tuning. 5 years experience.",
        skills=["MySQL"],
        experience_years=5.0,
    )

    rankings = rank(job=job, resumes=[cand])
    assert len(rankings) == 1
    r = rankings[0]

    # Exact matched skills should be empty
    assert r.matched_required_skills == []
    assert "PostgreSQL" in r.missing_required_skills

    # Partial credit: PostgreSQL gets 0.5 credit via MySQL
    assert r.component_scores.required_skill_score == 0.5
    assert r.match_score > 0.0

    # Reported separately in related_skills_matched
    assert len(r.related_skills_matched) == 1
    assert "PostgreSQL" in r.related_skills_matched[0]
    assert "MySQL" in r.related_skills_matched[0]


def test_exact_match_beats_related_match() -> None:
    """Verifies that an exact skill match (1.0) scores higher than a related match (0.5)."""
    job = analyze_job("Data Architect. Required: PostgreSQL. 5 years exp.")

    # Candidate 1: Exact match with PostgreSQL
    cand_exact = ParsedResume(
        filename="exact.txt",
        raw_text="Data Architect with PostgreSQL database design. 5 years exp.",
        cleaned_text="Data Architect with PostgreSQL database design. 5 years exp.",
        skills=["PostgreSQL"],
        experience_years=5.0,
    )

    # Candidate 2: Related match with MySQL (0.5 credit)
    cand_related = ParsedResume(
        filename="related.txt",
        raw_text="Data Architect with MySQL database design. 5 years exp.",
        cleaned_text="Data Architect with MySQL database design. 5 years exp.",
        skills=["MySQL"],
        experience_years=5.0,
    )

    rankings = rank(job=job, resumes=[cand_exact, cand_related])
    assert len(rankings) == 2

    r_exact = next(r for r in rankings if r.candidate == "exact.txt")
    r_related = next(r for r in rankings if r.candidate == "related.txt")

    # Exact match gets 1.0; related gets 0.5
    assert r_exact.component_scores.required_skill_score == 1.0
    assert r_related.component_scores.required_skill_score == 0.5

    # Exact match candidate ranks #1 and beats related candidate
    assert r_exact.rank == 1
    assert r_related.rank == 2
    assert r_exact.match_score > r_related.match_score


def test_highest_related_skill_credit_selected() -> None:
    """Verifies that when multiple related skills are present, the highest weight is selected."""
    # FastAPI relates to Flask (0.6), Django (0.5), Express.js (0.4)
    job = analyze_job("Backend Developer. Required skills: FastAPI.")
    assert job.required_skills == ["FastAPI"]

    # Candidate has both Django (0.5) and Flask (0.6)
    cand = ParsedResume(
        filename="multi_rel.txt",
        raw_text="API developer with Flask and Django web frameworks.",
        cleaned_text="API developer with Flask and Django web frameworks.",
        skills=["Flask", "Django"],
        experience_years=3.0,
    )

    rankings = rank(job=job, resumes=[cand])
    r = rankings[0]

    # Required skill score should earn 0.6 (highest), not sum (1.1) or 0.5
    assert r.component_scores.required_skill_score == 0.6
    assert len(r.related_skills_matched) == 1
    assert "Flask" in r.related_skills_matched[0]


def test_exact_match_always_scores_one_without_double_credit() -> None:
    """Verifies that an exact match scores 1.0 and does not add related skill credit on top."""
    job = analyze_job("Backend Engineer. Required: FastAPI.")

    # Candidate has both exact match (FastAPI) and related skill (Flask)
    cand = ParsedResume(
        filename="both.txt",
        raw_text="Backend engineer using FastAPI and Flask services.",
        skills=["FastAPI", "Flask"],
        experience_years=4.0,
    )

    rankings = rank(job=job, resumes=[cand])
    r = rankings[0]

    # Exact match scores 1.0; no extra related credit added for FastAPI
    assert r.component_scores.required_skill_score == 1.0
    assert "FastAPI" in r.matched_required_skills
    assert r.missing_required_skills == []
    # No related match needed since FastAPI was already matched exactly
    assert r.related_skills_matched == []


def test_preferred_skill_related_credit() -> None:
    """Verifies that unmatched preferred skills also earn related skill partial credit."""
    job = analyze_job("Cloud Engineer. Required: Python. Preferred: Kubernetes.")

    # Candidate has Python (exact req) and Docker (related to Kubernetes with 0.6)
    cand = ParsedResume(
        filename="cloud.txt",
        raw_text="Cloud engineer with Python and Docker experience.",
        skills=["Python", "Docker"],
        experience_years=4.0,
    )

    rankings = rank(job=job, resumes=[cand])
    r = rankings[0]

    assert r.component_scores.required_skill_score == 1.0
    assert r.component_scores.preferred_skill_score == 0.6
    assert any("Kubernetes" in s and "Docker" in s for s in r.related_skills_matched)


def test_weights_sum_to_one() -> None:
    """Verifies that scoring weights still sum to 1.0."""
    wc = WeightConfig()
    total = (
        wc.required_skill_weight
        + wc.preferred_skill_weight
        + wc.semantic_weight
        + wc.experience_weight
    )
    assert math.isclose(total, 1.0, abs_tol=1e-6)
