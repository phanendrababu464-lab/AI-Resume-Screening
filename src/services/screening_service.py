"""UI-free service layer for the AI-Based Resume Screening System.

Coordinates job parsing, resume ingestion, section splitting, skill extraction,
candidate anonymization, and 4-component weighted candidate ranking.
"""

from __future__ import annotations

import io
from pathlib import Path
import re
from typing import Any, BinaryIO, Optional, Union

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.anonymizer import anonymize_text
from src.config import (
    DEFAULT_DEVICE,
    DEFAULT_EXPERIENCE_WEIGHT,
    DEFAULT_PREFERRED_SKILL_WEIGHT,
    DEFAULT_REQUIRED_SKILL_WEIGHT,
    DEFAULT_SEMANTIC_SIMILARITY_WEIGHT,
    EMBEDDING_MODEL_NAME,
)
from src.job_parser import extract_min_experience_years, parse_job_description
from src.parser import extract_text, split_resume_sections
from src.preprocessor import clean_text
from src.schemas import (
    CandidateRanking,
    ComponentScores,
    JobAnalysis,
    ParsedResume,
    ResumeSections,
    ScreeningResult,
    WeightConfig,
)
from src.skill_extractor import TechnicalSkillExtractor

# Cached singleton instances for CPU inference efficiency
_SKILL_EXTRACTOR: Optional[TechnicalSkillExtractor] = None
_SENTENCE_MODEL: Optional[SentenceTransformer] = None


def get_skill_extractor() -> TechnicalSkillExtractor:
    """Returns a cached singleton instance of TechnicalSkillExtractor."""
    global _SKILL_EXTRACTOR
    if _SKILL_EXTRACTOR is None:
        _SKILL_EXTRACTOR = TechnicalSkillExtractor()
    return _SKILL_EXTRACTOR


def get_sentence_model() -> SentenceTransformer:
    """Returns a cached singleton instance of SentenceTransformer on CPU."""
    global _SENTENCE_MODEL
    if _SENTENCE_MODEL is None:
        _SENTENCE_MODEL = SentenceTransformer(EMBEDDING_MODEL_NAME, device=DEFAULT_DEVICE)
    return _SENTENCE_MODEL


RESUME_EXP_PATTERNS = [
    r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\b(?:\s+of)?(?:\s+[a-z]+)*\s+experience(?!\s+(?:old|of\s+age)\b)",
    r"(?:past|last)\s+(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\b",
    r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\b\s+(?:as|in|building|developing|administering|managing|statistical|software|working|leading|engineering|architecting|creating|designing|specializing|programming)\b",
    r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\b\s+experience",
    r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\b(?!\s+(?:old|of\s+age)\b)",
]


def extract_candidate_experience_years(text: str) -> Optional[float]:
    """Extracts candidate years of professional experience from resume text."""
    if not text or not isinstance(text, str):
        return None
    for pat in RESUME_EXP_PATTERNS:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except (ValueError, IndexError):
                continue
    return extract_min_experience_years(text)


def analyze_job(text: str) -> JobAnalysis:
    """Parses a job description to extract required/preferred skills and experience.

    Args:
        text: Raw text of the target job description.

    Returns:
        Structured JobAnalysis schema instance.
    """
    if not text or not isinstance(text, str) or not text.strip():
        return JobAnalysis(
            raw_text=text or "",
            cleaned_text="",
            required_skills=[],
            preferred_skills=[],
            all_skills=[],
            min_experience_years=None,
        )

    parsed = parse_job_description(text)
    cleaned = clean_text(text)
    return JobAnalysis(
        raw_text=text,
        cleaned_text=cleaned,
        required_skills=parsed.get("required_skills", []),
        preferred_skills=parsed.get("preferred_skills", []),
        all_skills=parsed.get("all_skills", []),
        min_experience_years=parsed.get("min_experience_years"),
    )


def parse_resumes(
    files: list[Union[str, Path, BinaryIO, io.BytesIO, Any]]
) -> list[ParsedResume]:
    """Ingests and parses resume files or streams into structured ParsedResume models.

    Args:
        files: List of file paths or binary stream objects (e.g. UploadedFile).

    Returns:
        List of structured ParsedResume instances.

    Raises:
        ValueError: If any file cannot be read, parsed, or has an unsupported format.
    """
    if not files:
        return []

    extractor = get_skill_extractor()
    results: list[ParsedResume] = []

    for f in files:
        filename = "resume.pdf"
        if isinstance(f, (str, Path)):
            filename = Path(f).name
        elif hasattr(f, "name") and getattr(f, "name"):
            filename = str(getattr(f, "name"))

        # Text extraction (propagates ValueError on corrupt streams/unsupported types)
        if isinstance(f, (str, Path)):
            raw_text = extract_text(f)
        else:
            if hasattr(f, "seek"):
                f.seek(0)
            raw_text = extract_text(f, filename=filename)

        cleaned = clean_text(raw_text)
        sections_dict = split_resume_sections(raw_text)
        sections = ResumeSections(**sections_dict)
        skills = extractor.extract_skills(cleaned)

        # Experience extraction from experience section first, fallback to raw text
        exp_years = extract_candidate_experience_years(sections.experience)
        if exp_years is None:
            exp_years = extract_candidate_experience_years(raw_text)

        anonymized = anonymize_text(raw_text)

        results.append(
            ParsedResume(
                filename=filename,
                raw_text=raw_text,
                cleaned_text=cleaned,
                sections=sections,
                skills=skills,
                experience_years=exp_years,
                anonymized_text=anonymized,
            )
        )

    return results


def rank(
    job: Union[JobAnalysis, str, dict[str, Any]],
    resumes: list[Union[ParsedResume, dict[str, Any]]],
    weights: Optional[Union[WeightConfig, dict[str, Any]]] = None,
) -> list[CandidateRanking]:
    """Ranks candidates using 4-component weighted scoring and TF-IDF baseline.

    Args:
        job: Target job description as JobAnalysis, plain text string, or dictionary.
        resumes: List of ParsedResume instances or dictionaries.
        weights: Optional scoring weights configuration (defaults to WeightConfig defaults).

    Returns:
        List of CandidateRanking instances sorted in descending order by match_score.
    """
    if not resumes:
        return []

    # 1. Normalize JobAnalysis
    if isinstance(job, str):
        job_obj = analyze_job(job)
    elif isinstance(job, dict):
        job_obj = JobAnalysis(**job)
    else:
        job_obj = job

    # 2. Normalize WeightConfig
    if weights is None:
        weight_cfg = WeightConfig()
    elif isinstance(weights, dict):
        weight_cfg = WeightConfig(**weights)
    else:
        weight_cfg = weights

    # 3. Normalize Resumes
    parsed_resumes: list[ParsedResume] = []
    for r in resumes:
        if isinstance(r, dict):
            d = dict(r)
            if "filename" not in d and "name" in d:
                d["filename"] = d["name"]
            if "raw_text" not in d and "text" in d:
                d["raw_text"] = d["text"]
            parsed_resumes.append(ParsedResume(**d))
        else:
            parsed_resumes.append(r)

    extractor = get_skill_extractor()
    model = get_sentence_model()

    # Dynamic extraction fallback if candidate skills or experience were omitted
    for pr in parsed_resumes:
        if not pr.anonymized_text and pr.raw_text.strip():
            pr.anonymized_text = anonymize_text(pr.raw_text)
        if not pr.skills and (pr.cleaned_text.strip() or pr.raw_text.strip()):
            src_t = pr.cleaned_text if pr.cleaned_text.strip() else pr.raw_text
            pr.skills = extractor.extract_skills(src_t)
        if pr.experience_years is None:
            src_t = pr.cleaned_text if pr.cleaned_text.strip() else pr.raw_text
            if src_t:
                pr.experience_years = extract_candidate_experience_years(src_t)

    # 4. Text preparation for semantic similarity & TF-IDF
    jd_sem_text = job_obj.cleaned_text if job_obj.cleaned_text.strip() else job_obj.raw_text
    cand_sem_texts: list[str] = []
    for pr in parsed_resumes:
        t = (
            pr.anonymized_text.strip()
            if pr.anonymized_text and pr.anonymized_text.strip()
            else (pr.cleaned_text.strip() if pr.cleaned_text.strip() else pr.raw_text.strip())
        )
        cand_sem_texts.append(t.strip())

    # 5. Semantic Similarity via SentenceTransformer
    semantic_scores = [0.0] * len(parsed_resumes)
    if jd_sem_text.strip():
        valid_indices = [i for i, t in enumerate(cand_sem_texts) if t]
        if valid_indices:
            valid_texts = [cand_sem_texts[i] for i in valid_indices]
            all_embs = model.encode([jd_sem_text] + valid_texts, convert_to_numpy=True, show_progress_bar=False)
            jd_emb = np.atleast_2d(all_embs[0])
            cand_embs = np.atleast_2d(all_embs[1:])
            sims = cosine_similarity(jd_emb, cand_embs)[0]
            for idx, orig_i in enumerate(valid_indices):
                semantic_scores[orig_i] = float(np.clip(sims[idx], 0.0, 1.0))

    # 6. TF-IDF Baseline Computation
    tfidf_scores = [0.0] * len(parsed_resumes)
    if jd_sem_text.strip():
        valid_indices = [i for i, t in enumerate(cand_sem_texts) if t]
        if valid_indices:
            corpus = [jd_sem_text] + [cand_sem_texts[i] for i in valid_indices]
            mat = None
            try:
                vec = TfidfVectorizer(stop_words="english")
                mat = vec.fit_transform(corpus)
            except ValueError:
                try:
                    vec = TfidfVectorizer()
                    mat = vec.fit_transform(corpus)
                except ValueError:
                    mat = None
            if mat is not None and mat.shape[0] > 1:
                t_sims = cosine_similarity(mat[0:1], mat[1:])[0]
                for idx, orig_i in enumerate(valid_indices):
                    tfidf_scores[orig_i] = round(float(np.clip(t_sims[idx], 0.0, 1.0)), 4)

    # 7. Scoring Each Candidate
    rankings: list[CandidateRanking] = []
    req_skills_set = job_obj.required_skills
    pref_skills_set = job_obj.preferred_skills

    for i, pr in enumerate(parsed_resumes):
        c_text = cand_sem_texts[i]

        if not c_text:
            # Empty candidate text -> exact 0.0 across all components
            comp = ComponentScores(
                required_skill_score=0.0,
                preferred_skill_score=0.0,
                semantic_score=0.0,
                experience_score=0.0,
                tfidf_baseline_score=0.0,
            )
            rankings.append(
                CandidateRanking(
                    rank=1,
                    candidate=pr.filename,
                    match_score=0.0,
                    component_scores=comp,
                    matched_skills=[],
                    missing_skills=list(req_skills_set),
                    matched_required_skills=[],
                    matched_preferred_skills=[],
                    missing_required_skills=list(req_skills_set),
                )
            )
            continue

        cand_skills_lower = {s.lower(): s for s in pr.skills}

        # Match required skills (case-insensitive lookup, preserve JD skill casing)
        matched_req = [s for s in req_skills_set if s.lower() in cand_skills_lower]
        missing_req = [s for s in req_skills_set if s.lower() not in cand_skills_lower]

        # Match preferred skills (case-insensitive lookup, preserve JD skill casing)
        matched_pref = [s for s in pref_skills_set if s.lower() in cand_skills_lower]

        matched_skills = sorted(list(set(matched_req + matched_pref)))
        missing_skills = list(missing_req)

        req_score = len(matched_req) / len(req_skills_set) if req_skills_set else 0.0
        pref_score = len(matched_pref) / len(pref_skills_set) if pref_skills_set else 0.0
        sem_score = semantic_scores[i]

        # Experience score
        if job_obj.min_experience_years is None or job_obj.min_experience_years <= 0.0:
            exp_score = 1.0
        else:
            cand_exp = pr.experience_years or 0.0
            exp_score = min(1.0, max(0.0, cand_exp) / job_obj.min_experience_years)

        # Composite score calculation (immunized against ZeroDivisionError)
        composite = (
            weight_cfg.required_skill_weight * req_score
            + weight_cfg.preferred_skill_weight * pref_score
            + weight_cfg.semantic_weight * sem_score
            + weight_cfg.experience_weight * exp_score
        )
        match_score = round(float(np.clip(composite * 100.0, 0.0, 100.0)), 2)

        comp = ComponentScores(
            required_skill_score=round(req_score, 4),
            preferred_skill_score=round(pref_score, 4),
            semantic_score=round(sem_score, 4),
            experience_score=round(exp_score, 4),
            tfidf_baseline_score=tfidf_scores[i],
        )

        rankings.append(
            CandidateRanking(
                rank=1,
                candidate=pr.filename,
                match_score=match_score,
                component_scores=comp,
                matched_skills=matched_skills,
                missing_skills=missing_skills,
                matched_required_skills=matched_req,
                matched_preferred_skills=matched_pref,
                missing_required_skills=missing_req,
            )
        )

    # Sort descending by match_score
    rankings.sort(key=lambda r: r.match_score, reverse=True)
    for rank_idx, r in enumerate(rankings, start=1):
        r.rank = rank_idx

    return rankings


def screen(
    job: Union[JobAnalysis, str],
    files: list[Union[str, Path, BinaryIO, io.BytesIO, Any]],
    weights: Optional[Union[WeightConfig, dict[str, Any]]] = None,
) -> ScreeningResult:
    """Convenience pipeline function parsing job, ingesting resumes, and ranking candidates.

    Args:
        job: Target job description as JobAnalysis or string.
        files: List of file paths or file streams.
        weights: Optional scoring weights configuration.

    Returns:
        ScreeningResult containing job analysis, candidate rankings, and total count.
    """
    if isinstance(job, str):
        job_obj = analyze_job(job)
    else:
        job_obj = job

    parsed_resumes = parse_resumes(files)
    rankings = rank(job=job_obj, resumes=parsed_resumes, weights=weights)
    return ScreeningResult(
        job=job_obj,
        rankings=rankings,
        total_resumes=len(parsed_resumes),
    )
