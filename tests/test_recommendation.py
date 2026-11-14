"""Unit and integration tests for Recommendation Engine and Visual Analytics Data (Requirement 1 & 4).

Validates:
1. build_recommendation for normal case (clear winner, runner up, margin).
2. build_recommendation for tied top scores (margin == 0.0, tie wording).
3. build_recommendation for single candidate (runner_up is None).
4. build_recommendation for empty candidate list.
5. build_recommendation for below-minimum-experience winner (warning present).
6. build_recommendation when no candidate meets all required skills (cohort warning present).
7. get_score_contributions sums exactly to composite score accounting for experience penalty.
8. Chart data helpers produce valid, decoupled structures for UI rendering.
"""

from __future__ import annotations

import math
import pytest

from src.schemas import (
    CandidateRanking,
    ComponentScores,
    JobAnalysis,
    Recommendation,
    WeightConfig,
)
from src.services.screening_service import (
    build_recommendation,
    get_candidate_breakdown_chart_data,
    get_overall_ranking_chart_data,
    get_score_composition_chart_data,
    get_score_contributions,
    get_skill_matrix_chart_data,
)


def _make_candidate(
    candidate: str,
    rank: int,
    match_score: float,
    req_score: float = 1.0,
    pref_score: float = 1.0,
    sem_score: float = 0.8,
    exp_score: float = 1.0,
    matched_req: list[str] | None = None,
    matched_pref: list[str] | None = None,
    missing_req: list[str] | None = None,
    related_matched: list[str] | None = None,
    below_min_exp: bool = False,
) -> CandidateRanking:
    """Helper to construct CandidateRanking domain models for deterministic unit testing."""
    return CandidateRanking(
        rank=rank,
        candidate=candidate,
        match_score=match_score,
        component_scores=ComponentScores(
            required_skill_score=req_score,
            preferred_skill_score=pref_score,
            semantic_score=sem_score,
            experience_score=exp_score,
            tfidf_baseline_score=0.45,
        ),
        matched_skills=(matched_req or []) + (matched_pref or []),
        missing_skills=missing_req or [],
        matched_required_skills=matched_req or [],
        matched_preferred_skills=matched_pref or [],
        missing_required_skills=missing_req or [],
        related_skills_matched=related_matched or [],
        below_min_experience=below_min_exp,
    )


def test_build_recommendation_empty_list() -> None:
    """Verifies build_recommendation handles empty candidate lists gracefully."""
    rec = build_recommendation([])
    assert isinstance(rec, Recommendation)
    assert rec.best_candidate is None
    assert rec.best_score is None
    assert rec.runner_up is None
    assert rec.margin_over_runner_up is None
    assert len(rec.warnings) > 0
    assert "no resumes were evaluated" in rec.summary_text.lower()


def test_build_recommendation_single_candidate() -> None:
    """Verifies build_recommendation for a single candidate evaluation."""
    c1 = _make_candidate(
        candidate="Alice.pdf",
        rank=1,
        match_score=92.5,
        matched_req=["Python", "FastAPI"],
        matched_pref=["Docker"],
        missing_req=[],
    )
    job = JobAnalysis(raw_text="Job", required_skills=["Python", "FastAPI"], preferred_skills=["Docker"])
    rec = build_recommendation([c1], job=job)

    assert rec.best_candidate == "Alice.pdf"
    assert rec.best_score == 92.5
    assert rec.runner_up is None
    assert rec.margin_over_runner_up is None
    assert "sole candidate" in rec.summary_text.lower()
    assert any("Python" in s for s in rec.strengths)
    assert any("Docker" in s for s in rec.strengths)


def test_build_recommendation_normal_case() -> None:
    """Verifies build_recommendation identifies winner, runner-up, margin, strengths, and gaps."""
    c1 = _make_candidate(
        candidate="Alice.pdf",
        rank=1,
        match_score=88.0,
        matched_req=["Python", "FastAPI"],
        matched_pref=["Docker"],
        missing_req=["PostgreSQL"],
    )
    c2 = _make_candidate(
        candidate="Bob.docx",
        rank=2,
        match_score=75.0,
        matched_req=["Python"],
        missing_req=["FastAPI", "PostgreSQL"],
    )
    job = JobAnalysis(
        raw_text="Job",
        required_skills=["Python", "FastAPI", "PostgreSQL"],
        preferred_skills=["Docker"],
    )
    rec = build_recommendation([c1, c2], job=job)

    assert rec.best_candidate == "Alice.pdf"
    assert rec.best_score == 88.0
    assert rec.runner_up == "Bob.docx"
    assert rec.margin_over_runner_up == 13.0
    assert "Outperforms runner-up Bob.docx" in rec.summary_text
    # Strengths include matched skills and strongest component
    assert any("Python" in s and "FastAPI" in s for s in rec.strengths)
    assert any("Strongest scoring component" in s for s in rec.strengths)
    # Gaps include missing required skills
    assert any("PostgreSQL" in g for g in rec.gaps)


def test_build_recommendation_tied_scores() -> None:
    """Verifies build_recommendation handles tied scores between top candidates."""
    c1 = _make_candidate(candidate="Alice.pdf", rank=1, match_score=85.0)
    c2 = _make_candidate(candidate="Bob.docx", rank=2, match_score=85.0)
    rec = build_recommendation([c1, c2])

    assert rec.best_candidate == "Alice.pdf"
    assert rec.runner_up == "Bob.docx"
    assert rec.margin_over_runner_up == 0.0
    assert "Tied for top position with Bob.docx" in rec.summary_text


def test_build_recommendation_below_min_experience_winner() -> None:
    """Verifies warning is explicitly included when the winning candidate is below min experience."""
    c1 = _make_candidate(
        candidate="Junior_Whiz.pdf",
        rank=1,
        match_score=72.0,
        below_min_exp=True,
    )
    job = JobAnalysis(raw_text="Job", min_experience_years=5.0)
    rec = build_recommendation([c1], job=job)

    assert rec.best_candidate == "Junior_Whiz.pdf"
    assert any("Experience below minimum" in w for w in rec.warnings)
    assert "falls below the minimum required experience" in rec.summary_text


def test_build_recommendation_no_candidate_meets_all_required() -> None:
    """Verifies warning is triggered when no candidate in the cohort matches all required skills."""
    c1 = _make_candidate(candidate="C1.pdf", rank=1, match_score=60.0, missing_req=["Kubernetes"])
    c2 = _make_candidate(candidate="C2.pdf", rank=2, match_score=50.0, missing_req=["Kubernetes", "AWS"])
    job = JobAnalysis(raw_text="Job", required_skills=["Kubernetes", "AWS"])
    rec = build_recommendation([c1, c2], job=job)

    assert any("No candidate fully meets the requirements; best available match." in w for w in rec.warnings)


def test_weighted_contributions_sum_to_composite_score() -> None:
    """Verifies that 4-component weighted contributions sum exactly to match_score for both normal and penalized candidates."""
    weights = WeightConfig(
        required_skill_weight=0.5,
        preferred_skill_weight=0.2,
        semantic_weight=0.2,
        experience_weight=0.1,
        experience_penalty=0.6,
    )

    # Candidate 1: Standard unpenalized candidate
    c_normal = _make_candidate(
        candidate="Normal.pdf",
        rank=1,
        match_score=88.5,
        req_score=1.0,
        pref_score=0.8,
        sem_score=0.65,
        exp_score=0.95,
        below_min_exp=False,
    )
    contribs_normal = get_score_contributions(c_normal, weights)
    total_normal = (
        contribs_normal["required_skills"]
        + contribs_normal["preferred_skills"]
        + contribs_normal["semantic_similarity"]
        + contribs_normal["experience_match"]
    )
    assert math.isclose(total_normal, c_normal.match_score, abs_tol=0.01)
    assert contribs_normal["experience_penalty_applied"] == 1.0
    assert contribs_normal["penalty_deduction"] == 0.0

    # Candidate 2: Penalized candidate (below_min_experience=True)
    c_penalized = _make_candidate(
        candidate="Junior.pdf",
        rank=2,
        match_score=36.4,
        req_score=0.8,
        pref_score=0.5,
        sem_score=0.55,
        exp_score=0.60,
        below_min_exp=True,
    )
    contribs_penalized = get_score_contributions(c_penalized, weights)
    total_penalized = (
        contribs_penalized["required_skills"]
        + contribs_penalized["preferred_skills"]
        + contribs_penalized["semantic_similarity"]
        + contribs_penalized["experience_match"]
    )
    assert math.isclose(total_penalized, c_penalized.match_score, abs_tol=0.01)
    assert contribs_penalized["experience_penalty_applied"] == 0.6
    assert contribs_penalized["penalty_deduction"] > 0.0


def test_chart_data_helpers() -> None:
    """Verifies that service chart helpers format records correctly for Altair rendering."""
    c1 = _make_candidate(
        candidate="A.pdf",
        rank=1,
        match_score=90.0,
        matched_req=["Python"],
        matched_pref=["Docker"],
        missing_req=["FastAPI"],
        related_matched=["FastAPI (via Flask: 0.6)"],
    )
    c2 = _make_candidate(
        candidate="B.docx",
        rank=2,
        match_score=70.0,
        matched_req=["Python"],
        missing_req=["FastAPI"],
    )
    job = JobAnalysis(raw_text="Job", required_skills=["Python", "FastAPI"], preferred_skills=["Docker"])

    # 1. Overall ranking data
    overall = get_overall_ranking_chart_data([c1, c2])
    assert len(overall) == 2
    assert overall[0]["color_category"] == "Top Candidate"
    assert overall[1]["color_category"] == "Candidate"
    assert overall[0]["label"] == "90.0%"

    # 2. Score composition data (4 components per candidate = 8 records)
    comp = get_score_composition_chart_data([c1, c2])
    assert len(comp) == 8
    assert all("percentage_label" in r for r in comp)

    # 3. Skill match matrix
    matrix = get_skill_matrix_chart_data([c1, c2], job)
    assert len(matrix) == 6  # 2 candidates * 3 job skills
    statuses = {(r["candidate"], r["skill"]): r["status"] for r in matrix}
    assert statuses[("A.pdf", "Python")] == "Exact Match"
    assert statuses[("A.pdf", "FastAPI")] == "Related Match"
    assert statuses[("B.docx", "FastAPI")] == "Missing"

    # 4. Individual breakdown data (5 components)
    breakdown = get_candidate_breakdown_chart_data(c1)
    assert len(breakdown) == 5
    assert {b["component"] for b in breakdown} == {
        "Required Skills",
        "Preferred Skills",
        "Semantic Match",
        "Experience Match",
        "TF-IDF Baseline",
    }
