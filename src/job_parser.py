"""Job description parser module.

Parses job descriptions to extract required vs preferred skills using section headers
and in-line cue phrases, and extracts minimum required years of experience.
"""

from __future__ import annotations

import re
from typing import Any

from src.skill_extractor import TechnicalSkillExtractor

# Cached singleton instance of TechnicalSkillExtractor
_SKILL_EXTRACTOR: TechnicalSkillExtractor | None = None


def get_skill_extractor() -> TechnicalSkillExtractor:
    """Returns a cached instance of TechnicalSkillExtractor."""
    global _SKILL_EXTRACTOR
    if _SKILL_EXTRACTOR is None:
        _SKILL_EXTRACTOR = TechnicalSkillExtractor()
    return _SKILL_EXTRACTOR


# Section Header Patterns
REQ_SECTION_PATTERNS = re.compile(
    r"^(?:required(?:\s+skills?|\s+qualifications?|\s+requirements?|\s+experience)?|"
    r"minimum(?:\s+qualifications?|\s+requirements?|\s+skills?)?|"
    r"basic(?:\s+qualifications?|\s+requirements?|\s+skills?)?|"
    r"must\s+haves?|"
    r"what\s+you(?:\x27ll|\s+will)?\s+need|"
    r"what\s+we(?:\x27re|\s+are)?\s+looking\s+for|"
    r"mandatory(?:\s+requirements?|\s+qualifications?)?|"
    r"essential(?:\s+qualifications?|\s+requirements?|\s+skills?)?|"
    r"prerequisites?|"
    r"core\s+requirements?|"
    r"key\s+responsibilities?|"
    r"responsibilities?|"
    r"duties|"
    r"requirements?|"
    r"qualifications?)$",
    re.IGNORECASE,
)

PREF_SECTION_PATTERNS = re.compile(
    r"^(?:preferred(?:\s+skills?|\s+qualifications?|\s+requirements?)?|"
    r"nice\s+to\s+have|"
    r"desired(?:\s+qualifications?|\s+skills?|\s+requirements?)?|"
    r"bonus(?:\s+points?|\s+qualifications?)?|"
    r"good\s+to\s+have|"
    r"pluses?|"
    r"what\s+would\s+be\s+nice|"
    r"additional(?:\s+qualifications?|\s+skills?)?|"
    r"desired\s+skills?|"
    r"optional\s+skills?)$",
    re.IGNORECASE,
)

EXCLUDED_SECTION_PATTERNS = re.compile(
    r"^(?:about\s+(?:us|the\s+company|our\s+team)|"
    r"company\s+overview|"
    r"who\s+we\s+are|"
    r"benefits|"
    r"what\s+we\s+offer|"
    r"perks|"
    r"compensation|"
    r"equal\s+opportunity)$",
    re.IGNORECASE,
)

# In-line Cue Phrase Patterns
REQ_CUE_PATTERNS = re.compile(
    r"\b(?:must\s+have|must\s+be(?:\s+proficient)?|required|essential|minimum|should\s+have|"
    r"need\s+to\s+have|mandatory|must\s+possess|prerequisite|proficien(?:t|cy)|a\s+must)\b",
    re.IGNORECASE,
)

PREF_CUE_PATTERNS = re.compile(
    r"\b(?:preferred|nice\s+to\s+have|is\s+a\s+plus|a\s+plus|\bplus\b|bonus|optional|ideal|desired|good\s+to\s+have|advantageous)\b",
    re.IGNORECASE,
)


def detect_multiple_jobs(text: str) -> tuple[bool, str | None]:
    """Detects if job description text appears to contain multiple job postings or roles.

    Returns:
        (has_multiple_jobs, warning_message)
    """
    if not text or not isinstance(text, str):
        return False, None

    # Pattern 1: Multiple explicit Job Title / Position Title lines
    title_matches = re.findall(
        r"(?im)^(?:\s*#*\s*)(?:job\s+title|position\s+title|target\s+role|role\s+title|position)\s*:\s*[^\n]+",
        text,
    )
    if len(title_matches) >= 2:
        return True, "This description appears to contain multiple job postings (multiple Job Title lines detected). Evaluating one job description per run yields more accurate skill matching."

    # Pattern 2: Numbered postings e.g. "Job 1:", "Job 2:", "Position 1:", "Role 1:", "Posting 1:"
    numbered_jobs = re.findall(
        r"(?im)^(?:\s*#*\s*)(?:job|position|role|opening|posting)\s*(?:#|\b)?\s*([1-9]|one|two|three)\s*[:\-\.]",
        text,
    )
    if len(numbered_jobs) >= 2:
        return True, "This description appears to contain multiple numbered job postings. Evaluating one role per run yields more accurate skill matching."

    # Pattern 3: Multiple distinct Requirements headers
    req_headers = re.findall(
        r"(?im)^(?:\s*#*\s*)(?:requirements|required\s+skills|minimum\s+qualifications)\s*:",
        text,
    )
    if len(req_headers) >= 2:
        return True, "This description appears to contain multiple job specification sections. Evaluating one role per run yields more accurate skill matching."

    return False, None


def extract_min_experience_years(text: str) -> float | None:
    """Extracts minimum required years of experience from text.

    Supports expressions such as:
        - '3+ years' -> 3.0
        - 'at least 5 years' -> 5.0
        - '3-5 years' -> 3.0
        - 'minimum of 4 years experience' -> 4.0
        - '2.5+ years of experience' -> 2.5

    Args:
        text: Input job description text or requirement snippet.

    Returns:
        Minimum years of experience as float, or None if not found.
    """
    if not text or not isinstance(text, str):
        return None

    patterns = [
        # Pattern 1: at least / minimum / min X years (or X-Y years)
        r"(?:at\s+least|minimum(?:\s+of)?|min\.?)\s*(\d+(?:\.\d+)?)\s*(?:-|–|—|to|\+)?\s*(?:\d+(?:\.\d+)?\s*)?\b(?:years?|yrs?)\b(?!\s+(?:old|of\s+age)\b)",
        # Pattern 2: range X-Y years / X to Y years
        r"(\d+(?:\.\d+)?)\s*(?:-|–|—|to)\s*(?:\d+(?:\.\d+)?)\s*\+?\s*\b(?:years?|yrs?)\b(?!\s+(?:old|of\s+age)\b)",
        # Pattern 3: X+ years / X+ yrs
        r"(\d+(?:\.\d+)?)\s*\+\s*\b(?:years?|yrs?)\b(?!\s+(?:old|of\s+age)\b)",
        # Pattern 4: X years of (relevant/work/etc.) experience or X years in ...
        r"(\d+(?:\.\d+)?)\s*\b(?:years?|yrs?)\b\s+(?:of\s+)?(?:[a-z]+\s+)?(?:experience|exp\.?)\b(?!\s+(?:old|of\s+age)\b)",
        r"(\d+(?:\.\d+)?)\s*\b(?:years?|yrs?)\b\s+in\s+",
        # Pattern 5: experience: X years
        r"experience\s*:\s*(?:at\s+least|min\.?|minimum)?\s*(\d+(?:\.\d+)?)\s*\+?\s*\b(?:years?|yrs?)\b(?!\s+(?:old|of\s+age)\b)",
    ]

    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except (ValueError, IndexError):
                continue

    return None


def _split_into_clauses(text: str) -> list[str]:
    """Splits a line into fine-grained clauses using sentences, semicolons, and contrasting conjunctions."""
    sentence_splits = re.split(r"\.\s+(?=[A-Z0-9\-\*])", text)
    semi_splits: list[str] = []
    for s in sentence_splits:
        semi_splits.extend(re.split(r";\s*", s))
    clauses: list[str] = []
    for s in semi_splits:
        clauses.extend(re.split(r",?\s+(?:while|whereas|although|but)\s+", s, flags=re.IGNORECASE))
    return [c.strip() for c in clauses if c.strip()]


def parse_job_description(text: str) -> dict[str, Any]:
    """Parses a job description to extract required and preferred skills and min experience years.

    Uses section headers and in-line cue phrases to categorize skills into required vs preferred.
    Precedence: required evidence takes precedence over preferred evidence. If neither section
    headers nor cue phrases are present, extracted technical skills default to required.

    Args:
        text: Plain text of the job description.

    Returns:
        Dict with keys:
            - 'raw_text': str
            - 'required_skills': list[str] (sorted, canonical skill names)
            - 'preferred_skills': list[str] (sorted, canonical skill names)
            - 'all_skills': list[str] (sorted union of required and preferred skills)
            - 'min_experience_years': Optional[float]
    """
    empty_result: dict[str, Any] = {
        "raw_text": text if isinstance(text, str) else "",
        "required_skills": [],
        "preferred_skills": [],
        "all_skills": [],
        "min_experience_years": None,
    }

    if not text or not isinstance(text, str) or not text.strip():
        return empty_result

    extractor = get_skill_extractor()
    all_extracted_skills = extractor.extract_skills(text)

    lines = text.splitlines()
    curr_section = "neutral"
    has_req_section = False
    has_pref_section = False

    req_clauses: list[str] = []
    pref_clauses: list[str] = []
    neutral_clauses: list[str] = []
    req_section_text: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Check section header
        header_candidate = re.sub(r"[\s:;.,]+$", "", stripped)
        header_base = re.sub(r"\s*\([^)]*\)", "", header_candidate).strip()
        header_base = re.sub(r"\s*\[[^\]]*\]", "", header_base).strip()

        cleaned_header = re.sub(r"^[#*\-=_~\[\]\(\)\s:;.,]+|[#*\-=_~\[\]\(\)\s:;.,]+$", "", stripped)
        cleaned_header = re.sub(
            r"^(?:\[?\d+[.)\]]|\(\d+\)|\[?[a-zA-Z][.)\]]|\([a-zA-Z]\)|\[?[ivxIVX]+[.)\]]|\([ivxIVX]+\))\s*",
            "",
            cleaned_header,
        )
        cleaned_header = re.sub(r"^[#*\-=_~\[\]\(\)\s:;.,]+|[#*\-=_~\[\]\(\)\s:;.,]+$", "", cleaned_header).strip()
        cleaned_header_base = re.sub(r"^[#*\-=_~\[\]\(\)\s:;.,]+|[#*\-=_~\[\]\(\)\s:;.,]+$", "", header_base).strip()

        is_req = bool(REQ_SECTION_PATTERNS.match(cleaned_header) or REQ_SECTION_PATTERNS.match(cleaned_header_base))
        is_pref = bool(PREF_SECTION_PATTERNS.match(cleaned_header) or PREF_SECTION_PATTERNS.match(cleaned_header_base))
        is_excl = bool(EXCLUDED_SECTION_PATTERNS.match(cleaned_header) or EXCLUDED_SECTION_PATTERNS.match(cleaned_header_base))

        if is_req:
            curr_section = "required"
            has_req_section = True
            continue
        elif is_pref:
            curr_section = "preferred"
            has_pref_section = True
            continue
        elif is_excl:
            curr_section = "excluded"
            continue
            curr_section = "excluded"
            continue

        if curr_section == "excluded":
            continue

        if curr_section == "required":
            req_section_text.append(stripped)

        # Split line by clauses/sentences for fine-grained cue detection
        clauses = _split_into_clauses(stripped)
        for clause in clauses:
            c_str = clause.strip()
            if not c_str:
                continue
            has_req_cue = bool(REQ_CUE_PATTERNS.search(c_str))
            has_pref_cue = bool(PREF_CUE_PATTERNS.search(c_str))

            if has_req_cue and not has_pref_cue:
                req_clauses.append(c_str)
            elif has_pref_cue and not has_req_cue:
                pref_clauses.append(c_str)
            elif curr_section == "required":
                req_clauses.append(c_str)
            elif curr_section == "preferred":
                pref_clauses.append(c_str)
            else:
                neutral_clauses.append(c_str)

    # Extract skills per clause bucket
    req_skills: set[str] = set()
    for c in req_clauses:
        req_skills.update(extractor.extract_skills(c))

    pref_skills: set[str] = set()
    for c in pref_clauses:
        pref_skills.update(extractor.extract_skills(c))

    # Required takes precedence over preferred
    pref_skills.difference_update(req_skills)

    # If no explicit sections or cue phrases were present, all skills default to required
    if not has_req_section and not has_pref_section and not req_clauses and not pref_clauses:
        req_skills.update(all_extracted_skills)
    elif not req_skills:
        # Preferred skills found, but no explicit required cues:
        # Any other extracted skill not in preferred defaults to required
        remaining = set(all_extracted_skills) - pref_skills
        req_skills.update(remaining)
    elif not has_req_section and not has_pref_section:
        # Some in-line cues were used; remaining neutral skills default to required
        neutral_skills = set(all_extracted_skills) - pref_skills - req_skills
        req_skills.update(neutral_skills)

    # Required strictly overrides preferred
    pref_skills.difference_update(req_skills)

    # Extract minimum experience years (search required section text first, then whole text)
    min_exp: float | None = None
    if req_section_text:
        min_exp = extract_min_experience_years("\n".join(req_section_text))
    if min_exp is None and req_clauses:
        min_exp = extract_min_experience_years("\n".join(req_clauses))
    if min_exp is None:
        min_exp = extract_min_experience_years(text)

    sorted_req = sorted(req_skills)
    sorted_pref = sorted(pref_skills)
    sorted_all = sorted(req_skills | pref_skills)

    has_multi, multi_warn = detect_multiple_jobs(text)

    return {
        "raw_text": text,
        "required_skills": sorted_req,
        "preferred_skills": sorted_pref,
        "all_skills": sorted_all,
        "min_experience_years": min_exp,
        "has_multiple_jobs": has_multi,
        "multiple_jobs_warning": multi_warn,
    }
