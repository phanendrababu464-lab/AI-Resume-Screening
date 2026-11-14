"""UI-free service layer for the AI-Based Resume Screening System.

Coordinates job parsing, resume ingestion, section splitting, skill extraction,
candidate anonymization, and 4-component weighted candidate ranking.
"""

from __future__ import annotations

import io
import json
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
    DEFAULT_EXPERIENCE_PENALTY,
    DEFAULT_EXPERIENCE_WEIGHT,
    DEFAULT_PREFERRED_SKILL_WEIGHT,
    DEFAULT_REQUIRED_SKILL_WEIGHT,
    DEFAULT_SEMANTIC_SIMILARITY_WEIGHT,
    EMBEDDING_MODEL_NAME,
    RELATED_SKILLS_FILE,
)
from src.job_parser import extract_min_experience_years, parse_job_description
from src.parser import extract_text, split_resume_sections
from src.preprocessor import clean_text
from src.schemas import (
    CandidateRanking,
    ComponentScores,
    JobAnalysis,
    ParsedResume,
    Recommendation,
    ResumeSections,
    ScreeningResult,
    WeightConfig,
)
from src.skill_extractor import TechnicalSkillExtractor

# Cached singleton instances for CPU inference efficiency
_SKILL_EXTRACTOR: Optional[TechnicalSkillExtractor] = None
_SENTENCE_MODEL: Optional[SentenceTransformer] = None
_RELATED_SKILLS_MAP: Optional[dict[str, dict[str, float]]] = None


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


def get_related_skills_map() -> dict[str, dict[str, float]]:
    """Loads and returns the cached related skills mapping dictionary."""
    global _RELATED_SKILLS_MAP
    if _RELATED_SKILLS_MAP is None:
        if RELATED_SKILLS_FILE.exists():
            try:
                with open(RELATED_SKILLS_FILE, "r", encoding="utf-8") as f:
                    _RELATED_SKILLS_MAP = json.load(f)
            except Exception:
                _RELATED_SKILLS_MAP = {}
        else:
            _RELATED_SKILLS_MAP = {}
    return _RELATED_SKILLS_MAP


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
    related_skills_map = get_related_skills_map()
    normalized_rel_map: dict[str, dict[str, float]] = {
        k.lower(): v for k, v in related_skills_map.items()
    }

    for i, pr in enumerate(parsed_resumes):
        c_text = cand_sem_texts[i]

        if not c_text:
            # Empty candidate text -> exact 0.0 across all components
            below_min = (
                job_obj.min_experience_years is not None
                and job_obj.min_experience_years > 0.0
            )
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
                    related_skills_matched=[],
                    below_min_experience=below_min,
                )
            )
            continue

        cand_skills_lower = {s.lower(): s for s in pr.skills}

        # Match required skills (case-insensitive lookup, preserve JD skill casing)
        matched_req = [s for s in req_skills_set if s.lower() in cand_skills_lower]
        missing_req = [s for s in req_skills_set if s.lower() not in cand_skills_lower]

        # Match preferred skills (case-insensitive lookup, preserve JD skill casing)
        matched_pref = [s for s in pref_skills_set if s.lower() in cand_skills_lower]
        missing_pref = [s for s in pref_skills_set if s.lower() not in cand_skills_lower]

        matched_skills = sorted(list(set(matched_req + matched_pref)))
        missing_skills = list(missing_req)

        # Related skills partial credit: unmatched skill earns highest credit from related skills in resume
        related_matches: list[str] = []
        req_related_credit = 0.0
        for s in missing_req:
            rel_dict = normalized_rel_map.get(s.lower(), {})
            best_rel_skill: Optional[str] = None
            best_weight: float = 0.0
            for rel_s, weight in rel_dict.items():
                if rel_s.lower() in cand_skills_lower and weight > best_weight:
                    best_weight = weight
                    best_rel_skill = cand_skills_lower[rel_s.lower()]
            if best_rel_skill is not None and best_weight > 0.0:
                req_related_credit += best_weight
                related_matches.append(f"{s} (via {best_rel_skill}: {best_weight})")

        pref_related_credit = 0.0
        for s in missing_pref:
            rel_dict = normalized_rel_map.get(s.lower(), {})
            best_rel_skill: Optional[str] = None
            best_weight: float = 0.0
            for rel_s, weight in rel_dict.items():
                if rel_s.lower() in cand_skills_lower and weight > best_weight:
                    best_weight = weight
                    best_rel_skill = cand_skills_lower[rel_s.lower()]
            if best_rel_skill is not None and best_weight > 0.0:
                pref_related_credit += best_weight
                related_matches.append(f"{s} (via {best_rel_skill}: {best_weight})")

        req_score = (len(matched_req) + req_related_credit) / len(req_skills_set) if req_skills_set else 0.0
        pref_score = (len(matched_pref) + pref_related_credit) / len(pref_skills_set) if pref_skills_set else 0.0
        req_score = min(1.0, max(0.0, req_score))
        pref_score = min(1.0, max(0.0, pref_score))

        sem_score = semantic_scores[i]

        # Experience score and minimum experience gate check
        if job_obj.min_experience_years is None or job_obj.min_experience_years <= 0.0:
            exp_score = 1.0
            below_min = False
        else:
            cand_exp = pr.experience_years or 0.0
            exp_score = min(1.0, max(0.0, cand_exp) / job_obj.min_experience_years)
            below_min = cand_exp < job_obj.min_experience_years

        # Composite score calculation (immunized against ZeroDivisionError)
        composite = (
            weight_cfg.required_skill_weight * req_score
            + weight_cfg.preferred_skill_weight * pref_score
            + weight_cfg.semantic_weight * sem_score
            + weight_cfg.experience_weight * exp_score
        )
        raw_score = composite * 100.0
        if below_min:
            raw_score = raw_score * weight_cfg.experience_penalty

        match_score = round(float(np.clip(raw_score, 0.0, 100.0)), 2)

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
                related_skills_matched=related_matches,
                below_min_experience=below_min,
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


def build_recommendation(
    rankings: list[CandidateRanking],
    job: Optional[JobAnalysis] = None,
) -> Recommendation:
    """Builds a deterministic candidate recommendation from evaluation results without LLM.

    Args:
        rankings: Sorted list of candidate rankings.
        job: Optional parsed JobAnalysis domain model.

    Returns:
        Structured Recommendation schema instance.
    """
    if not rankings:
        return Recommendation(
            best_candidate=None,
            best_score=None,
            runner_up=None,
            margin_over_runner_up=None,
            strengths=[],
            gaps=[],
            warnings=["No candidates were evaluated."],
            summary_text="No candidate recommendations available because no resumes were evaluated.",
        )

    top = rankings[0]
    best_candidate = top.candidate
    best_score = top.match_score

    # Runner-up and margin calculation
    if len(rankings) == 1:
        runner_up = None
        margin_over_runner_up = None
        comparison_text = f"{best_candidate} was the sole candidate evaluated."
    else:
        second = rankings[1]
        runner_up = second.candidate
        margin = round(top.match_score - second.match_score, 2)
        margin_over_runner_up = margin
        if margin == 0.0:
            comparison_text = f"Tied for top position with {runner_up} ({second.match_score:.1f}%)."
        else:
            comparison_text = f"Outperforms runner-up {runner_up} ({second.match_score:.1f}%) by a margin of {margin:.1f} percentage points."

    # Strengths
    strengths: list[str] = []
    if top.matched_required_skills:
        strengths.append(f"Matched required skills: {', '.join(top.matched_required_skills)}")
    if top.matched_preferred_skills:
        strengths.append(f"Matched preferred skills: {', '.join(top.matched_preferred_skills)}")

    comp_scores = {
        "Required Skills": top.component_scores.required_skill_score * 100.0,
        "Preferred Skills": top.component_scores.preferred_skill_score * 100.0,
        "Semantic Similarity": top.component_scores.semantic_score * 100.0,
        "Experience Match": top.component_scores.experience_score * 100.0,
    }
    strongest_name, strongest_val = max(comp_scores.items(), key=lambda item: item[1])
    strengths.append(f"Strongest scoring component: {strongest_name} ({strongest_val:.1f}%)")

    # Gaps
    gaps: list[str] = []
    if top.missing_required_skills:
        gaps.append(f"Missing required skills: {', '.join(top.missing_required_skills)}")
    else:
        gaps.append("None — possesses all mandatory required skills.")

    if top.related_skills_matched:
        gaps.append(f"Related skills receiving partial credit: {', '.join(top.related_skills_matched)}")

    # Warnings
    warnings: list[str] = []
    if top.below_min_experience:
        min_exp_note = f" (requires {job.min_experience_years:.1f}+ years)" if (job and job.min_experience_years) else ""
        warnings.append(f"Experience below minimum: Candidate experience does not meet the minimum requirement{min_exp_note}; composite score was penalized.")

    # Check if NO candidate matches all required skills
    has_reqs = bool(job and job.required_skills)
    no_candidate_fully_meets = all(bool(r.missing_required_skills) for r in rankings)
    if has_reqs and no_candidate_fully_meets:
        warnings.append("No candidate fully meets the requirements; best available match.")

    # Summary text
    summary_parts = [
        f"{best_candidate} is the recommended top candidate with a composite score of {best_score:.1f}%.",
        comparison_text,
    ]
    if top.matched_required_skills:
        total_reqs = len(job.required_skills) if job and job.required_skills else len(top.matched_required_skills)
        summary_parts.append(
            f"Demonstrates strong alignment matching {len(top.matched_required_skills)}/{total_reqs} required skills."
        )
    if top.below_min_experience:
        summary_parts.append("Note: Candidate falls below the minimum required experience.")
    summary_text = " ".join(summary_parts)

    return Recommendation(
        best_candidate=best_candidate,
        best_score=best_score,
        runner_up=runner_up,
        margin_over_runner_up=margin_over_runner_up,
        strengths=strengths,
        gaps=gaps,
        warnings=warnings,
        summary_text=summary_text,
    )


def get_score_contributions(
    candidate: CandidateRanking,
    weights: Optional[WeightConfig] = None,
) -> dict[str, float]:
    """Computes the weighted contribution of each component in percentage points.

    Scales components by the experience penalty if below_min_experience is True,
    ensuring the contributions sum exactly to candidate.match_score.
    """
    if weights is None:
        weights = WeightConfig()

    penalty = weights.experience_penalty if candidate.below_min_experience else 1.0

    raw_req = candidate.component_scores.required_skill_score * weights.required_skill_weight * 100.0
    raw_pref = candidate.component_scores.preferred_skill_score * weights.preferred_skill_weight * 100.0
    raw_sem = candidate.component_scores.semantic_score * weights.semantic_weight * 100.0
    raw_exp = candidate.component_scores.experience_score * weights.experience_weight * 100.0

    req_contrib = round(raw_req * penalty, 2)
    pref_contrib = round(raw_pref * penalty, 2)
    sem_contrib = round(raw_sem * penalty, 2)
    exp_contrib = round(raw_exp * penalty, 2)

    # Reconcile rounding discrepancy against candidate.match_score
    diff = round(candidate.match_score - (req_contrib + pref_contrib + sem_contrib + exp_contrib), 2)
    if abs(diff) > 0:
        components = [("required", req_contrib), ("preferred", pref_contrib), ("semantic", sem_contrib), ("experience", exp_contrib)]
        components.sort(key=lambda x: x[1], reverse=True)
        largest = components[0][0]
        if largest == "required":
            req_contrib = round(req_contrib + diff, 2)
        elif largest == "preferred":
            pref_contrib = round(pref_contrib + diff, 2)
        elif largest == "semantic":
            sem_contrib = round(sem_contrib + diff, 2)
        else:
            exp_contrib = round(exp_contrib + diff, 2)

    unpenalized_total = round(raw_req + raw_pref + raw_sem + raw_exp, 2)
    penalty_deduction = round(unpenalized_total - candidate.match_score, 2) if candidate.below_min_experience else 0.0

    return {
        "required_skills": req_contrib,
        "preferred_skills": pref_contrib,
        "semantic_similarity": sem_contrib,
        "experience_match": exp_contrib,
        "total_contribution": round(req_contrib + pref_contrib + sem_contrib + exp_contrib, 2),
        "composite_score": candidate.match_score,
        "experience_penalty_applied": penalty,
        "penalty_deduction": penalty_deduction,
    }


def get_overall_ranking_chart_data(rankings: list[CandidateRanking]) -> list[dict[str, Any]]:
    """Formats overall rankings into chart data records for Altair."""
    return [
        {
            "candidate": r.candidate,
            "score": r.match_score,
            "label": f"{r.match_score:.1f}%",
            "rank": r.rank,
            "color_category": "Top Candidate" if r.rank == 1 else "Candidate",
        }
        for r in rankings
    ]


def get_score_composition_chart_data(
    rankings: list[CandidateRanking],
    weights: Optional[WeightConfig] = None,
) -> list[dict[str, Any]]:
    """Formats 4-component weighted contributions into stacked chart data records."""
    if weights is None:
        weights = WeightConfig()

    records: list[dict[str, Any]] = []
    for r in rankings:
        contribs = get_score_contributions(r, weights)
        penalty_note = f" (Penalty: ×{contribs['experience_penalty_applied']:.2f})" if r.below_min_experience else ""

        records.append({
            "candidate": r.candidate,
            "component": "1. Required Skills",
            "contribution": contribs["required_skills"],
            "percentage_label": f"{contribs['required_skills']:.1f}%",
            "below_min_experience": r.below_min_experience,
            "penalty_note": penalty_note,
        })
        records.append({
            "candidate": r.candidate,
            "component": "2. Preferred Skills",
            "contribution": contribs["preferred_skills"],
            "percentage_label": f"{contribs['preferred_skills']:.1f}%",
            "below_min_experience": r.below_min_experience,
            "penalty_note": penalty_note,
        })
        records.append({
            "candidate": r.candidate,
            "component": "3. Semantic Match",
            "contribution": contribs["semantic_similarity"],
            "percentage_label": f"{contribs['semantic_similarity']:.1f}%",
            "below_min_experience": r.below_min_experience,
            "penalty_note": penalty_note,
        })
        records.append({
            "candidate": r.candidate,
            "component": "4. Experience Match",
            "contribution": contribs["experience_match"],
            "percentage_label": f"{contribs['experience_match']:.1f}%",
            "below_min_experience": r.below_min_experience,
            "penalty_note": penalty_note,
        })
    return records


def get_skill_matrix_chart_data(
    rankings: list[CandidateRanking],
    job: JobAnalysis,
) -> list[dict[str, Any]]:
    """Builds skill matrix records (candidates x skills) for heatmap/grid rendering."""
    skills_in_order: list[tuple[str, str]] = []
    for s in job.required_skills:
        skills_in_order.append((s, "Required"))
    for s in job.preferred_skills:
        if (s, "Required") not in skills_in_order:
            skills_in_order.append((s, "Preferred"))

    records: list[dict[str, Any]] = []
    for r in rankings:
        for s, skill_type in skills_in_order:
            if s in r.matched_required_skills or s in r.matched_preferred_skills:
                status = "Exact Match"
            elif any(s.lower() in rel.lower() for rel in r.related_skills_matched):
                status = "Related Match"
            else:
                status = "Missing"

            records.append({
                "candidate": r.candidate,
                "skill": s,
                "skill_type": skill_type,
                "skill_display": f"{s} ({skill_type[:3]})",
                "status": status,
            })
    return records


def get_candidate_breakdown_chart_data(candidate: CandidateRanking) -> list[dict[str, Any]]:
    """Formats individual candidate component percentages for horizontal bar rendering."""
    tfidf = candidate.component_scores.tfidf_baseline_score or 0.0
    return [
        {"component": "Required Skills", "percentage": round(candidate.component_scores.required_skill_score * 100.0, 1)},
        {"component": "Preferred Skills", "percentage": round(candidate.component_scores.preferred_skill_score * 100.0, 1)},
        {"component": "Semantic Match", "percentage": round(candidate.component_scores.semantic_score * 100.0, 1)},
        {"component": "Experience Match", "percentage": round(candidate.component_scores.experience_score * 100.0, 1)},
        {"component": "TF-IDF Baseline", "percentage": round(tfidf * 100.0, 1)},
    ]
