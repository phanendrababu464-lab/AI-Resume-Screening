"""Unit and integration tests for the Minimum-Experience Gate (Requirement 1).

Validates:
1. Candidate below minimum experience receives below_min_experience=True flag.
2. Final score is multiplied by the configurable experience penalty (default 0.6).
3. Candidate meeting or exceeding minimum experience is not penalized.
4. Job with no minimum experience does not trigger penalty.
5. Configurable penalty multiplier is respected.
6. The 4 component scoring weights sum to 1.0 regardless of experience penalty.
"""

from __future__ import annotations

import math
import pytest
from pydantic import ValidationError

from src.schemas import CandidateRanking, JobAnalysis, ParsedResume, WeightConfig
from src.services.screening_service import analyze_job, rank


def test_candidate_below_min_experience_penalty_and_flag() -> None:
    """Verifies that a candidate below minimum experience gets below_min_experience=True and 0.6 penalty."""
    job = analyze_job(
        "Senior Backend Engineer. Minimum 5 years of software engineering experience required. "
        "Required: Python, FastAPI. Preferred: Docker."
    )
    assert job.min_experience_years == 5.0

    # Candidate A: 2.0 years experience (< 5.0 min)
    cand_below = ParsedResume(
        filename="junior.txt",
        raw_text="Backend engineer with Python, FastAPI, and Docker. 2 years of experience.",
        cleaned_text="Backend engineer with Python, FastAPI, and Docker. 2 years of experience.",
        skills=["Python", "FastAPI", "Docker"],
        experience_years=2.0,
    )

    # Candidate B: identical skills and text, but with 5.0 years experience (meets 5.0 min)
    cand_meets = ParsedResume(
        filename="senior.txt",
        raw_text="Backend engineer with Python, FastAPI, and Docker. 5 years of experience.",
        cleaned_text="Backend engineer with Python, FastAPI, and Docker. 5 years of experience.",
        skills=["Python", "FastAPI", "Docker"],
        experience_years=5.0,
    )

    rankings = rank(job=job, resumes=[cand_below, cand_meets])
    assert len(rankings) == 2

    r_below = next(r for r in rankings if r.candidate == "junior.txt")
    r_meets = next(r for r in rankings if r.candidate == "senior.txt")

    # Flag verification
    assert r_below.below_min_experience is True
    assert r_meets.below_min_experience is False

    # Mathematical penalty verification (default penalty is 0.6)
    # Both have req_score=1.0, pref_score=1.0, identical sem_score
    # cand_below exp_score = 2/5 = 0.4; cand_meets exp_score = 5/5 = 1.0
    comp_below = r_below.component_scores
    unpenalized_below_raw = (
        0.5 * comp_below.required_skill_score
        + 0.2 * comp_below.preferred_skill_score
        + 0.2 * comp_below.semantic_score
        + 0.1 * comp_below.experience_score
    ) * 100.0
    expected_penalized_score = round(unpenalized_below_raw * 0.6, 2)
    assert abs(r_below.match_score - expected_penalized_score) <= 0.05

    # Meeting minimum experience must score strictly higher
    assert r_meets.match_score > r_below.match_score


def test_configurable_experience_penalty_multiplier() -> None:
    """Verifies that custom experience_penalty in WeightConfig is respected."""
    job = analyze_job("DevOps Engineer. Minimum 4 years experience required. Required: Kubernetes.")
    cand = ParsedResume(
        filename="candidate.txt",
        raw_text="DevOps with Kubernetes. 2 years experience.",
        skills=["Kubernetes"],
        experience_years=2.0,
    )

    # Test with penalty = 0.5
    cfg_50 = WeightConfig(experience_penalty=0.5)
    r_50 = rank(job=job, resumes=[cand], weights=cfg_50)[0]
    assert r_50.below_min_experience is True

    # Test with penalty = 0.8
    cfg_80 = WeightConfig(experience_penalty=0.8)
    r_80 = rank(job=job, resumes=[cand], weights=cfg_80)[0]
    assert r_80.below_min_experience is True

    # Test with penalty = 1.0 (no penalty)
    cfg_100 = WeightConfig(experience_penalty=1.0)
    r_100 = rank(job=job, resumes=[cand], weights=cfg_100)[0]
    assert r_100.below_min_experience is True

    assert r_50.match_score < r_80.match_score < r_100.match_score


def test_candidate_exceeding_min_experience_not_penalized() -> None:
    """Verifies candidates exceeding min experience have below_min_experience=False and no penalty."""
    job = analyze_job("Lead Engineer. Minimum 5 years required. Required: Python.")
    cand = ParsedResume(
        filename="lead.txt",
        raw_text="Lead engineer with 8 years experience in Python.",
        skills=["Python"],
        experience_years=8.0,
    )
    r = rank(job=job, resumes=[cand])[0]
    assert r.below_min_experience is False
    assert r.component_scores.experience_score == 1.0


def test_job_without_minimum_experience_does_not_penalize() -> None:
    """Verifies that jobs without a minimum experience requirement never penalize candidates."""
    job = analyze_job("Software Developer. Required: Python, Docker.")
    assert job.min_experience_years is None

    cand = ParsedResume(
        filename="junior.txt",
        raw_text="Junior developer with Python and Docker. 1 year experience.",
        skills=["Python", "Docker"],
        experience_years=1.0,
    )
    r = rank(job=job, resumes=[cand])[0]
    assert r.below_min_experience is False
    # Under renormalized applicable components, non-applicable experience shows None (N/A)
    assert r.component_scores.experience_score is None

    # Legacy un-renormalized ablation verifies 1.0
    r_legacy = rank(job=job, resumes=[cand], weights=WeightConfig(renormalize_weights=False))[0]
    assert r_legacy.component_scores.experience_score == 1.0


def test_scoring_weights_sum_to_one() -> None:
    """Verifies that the 4 component weights sum to 1.0, and experience_penalty is independent."""
    wc_default = WeightConfig()
    total_default = (
        wc_default.required_skill_weight
        + wc_default.preferred_skill_weight
        + wc_default.semantic_weight
        + wc_default.experience_weight
    )
    assert math.isclose(total_default, 1.0, abs_tol=1e-6)
    assert wc_default.experience_penalty == 0.6

    # Custom weights summing to 1.0
    wc_custom = WeightConfig(
        required_skill_weight=0.4,
        preferred_skill_weight=0.3,
        semantic_weight=0.2,
        experience_weight=0.1,
        experience_penalty=0.75,
    )
    total_custom = (
        wc_custom.required_skill_weight
        + wc_custom.preferred_skill_weight
        + wc_custom.semantic_weight
        + wc_custom.experience_weight
    )
    assert math.isclose(total_custom, 1.0, abs_tol=1e-6)
    assert wc_custom.experience_penalty == 0.75
