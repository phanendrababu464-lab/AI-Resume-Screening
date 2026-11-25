"""UI-free service layer for the AI-Based Resume Screening System.

Coordinates job parsing, resume ingestion, section splitting, skill extraction,
candidate anonymization, and 4-component weighted candidate ranking.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import re
from typing import Any, BinaryIO, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

from src.anonymizer import anonymize_text
from src.config import (
    DEFAULT_DEVICE,
    DEFAULT_EXPERIENCE_PENALTY,
    DEFAULT_EXPERIENCE_WEIGHT,
    DEFAULT_PREFERRED_SKILL_WEIGHT,
    DEFAULT_RENORMALIZE_WEIGHTS,
    DEFAULT_REQUIRED_SKILL_WEIGHT,
    DEFAULT_SEMANTIC_SIMILARITY_WEIGHT,
    TFIDF_MAX_NGRAM,
    RELATED_SKILLS_FILE,
)
from src.job_parser import extract_min_experience_years, get_skill_extractor, parse_job_description
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


def verify_schemas_path(repo_root: Path, schemas_file: Path) -> bool:
    """Verifies that schemas.py is loaded from inside repo_root."""
    try:
        schemas_file.resolve().relative_to(repo_root.resolve())
        return True
    except ValueError:
        return False

# Cached singleton instances for CPU inference efficiency
_SENTENCE_MODEL: Optional[SentenceTransformer] = None
_RELATED_SKILLS_MAP: Optional[dict[str, dict[str, float]]] = None


def get_sentence_model() -> SentenceTransformer:
    """Returns a cached singleton instance of SentenceTransformer on CPU."""
    global _SENTENCE_MODEL
    if _SENTENCE_MODEL is None:
        from src.warm_cache import ensure_embedding_snapshot

        model_path = ensure_embedding_snapshot()
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        import torch
        from sentence_transformers import SentenceTransformer

        torch.set_num_threads(int(os.getenv("OMP_NUM_THREADS", "1")))
        _SENTENCE_MODEL = SentenceTransformer(
            model_path, device=DEFAULT_DEVICE, local_files_only=True, trust_remote_code=False,
        )
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


def compute_text_hash(text: str) -> str:
    """Computes a normalized SHA-256 hash of plain text to detect duplicate documents."""
    normalized = " ".join(text.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


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


def extract_evidenced_experience(text: str) -> float | None:
    """Accept explicit experience statements and ignore standalone durations."""
    match = re.search(
        r"(?<![\d.])(\d{1,2}(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)"
        r"\s+(?:of\s+)?(?:(?:professional|relevant|technical|work|hands-on)\s+)?experience\b",
        text, re.IGNORECASE,
    )
    return float(match.group(1)) if match and float(match.group(1)) <= 60 else None


def analyze_job(text: str) -> JobAnalysis:
    """Parses a job description to extract required/preferred skills, experience, and multi-job warnings.

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
            has_multiple_jobs=False,
            multiple_jobs_warning=None,
        )

    parsed = parse_job_description(text)
    cleaned = clean_text(text)

    # Extract job title if present
    job_title = None
    for line in text.splitlines():
        line_clean = line.strip()
        if line_clean.lower().startswith("job title:"):
            job_title = line_clean.split(":", 1)[1].strip()
            break
        elif line_clean and not job_title and len(line_clean) < 60:
            job_title = line_clean

    return JobAnalysis(
        raw_text=text,
        cleaned_text=cleaned,
        job_title=job_title,
        required_skills=parsed.get("required_skills", []),
        preferred_skills=parsed.get("preferred_skills", []),
        all_skills=parsed.get("all_skills", []),
        min_experience_years=parsed.get("min_experience_years"),
        has_multiple_jobs=parsed.get("has_multiple_jobs", False),
        multiple_jobs_warning=parsed.get("multiple_jobs_warning"),
    )


def parse_resumes(
    files: list[Union[str, Path, BinaryIO, io.BytesIO, Any]]
) -> list[ParsedResume]:
    """Ingests and parses resume files or streams into structured ParsedResume models.

    Detects duplicate documents via normalized text hashing.

    Args:
        files: List of file paths or binary stream objects (e.g. UploadedFile).

    Returns:
        List of structured ParsedResume instances.

    Raises:
        ValueError: If any file cannot be read, parsed, or has an unsupported format.
    """
    if not files:
        return []

    from src.parser import extract_text, split_resume_sections

    extractor = get_skill_extractor()
    results: list[ParsedResume] = []
    seen_hashes: dict[str, str] = {}

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

        # Duplicate detection by text hash
        t_hash = compute_text_hash(raw_text) if raw_text.strip() else None
        if t_hash and t_hash in seen_hashes:
            is_dup = True
            dup_of = seen_hashes[t_hash]
        else:
            is_dup = False
            dup_of = None
            if t_hash:
                seen_hashes[t_hash] = filename

        results.append(
            ParsedResume(
                filename=filename,
                raw_text=raw_text,
                cleaned_text=cleaned,
                sections=sections,
                skills=skills,
                experience_years=exp_years,
                anonymized_text=anonymized,
                text_hash=t_hash,
                is_duplicate=is_dup,
                duplicate_of=dup_of,
            )
        )

    return results


def get_applicable_components(
    job: JobAnalysis,
    weights: WeightConfig,
) -> tuple[list[str], list[str], dict[str, float], Optional[str]]:
    """Determines applicable scoring components and rescales weights when enabled.

    Applicable components:
    - required: if the job has required skills
    - preferred: if the job has preferred skills
    - experience: if the job states a minimum years
    - semantic: always applicable

    Returns:
        (applicable_list, non_applicable_list, effective_weights_dict, redistribution_note)
    """
    if weights.skill_weight is not None:
        factors = {
            "semantic": weights.semantic_weight,
            "keyword": weights.keyword_weight,
            "skills": weights.skill_weight,
            "experience": weights.experience_weight,
        }
        missing = []
        if not (job.required_skills or job.preferred_skills):
            missing.append("skills")
        if not job.min_experience_years:
            missing.append("experience")
        note = "Unspecified criteria contribute zero points." if missing else None
        return list(factors), missing, factors, note

    applicable: list[str] = []
    if job.required_skills:
        applicable.append("required")
    if job.preferred_skills:
        applicable.append("preferred")
    if job.min_experience_years is not None and job.min_experience_years > 0.0:
        applicable.append("experience")
    applicable.append("semantic")  # semantic is always applicable

    all_components = ["required", "preferred", "semantic", "experience"]
    non_applicable = [c for c in ["required", "preferred", "experience"] if c not in applicable]

    user_weights = {
        "required": weights.required_skill_weight,
        "preferred": weights.preferred_skill_weight,
        "semantic": weights.semantic_weight,
        "experience": weights.experience_weight,
    }

    if weights.renormalize_weights:
        s = sum(user_weights[c] for c in applicable)
        if s > 0:
            effective_weights = {
                c: (round(user_weights[c] / s, 4) if c in applicable else 0.0)
                for c in user_weights
            }
            # Reconcile rounding discrepancy on largest applicable component
            diff = round(1.0 - sum(effective_weights[c] for c in applicable), 4)
            if abs(diff) > 0 and applicable:
                largest = max(applicable, key=lambda c: effective_weights[c])
                effective_weights[largest] = round(effective_weights[largest] + diff, 4)
        else:
            effective_weights = {c: 0.0 for c in user_weights}
    else:
        effective_weights = dict(user_weights)

    # Note generation
    note: Optional[str] = None
    if non_applicable and weights.renormalize_weights:
        name_map = {
            "required": "Required skills",
            "preferred": "Preferred skills",
            "experience": "Minimum experience",
        }
        parts = [name_map[c] for c in non_applicable if c in name_map]
        if len(parts) == 1:
            note = f"{parts[0]} was not specified, so its weight was redistributed across the applicable components."
        elif len(parts) > 1:
            note = f"{' and '.join(parts)} were not specified, so their weights were redistributed across the applicable components."

    return applicable, non_applicable, effective_weights, note


def rank(
    job: Union[JobAnalysis, str, dict[str, Any]],
    resumes: list[Union[ParsedResume, dict[str, Any]]],
    weights: Optional[Union[WeightConfig, dict[str, Any]]] = None,
) -> list[CandidateRanking]:
    """Ranks candidates using 4-component weighted scoring and TF-IDF baseline.

    When weights.renormalize_weights is True, rescales weights across applicable
    components only, and assigns None ("N/A") to non-applicable components.
    Candidates with identical match scores receive competition tie ranks (e.g. 'T-2').

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

    # Determine applicable components and effective weights
    app_components, non_app_components, eff_weights, _ = get_applicable_components(job_obj, weight_cfg)

    # 3. Normalize Resumes
    parsed_resumes: list[ParsedResume] = []
    seen_hashes: dict[str, str] = {}
    for r in resumes:
        if isinstance(r, dict):
            d = dict(r)
            if "filename" not in d and "name" in d:
                d["filename"] = d["name"]
            if "raw_text" not in d and "text" in d:
                d["raw_text"] = d["text"]
            pr_item = ParsedResume(**d)
        else:
            pr_item = r

        if not pr_item.text_hash and pr_item.raw_text.strip():
            pr_item.text_hash = compute_text_hash(pr_item.raw_text)

        if pr_item.text_hash:
            if pr_item.text_hash in seen_hashes:
                pr_item.is_duplicate = True
                pr_item.duplicate_of = seen_hashes[pr_item.text_hash]
            else:
                seen_hashes[pr_item.text_hash] = pr_item.filename

        parsed_resumes.append(pr_item)

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

    if weight_cfg.skill_weight is not None:
        for pr in parsed_resumes:
            pr.experience_years = extract_evidenced_experience(pr.sections.experience or pr.raw_text)

    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

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
            valid_texts = [cand_sem_texts[i][:24000] for i in valid_indices]
            all_embs = model.encode(
                [jd_sem_text] + valid_texts, batch_size=4, convert_to_numpy=True, show_progress_bar=False,
            )
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
                vec = TfidfVectorizer(stop_words="english", ngram_range=(1, TFIDF_MAX_NGRAM))
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
            # Empty candidate text -> exact 0.0 across all applicable components
            below_min = (
                "experience" in app_components
                and job_obj.min_experience_years is not None
                and job_obj.min_experience_years > 0.0
            )
            comp = ComponentScores(
                required_skill_score=0.0 if "required" in app_components or not weight_cfg.renormalize_weights else None,
                preferred_skill_score=0.0 if "preferred" in app_components or not weight_cfg.renormalize_weights else None,
                semantic_score=0.0,
                experience_score=0.0 if "experience" in app_components or not weight_cfg.renormalize_weights else None,
                tfidf_baseline_score=0.0,
            )
            rankings.append(
                CandidateRanking(
                    rank=1,
                    rank_display="1",
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
                    is_duplicate=pr.is_duplicate,
                    duplicate_of=pr.duplicate_of,
                    text_hash=pr.text_hash,
                    resume_snippet=(pr.anonymized_text or "")[:4000] if weight_cfg.skill_weight is not None else (pr.cleaned_text or pr.raw_text or "")[:4000],
                )
            )
            continue

        if weight_cfg.skill_weight is not None:
            known = {skill.casefold() for skill in pr.skills}
            explicit = [skill for skill in req_skills_set + pref_skills_set if skill.casefold() not in known and skill.casefold() not in extractor.lookup]
            pr.skills = sorted(set(pr.skills + [
                skill for skill in explicit
                if re.search(r"(?<![\w.+#-])" + re.escape(skill) + r"(?![\w+#-]|\.\w)", c_text, re.IGNORECASE)
            ]))
        cand_skills_lower = {s.lower(): s for s in pr.skills}

        # Match required skills
        matched_req = [s for s in req_skills_set if s.lower() in cand_skills_lower]
        missing_req = [s for s in req_skills_set if s.lower() not in cand_skills_lower]

        # Match preferred skills
        matched_pref = [s for s in pref_skills_set if s.lower() in cand_skills_lower]
        missing_pref = [s for s in pref_skills_set if s.lower() not in cand_skills_lower]

        matched_skills = sorted(list(set(matched_req + matched_pref)))
        missing_skills = list(missing_req)

        # Related skills partial credit
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

        # Determine scores per component based on applicability
        if "required" in app_components:
            req_score: Optional[float] = (len(matched_req) + req_related_credit) / len(req_skills_set) if req_skills_set else 0.0
            req_score = min(1.0, max(0.0, req_score))
            req_score_rounded: Optional[float] = round(req_score, 4)
        else:
            if weight_cfg.renormalize_weights:
                req_score = None
                req_score_rounded = None
            else:
                req_score = 0.0
                req_score_rounded = 0.0

        if "preferred" in app_components:
            pref_score: Optional[float] = (len(matched_pref) + pref_related_credit) / len(pref_skills_set) if pref_skills_set else 0.0
            pref_score = min(1.0, max(0.0, pref_score))
            pref_score_rounded: Optional[float] = round(pref_score, 4)
        else:
            if weight_cfg.renormalize_weights:
                pref_score = None
                pref_score_rounded = None
            else:
                pref_score = 0.0
                pref_score_rounded = 0.0

        sem_score = semantic_scores[i]
        sem_score_rounded = round(sem_score, 4)

        if job_obj.min_experience_years and "experience" in app_components:
            cand_exp = pr.experience_years or 0.0
            exp_score: Optional[float] = min(1.0, max(0.0, cand_exp / job_obj.min_experience_years))
            exp_score_rounded: Optional[float] = round(exp_score, 4)
            below_min = cand_exp < job_obj.min_experience_years
        else:
            if weight_cfg.renormalize_weights:
                exp_score = None
                exp_score_rounded = None
                below_min = False
            else:
                exp_score = 1.0
                exp_score_rounded = 1.0
                below_min = False

        if weight_cfg.skill_weight is not None:
            skill_scores = [(score, importance) for score, importance in (
                (req_score if req_skills_set else None, 0.8),
                (pref_score if pref_skills_set else None, 0.2),
            ) if score is not None]
            skill_score = sum(score * w for score, w in skill_scores) / sum(
                w for _, w in skill_scores
            ) if skill_scores else None
            exp_score = exp_score if pr.experience_years is not None and job_obj.min_experience_years else None
            below_min = exp_score is not None and exp_score < 1
            composite = (
                sem_score * eff_weights["semantic"]
                + tfidf_scores[i] * eff_weights["keyword"]
                + (skill_score or 0) * eff_weights["skills"]
                + (exp_score or 0) * eff_weights["experience"]
            )
        else:
            skill_score = None
            composite = sum(
                weight * (score or 0) for weight, score in (
                    (eff_weights["required"], req_score),
                    (eff_weights["preferred"], pref_score),
                    (eff_weights["semantic"], sem_score),
                    (eff_weights["experience"], exp_score),
                )
            )

        raw_score = composite * 100.0
        if below_min and weight_cfg.skill_weight is None:
            raw_score *= weight_cfg.experience_penalty

        match_score = round(float(np.clip(raw_score, 0.0, 100.0)), 2)

        comp = ComponentScores(
            required_skill_score=req_score_rounded if req_skills_set or weight_cfg.skill_weight is None else None,
            preferred_skill_score=pref_score_rounded if pref_skills_set or weight_cfg.skill_weight is None else None,
            semantic_score=sem_score_rounded,
            skill_score=round(skill_score, 4) if skill_score is not None else None,
            experience_score=round(exp_score, 4) if exp_score is not None else None,
            tfidf_baseline_score=tfidf_scores[i],
        )

        rankings.append(
            CandidateRanking(
                candidate_id=str(i + 1),
                detected_skills=pr.skills,
                experience_years=pr.experience_years,
                rank=1,
                rank_display="1",
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
                is_duplicate=pr.is_duplicate,
                duplicate_of=pr.duplicate_of,
                text_hash=pr.text_hash,
                resume_snippet=(pr.anonymized_text or "")[:4000] if weight_cfg.skill_weight is not None else (pr.cleaned_text or pr.raw_text or "")[:4000],
            )
        )

    # Sort descending by match_score
    rankings.sort(key=lambda r: r.match_score, reverse=True)

    # Assign competition ranks with tie detection (e.g. 1, T-2, T-2, 4)
    current_rank = 1
    idx = 0
    n = len(rankings)
    while idx < n:
        j = idx
        while j < n and abs(rankings[j].match_score - rankings[idx].match_score) < 1e-5:
            j += 1
        group_size = j - idx
        is_tie = group_size > 1
        display_str = f"T-{current_rank}" if is_tie else str(current_rank)
        for k in range(idx, j):
            rankings[k].rank = current_rank
            rankings[k].rank_display = display_str
        current_rank += group_size
        idx = j

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
        ScreeningResult containing job analysis, candidate rankings, total count,
        effective weights, and redistribution note.
    """
    if isinstance(job, str):
        job_obj = analyze_job(job)
    else:
        job_obj = job

    if weights is None:
        weight_cfg = WeightConfig()
    elif isinstance(weights, dict):
        weight_cfg = WeightConfig(**weights)
    else:
        weight_cfg = weights

    app_comp, non_app_comp, eff_w, note = get_applicable_components(job_obj, weight_cfg)
    parsed_resumes = parse_resumes(files)
    rankings = rank(job=job_obj, resumes=parsed_resumes, weights=weight_cfg)

    return ScreeningResult(
        job=job_obj,
        rankings=rankings,
        total_resumes=len(parsed_resumes),
        effective_weights=eff_w,
        non_applicable_components=non_app_comp,
        weight_redistribution_note=note,
    )


def build_recommendation(
    rankings: list[CandidateRanking],
    job: Optional[JobAnalysis] = None,
) -> Recommendation:
    """Builds a deterministic candidate recommendation from evaluation results without LLM.

    Handles ties for 1st place and tied runner-ups, duplicate candidate warnings,
    and excludes non-applicable components from strongest component / gaps.

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
            runner_up_score=None,
            margin_over_runner_up=None,
            missing_skills=[],
            is_tie=False,
            tied_candidates=[],
            strengths=[],
            gaps=[],
            warnings=["No candidates were evaluated."],
            summary_text="No candidate recommendations available because no resumes were evaluated.",
        )

    top = rankings[0]
    best_candidate = top.candidate
    best_score = top.match_score
    missing_skills = list(top.missing_required_skills)

    # Check ties for top position
    top_ties = [r for r in rankings if abs(r.match_score - top.match_score) < 1e-5]

    if len(top_ties) > 1:
        # Tied for #1: do not name an arbitrary runner up
        runner_up = None
        runner_up_score = None
        margin_over_runner_up = 0.0
        is_tie = True
        tied_candidates = [r.candidate for r in top_ties]
        other_names = ", ".join(r.candidate for r in top_ties if r.candidate != top.candidate)
        comparison_text = f"Tied for top position with {other_names} ({top.match_score:.1f}%)."
    elif len(rankings) == 1:
        runner_up = None
        runner_up_score = None
        margin_over_runner_up = None
        is_tie = False
        tied_candidates = [best_candidate]
        comparison_text = f"{best_candidate} was the sole candidate evaluated."
    else:
        second = rankings[1]
        second_ties = [r for r in rankings[1:] if abs(r.match_score - second.match_score) < 1e-5]
        margin = round(top.match_score - second.match_score, 2)
        margin_over_runner_up = margin
        runner_up_score = second.match_score
        is_tie = False
        tied_candidates = [best_candidate]
        if len(second_ties) > 1:
            # Tied runners-up: do not name an arbitrary runner-up
            tied_names = ", ".join(r.candidate for r in second_ties)
            runner_up = f"{tied_names} (Tied)"
            comparison_text = f"Outperforms tied runners-up {tied_names} ({second.match_score:.1f}%) by a margin of {margin:.1f} pts."
        else:
            runner_up = second.candidate
            comparison_text = f"Outperforms runner-up {runner_up} ({second.match_score:.1f}%) by a margin of {margin:.1f} pts."

    # Strengths: only consider applicable components (score is not None)
    strengths: list[str] = []
    if top.matched_required_skills:
        strengths.append(f"Matched required skills: {', '.join(top.matched_required_skills)}")
    if top.matched_preferred_skills:
        strengths.append(f"Matched preferred skills: {', '.join(top.matched_preferred_skills)}")

    comp_scores: dict[str, float] = {}
    if top.component_scores.required_skill_score is not None:
        comp_scores["Required Skills"] = top.component_scores.required_skill_score * 100.0
    if top.component_scores.preferred_skill_score is not None:
        comp_scores["Preferred Skills"] = top.component_scores.preferred_skill_score * 100.0
    comp_scores["Semantic Similarity"] = top.component_scores.semantic_score * 100.0
    if top.component_scores.experience_score is not None:
        comp_scores["Experience Match"] = top.component_scores.experience_score * 100.0

    if comp_scores:
        strongest_name, strongest_val = max(comp_scores.items(), key=lambda item: item[1])
        strengths.append(f"Strongest scoring component: {strongest_name} ({strongest_val:.1f}%)")

    # Gaps: do not list non-applicable components as gaps
    gaps: list[str] = []
    if job and not job.required_skills:
        gaps.append("None — required skills were not specified for this role.")
    elif top.missing_required_skills:
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

    # Duplicate resume warnings
    if top.is_duplicate:
        warnings.append(f"Probable duplicate resume: {top.candidate} has identical content to {top.duplicate_of}.")
    cohort_dups = [f"{r.candidate} (duplicate of {r.duplicate_of})" for r in rankings if r.is_duplicate and r.candidate != top.candidate]
    if cohort_dups:
        warnings.append(f"Probable duplicate resumes detected: {', '.join(cohort_dups)}.")

    # Multi-job posting warning if detected
    if job and job.has_multiple_jobs and job.multiple_jobs_warning:
        warnings.append(job.multiple_jobs_warning)

    # Summary text
    summary_parts = [
        f"{best_candidate} is the recommended top candidate with a composite score of {best_score:.1f}%.",
        comparison_text,
    ]

    is_partial_fit = (best_score < 50.0) or bool(top.missing_required_skills) or bool(top.below_min_experience)

    if is_partial_fit:
        missing_reasons: list[str] = []
        if top.missing_required_skills:
            missing_reasons.append(f"missing required skills: {', '.join(top.missing_required_skills)}")
        if top.below_min_experience:
            min_exp_note = f" ({job.min_experience_years:.1f}+ years required)" if (job and job.min_experience_years) else ""
            missing_reasons.append(f"falls below the minimum required experience{min_exp_note}")
        if best_score < 50.0 and not top.missing_required_skills and not top.below_min_experience:
            missing_reasons.append(f"composite score below 50% ({best_score:.1f}%)")

        missing_details = f" ({'; '.join(missing_reasons)})" if missing_reasons else ""
        summary_parts.append(
            f"Rated as best available match, partial fit{missing_details}."
        )
    else:
        total_reqs = len(job.required_skills) if job and job.required_skills else len(top.matched_required_skills)
        summary_parts.append(
            f"Demonstrates strong alignment matching {len(top.matched_required_skills)}/{total_reqs} required skills."
        )

    summary_text = " ".join(summary_parts)

    return Recommendation(
        best_candidate=best_candidate,
        best_score=best_score,
        runner_up=runner_up,
        runner_up_score=runner_up_score,
        margin_over_runner_up=margin_over_runner_up,
        missing_skills=missing_skills,
        is_tie=is_tie,
        tied_candidates=tied_candidates,
        strengths=strengths,
        gaps=gaps,
        warnings=warnings,
        summary_text=summary_text,
    )


def get_score_contributions(
    candidate: CandidateRanking,
    weights: Optional[WeightConfig] = None,
    job: Optional[JobAnalysis] = None,
) -> dict[str, Any]:
    """Computes the weighted contribution of each component in percentage points.

    Scales components by the experience penalty if below_min_experience is True,
    ensuring applicable contributions sum exactly to candidate.match_score.
    Non-applicable components are returned as None ("N/A").
    """
    if weights is None:
        weights = WeightConfig()

    penalty = weights.experience_penalty if candidate.below_min_experience else 1.0

    if job is not None:
        app_list, _, eff_weights, _ = get_applicable_components(job, weights)
    else:
        # Determine from candidate scores
        app_list = ["semantic"]
        if candidate.component_scores.required_skill_score is not None:
            app_list.append("required")
        if candidate.component_scores.preferred_skill_score is not None:
            app_list.append("preferred")
        if candidate.component_scores.experience_score is not None:
            app_list.append("experience")

        user_w = {
            "required": weights.required_skill_weight,
            "preferred": weights.preferred_skill_weight,
            "semantic": weights.semantic_weight,
            "experience": weights.experience_weight,
        }
        if weights.renormalize_weights:
            s = sum(user_w[c] for c in app_list)
            eff_weights = {c: (user_w[c] / s if s > 0 and c in app_list else 0.0) for c in user_w}
        else:
            eff_weights = dict(user_w)

    raw_req = (candidate.component_scores.required_skill_score or 0.0) * eff_weights["required"] * 100.0 if "required" in app_list else 0.0
    raw_pref = (candidate.component_scores.preferred_skill_score or 0.0) * eff_weights["preferred"] * 100.0 if "preferred" in app_list else 0.0
    raw_sem = candidate.component_scores.semantic_score * eff_weights["semantic"] * 100.0
    raw_exp = (candidate.component_scores.experience_score or 0.0) * eff_weights["experience"] * 100.0 if "experience" in app_list else 0.0

    req_contrib = round(raw_req * penalty, 2)
    pref_contrib = round(raw_pref * penalty, 2)
    sem_contrib = round(raw_sem * penalty, 2)
    exp_contrib = round(raw_exp * penalty, 2)

    # Reconcile rounding discrepancy against candidate.match_score on largest applicable component
    diff = round(candidate.match_score - (req_contrib + pref_contrib + sem_contrib + exp_contrib), 2)
    if abs(diff) > 0:
        candidates_to_adjust = []
        if "required" in app_list:
            candidates_to_adjust.append(("required", req_contrib))
        if "preferred" in app_list:
            candidates_to_adjust.append(("preferred", pref_contrib))
        candidates_to_adjust.append(("semantic", sem_contrib))
        if "experience" in app_list:
            candidates_to_adjust.append(("experience", exp_contrib))

        candidates_to_adjust.sort(key=lambda x: x[1], reverse=True)
        largest = candidates_to_adjust[0][0]
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
        "required_skills": req_contrib if "required" in app_list else None,
        "preferred_skills": pref_contrib if "preferred" in app_list else None,
        "semantic_similarity": sem_contrib,
        "experience_match": exp_contrib if "experience" in app_list else None,
        "total_contribution": round(
            (req_contrib if "required" in app_list else 0.0)
            + (pref_contrib if "preferred" in app_list else 0.0)
            + sem_contrib
            + (exp_contrib if "experience" in app_list else 0.0),
            2,
        ),
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
            "rank_display": r.rank_display or str(r.rank),
            "color_category": "Top Candidate" if r.rank == 1 else "Candidate",
            "is_duplicate": r.is_duplicate,
            "duplicate_of": r.duplicate_of,
        }
        for r in rankings
    ]


def get_score_composition_chart_data(
    rankings: list[CandidateRanking],
    weights: Optional[WeightConfig] = None,
    job: Optional[JobAnalysis] = None,
) -> list[dict[str, Any]]:
    """Formats weighted contributions into stacked chart data records for applicable components."""
    if weights is None:
        weights = WeightConfig()

    if weights.skill_weight is not None:
        records = []
        for candidate in rankings:
            scores = candidate.component_scores
            factors = {
                "Semantic": (scores.semantic_score, weights.semantic_weight),
                "Keyword": (scores.tfidf_baseline_score, weights.keyword_weight),
                "Skills": (scores.skill_score, weights.skill_weight),
                "Experience": (scores.experience_score, weights.experience_weight),
            }
            points = {label: round((score or 0) * weight * 100, 2) for label, (score, weight) in factors.items()}
            largest = max(points, key=points.__getitem__)
            points[largest] = round(points[largest] + candidate.match_score - sum(points.values()), 2)
            records.extend({
                "candidate": candidate.candidate,
                "component": label,
                "contribution": value,
                "percentage_label": f"{value:.2f}",
                "below_min_experience": candidate.below_min_experience,
                "penalty_note": "",
            } for label, value in points.items())
        return records

    records: list[dict[str, Any]] = []
    for r in rankings:
        contribs = get_score_contributions(r, weights, job)
        penalty_note = f" (Penalty: ×{contribs['experience_penalty_applied']:.2f})" if r.below_min_experience else ""

        if contribs["required_skills"] is not None:
            records.append({
                "candidate": r.candidate,
                "component": "1. Required Skills",
                "contribution": contribs["required_skills"],
                "percentage_label": f"{contribs['required_skills']:.1f}%",
                "below_min_experience": r.below_min_experience,
                "penalty_note": penalty_note,
            })
        if contribs["preferred_skills"] is not None:
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
        if contribs["experience_match"] is not None:
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
    items = []
    if candidate.component_scores.required_skill_score is not None:
        items.append({"component": "Required Skills", "percentage": round(candidate.component_scores.required_skill_score * 100.0, 1)})
    else:
        items.append({"component": "Required Skills", "percentage": None, "display": "N/A"})

    if candidate.component_scores.preferred_skill_score is not None:
        items.append({"component": "Preferred Skills", "percentage": round(candidate.component_scores.preferred_skill_score * 100.0, 1)})
    else:
        items.append({"component": "Preferred Skills", "percentage": None, "display": "N/A"})

    items.append({"component": "Semantic Match", "percentage": round(candidate.component_scores.semantic_score * 100.0, 1)})

    if candidate.component_scores.experience_score is not None:
        items.append({"component": "Experience Match", "percentage": round(candidate.component_scores.experience_score * 100.0, 1)})
    else:
        items.append({"component": "Experience Match", "percentage": None, "display": "N/A"})

    items.append({"component": "TF-IDF Baseline", "percentage": round(tfidf * 100.0, 1)})
    return items
