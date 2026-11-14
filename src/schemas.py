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
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    all_skills: list[str] = Field(default_factory=list)
    min_experience_years: Optional[float] = None


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
    cleaned_text: str = ""
    sections: ResumeSections = Field(default_factory=ResumeSections)
    skills: list[str] = Field(default_factory=list)
    experience_years: Optional[float] = None
    anonymized_text: Optional[str] = None


class WeightConfig(BaseModel):
    """Configurable scoring weights for 4-component candidate ranking."""

    required_skill_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    preferred_skill_weight: float = Field(default=0.2, ge=0.0, le=1.0)
    semantic_weight: float = Field(default=0.2, ge=0.0, le=1.0)
    experience_weight: float = Field(default=0.1, ge=0.0, le=1.0)


class ComponentScores(BaseModel):
    """Individual breakdown scores comprising the composite ranking."""

    required_skill_score: float = 0.0
    preferred_skill_score: float = 0.0
    semantic_score: float = 0.0
    experience_score: float = 0.0
    tfidf_baseline_score: Optional[float] = None


class CandidateRanking(BaseModel):
    """Evaluated ranking output for a candidate against a job description."""

    rank: int
    candidate: str
    match_score: float
    component_scores: ComponentScores
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    matched_required_skills: list[str] = Field(default_factory=list)
    matched_preferred_skills: list[str] = Field(default_factory=list)
    missing_required_skills: list[str] = Field(default_factory=list)


class ScreeningResult(BaseModel):
    """Container aggregating the job analysis and all ranked candidates."""

    job: JobAnalysis
    rankings: list[CandidateRanking] = Field(default_factory=list)
    total_resumes: int = 0
