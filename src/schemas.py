"""Pydantic v2 schemas for the AI-Based Resume Screening System.

Defines domain contracts for job analysis, parsed resumes, candidate rankings,
scoring components, and configurable scoring weights.
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class JobAnalysis(BaseModel):
    """Structured representation of a parsed job description."""

    raw_text: str
    cleaned_text: str = ""
    job_title: Optional[str] = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    all_skills: list[str] = Field(default_factory=list)
    min_experience_years: Optional[float] = None
    has_multiple_jobs: bool = False
    multiple_jobs_warning: Optional[str] = None


class ResumeSections(BaseModel):
    """Standardized resume sections extracted from raw document text."""

    skills: str = ""
    experience: str = ""
    education: str = ""
    projects: str = ""
    other: str = ""


class ParsedResume(BaseModel):
    """Structured representation of an ingested and parsed candidate resume."""

    filename: str
    raw_text: str
    source_filename: str | None = None
    cleaned_text: str = ""
    sections: ResumeSections = Field(default_factory=ResumeSections)
    skills: list[str] = Field(default_factory=list)
    experience_years: Optional[float] = None
    anonymized_text: Optional[str] = None
    text_hash: Optional[str] = None
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None


class WeightConfig(BaseModel):
    """Configurable scoring weights for 4-component candidate ranking."""

    required_skill_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    preferred_skill_weight: float = Field(default=0.2, ge=0.0, le=1.0)
    semantic_weight: float = Field(default=0.2, ge=0.0, le=1.0)
    experience_weight: float = Field(default=0.1, ge=0.0, le=1.0)
    skill_weight: float | None = Field(default=None, ge=0, le=1)
    keyword_weight: float = Field(default=0.2, ge=0, le=1)
    experience_penalty: float = Field(default=0.6, ge=0.0, le=1.0)
    renormalize_weights: bool = Field(default=True)


class ComponentScores(BaseModel):
    """Individual breakdown scores comprising the composite ranking."""

    required_skill_score: Optional[float] = None
    preferred_skill_score: Optional[float] = None
    semantic_score: float = 0.0
    experience_score: Optional[float] = None
    skill_score: float | None = None
    tfidf_baseline_score: Optional[float] = None


class CandidateRanking(BaseModel):
    """Evaluated ranking output for a candidate against a job description."""

    rank: int
    candidate_id: str = ""
    resume_filename: str | None = None
    candidate_name: str | None = None
    detected_skills: list[str] = Field(default_factory=list)
    experience_years: float | None = None
    rank_display: str = ""
    candidate: str
    match_score: float
    component_scores: ComponentScores
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    matched_required_skills: list[str] = Field(default_factory=list)
    matched_preferred_skills: list[str] = Field(default_factory=list)
    missing_required_skills: list[str] = Field(default_factory=list)
    related_skills_matched: list[str] = Field(default_factory=list)
    below_min_experience: bool = False
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None
    text_hash: Optional[str] = None
    resume_snippet: Optional[str] = ""


class ScreeningResult(BaseModel):
    """Container aggregating the job analysis and all ranked candidates."""

    job: JobAnalysis
    rankings: list[CandidateRanking] = Field(default_factory=list)
    total_resumes: int = 0
    effective_weights: dict[str, float] = Field(default_factory=dict)
    non_applicable_components: list[str] = Field(default_factory=list)
    weight_redistribution_note: Optional[str] = None


class Recommendation(BaseModel):
    """Deterministic candidate recommendation summary for the top match."""

    best_candidate: Optional[str] = None
    best_score: Optional[float] = None
    runner_up: Optional[str] = None
    runner_up_score: Optional[float] = None
    margin_over_runner_up: Optional[float] = None
    missing_skills: list[str] = Field(default_factory=list)
    is_tie: bool = False
    tied_candidates: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    summary_text: str = ""
