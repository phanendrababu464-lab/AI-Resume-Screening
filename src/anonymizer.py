"""Candidate anonymization module for PII and demographic attribute redaction.

Redacts Personally Identifiable Information (PII) including candidate names,
email addresses, phone numbers, and gendered pronouns from resume texts and
structured resume dictionaries to ensure evaluation invariance.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import re
from typing import Any, Optional

# Standard replacement tokens
NAME_TOKEN = "[NAME]"
EMAIL_TOKEN = "[EMAIL]"
PHONE_TOKEN = "[PHONE]"
PRONOUN_TOKEN = "[PRONOUN]"

# Prefix titles (honorifics/professional titles at the start of names)
PREFIX_TITLES: set[str] = {
    "mr", "mrs", "ms", "miss", "dr", "prof", "rev",
}

# Suffixes (degrees, designations, generational markers at the end of names)
SUFFIXES: set[str] = {
    "jr", "sr", "ii", "iii", "iv", "phd", "md", "esq", "mba", "cpa",
}

# Common English stopwords to avoid matching as standalone name tokens
COMMON_STOPWORDS: set[str] = {
    "and", "or", "the", "in", "at", "to", "for", "with", "on", "by", "from",
    "an", "a", "of", "is", "was", "are", "were", "be", "been", "has", "have", "had",
    "do", "does", "did", "as", "if", "not", "so", "up", "out",
    # Common English modal verbs / polysemes
    "will", "can", "may", "might", "shall", "must", "art", "go",
    # Calendar month abbreviations and full names
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
    "january", "february", "march", "april", "june", "july", "august",
    "september", "october", "november", "december",
}

# Technical skills guard set: programming languages and tools that frequently collide with human names
KNOWN_SKILLS_GUARD: set[str] = {
    "ruby", "rust", "swift", "bash", "go", "julia", "r", "c",
    "python", "java", "scala", "kotlin", "perl", "dart", "lua", "php",
    "haskell", "clojure", "elixir", "erlang", "matlab", "fortran", "cobol",
    "lisp", "scheme", "prolog", "docker", "kubernetes", "ansible", "terraform",
    "jenkins", "git", "linux", "aws", "azure", "gcp", "spark", "hadoop",
    "kafka", "flink", "storm", "react", "vue", "angular", "node", "django",
    "flask", "fastapi", "spring", "sql", "mysql", "postgres", "postgresql",
    "redis", "mongodb", "cassandra",
}

_LOADED_TECHNICAL_SKILLS: set[str] | None = None


def _get_technical_skills_set() -> set[str]:
    """Returns lowercased technical skills set from taxonomy file or fallback guard set."""
    global _LOADED_TECHNICAL_SKILLS
    if _LOADED_TECHNICAL_SKILLS is not None:
        return _LOADED_TECHNICAL_SKILLS

    skills: set[str] = set(KNOWN_SKILLS_GUARD)
    try:
        from src.config import DEFAULT_SKILLS_FILE
        skills_file = Path(DEFAULT_SKILLS_FILE)
    except Exception:
        skills_file = Path(__file__).resolve().parent.parent / "data" / "skills" / "technical_skills.json"

    if skills_file.exists():
        try:
            with open(skills_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data.get("skills", []):
                    if isinstance(item, str):
                        clean_item = item.strip().lower()
                        if clean_item:
                            skills.add(clean_item)
                            for word in clean_item.split():
                                w_clean = re.sub(r"^[^\w]+|[^\w]+$", "", word)
                                if len(w_clean) >= 2:
                                    skills.add(w_clean)
        except Exception:
            pass

    _LOADED_TECHNICAL_SKILLS = skills
    return _LOADED_TECHNICAL_SKILLS

# Regex for email addresses (handles standard, subdomains, plus-addressing)
EMAIL_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

# Regex for phone numbers (US and international formats, extensions, parens, dots, dashes, spaces)
PHONE_REGEX = re.compile(
    r"""
    (?<!\w)
    (?:
        # International formats with '+' prefix
        \+\d{1,3}[-.\s]*(?:\([0-9]+\)[-.\s]*)?(?:[0-9]{1,4}[-.\s]*){2,5}[0-9]{2,5}
        |
        # Standard US/NANP format with or without +1 / 1
        (?:\+?1[-.\s]*)?
        (?:
            \(\s*\d{3}\s*\)[-.\s]*\d{3}[-.\s]*\d{4}
            |
            \b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b
        )
        |
        # Multi-segment formats like 555-0199-88
        \b\d{3}[-.\s]\d{4}[-.\s]\d{2,4}\b
        |
        # European city code formats like 030 1234567
        \b0\d{1,4}[-.\s]\d{5,8}\b
        |
        # 7-digit local formats like 555-0101
        \b\d{3}[-.\s]\d{4}\b
    )
    (?:\s*(?:ext|x|ext\.)\s*\d{1,5})?
    (?!\w)
    """,
    re.VERBOSE,
)

# Regex for gendered and neutral personal pronouns with strict word boundaries (longer tokens first)
PRONOUN_REGEX = re.compile(
    r"\b(?:themselves|himself|herself|their|them|they|hers|her|him|his|she|he)\b",
    re.IGNORECASE,
)

# Regex for explicit candidate name labels (e.g., Name: Jane Doe)
NAME_LABEL_REGEX = re.compile(
    r"((?:Candidate(?:\s+Name)?|Full Name|Applicant(?:\s+Name)?|Name)[ \t]*:[ \t]*)[A-Za-z \t.,\x27-]+",
    re.IGNORECASE,
)

# Regex for honorifics / prefix titles preceding name placeholder
HONORIFIC_NAME_REGEX = re.compile(
    r"\b(?:Mr|Mrs|Ms|Miss|Dr|Prof|Rev)\.?\s*\[NAME\]",
    re.IGNORECASE,
)


def _generate_name_variations(name: str) -> list[str]:
    """Generates variations and sub-sequences of a candidate name for redaction."""
    if not name or not name.strip():
        return []

    variations: set[str] = set()
    cleaned = name.strip()
    raw_tokens = cleaned.split()

    # Identify prefix titles
    start_idx = 0
    while start_idx < len(raw_tokens):
        token_clean = re.sub(r"^[^\w]+|[^\w]+$", "", raw_tokens[start_idx]).lower()
        if token_clean in PREFIX_TITLES:
            start_idx += 1
        else:
            break

    # Identify suffixes
    end_idx = len(raw_tokens)
    while end_idx > start_idx:
        token_clean = re.sub(r"^[^\w]+|[^\w]+$", "", raw_tokens[end_idx - 1]).lower()
        if token_clean in SUFFIXES:
            end_idx -= 1
        else:
            break

    tech_skills = _get_technical_skills_set()

    # Add full name if multi-word
    if len(raw_tokens) >= 2:
        variations.add(cleaned)

    # Add name without prefix title (may still include suffix like "John Doe, Jr.")
    if start_idx < len(raw_tokens):
        without_title = " ".join(raw_tokens[start_idx:])
        if without_title:
            wt_tokens = without_title.split()
            if len(wt_tokens) >= 2:
                variations.add(without_title)
            elif (
                len(wt_tokens) == 1
                and wt_tokens[0].lower() not in COMMON_STOPWORDS
                and wt_tokens[0].lower() not in tech_skills
            ):
                variations.add(without_title)

    # Core name without prefix title or suffix (e.g. "John Doe")
    if start_idx < end_idx:
        core_tokens = raw_tokens[start_idx:end_idx]
        core_clean = [re.sub(r"^[^\w]+|[^\w]+$", "", t) for t in core_tokens]
        core_clean = [t for t in core_clean if t]

        if len(core_clean) >= 2:
            variations.add(" ".join(core_clean))
            if len(core_clean) >= 3:
                variations.add(f"{core_clean[0]} {core_clean[-1]}")
            for n in range(2, len(core_clean)):
                for i in range(len(core_clean) - n + 1):
                    variations.add(" ".join(core_clean[i : i + n]))

        # Single-token unigrams: guard against technical skills and stopwords
        for t in core_clean:
            if "-" in t:
                parts = t.split("-")
                for p in parts:
                    p_c = re.sub(r"^[^\w]+|[^\w]+$", "", p)
                    if (
                        len(p_c) >= 2
                        and p_c.lower() not in COMMON_STOPWORDS
                        and p_c.lower() not in tech_skills
                    ):
                        variations.add(p_c)
            if (
                len(t) >= 2
                and t.lower() not in COMMON_STOPWORDS
                and t.lower() not in tech_skills
            ):
                variations.add(t)

    return sorted(variations, key=lambda x: len(x), reverse=True)


def _detect_names_from_text(text: str, candidate_name: Optional[str] = None) -> list[str]:
    """Detects candidate names from explicit labels or prominent header lines in text."""
    names: list[str] = []

    # 1. Explicit labels
    label_patterns = [
        r"(?:Candidate(?:\s+Name)?|Full Name|Applicant(?:\s+Name)?|Name)[ \t]*:[ \t]*([A-Za-z \t.\x27-]+)",
    ]
    for pat in label_patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            val = m.group(1).strip()
            val = re.split(r"[|\n,\t;]", val)[0].strip()
            if 2 <= len(val.split()) <= 4:
                names.append(val)

    # 2. First non-empty lines in resume text (heuristic header detection)
    # Only run heuristic header detection if candidate_name is omitted or empty
    if not candidate_name or not candidate_name.strip():
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        non_name_headers = {
            "resume", "curriculum vitae", "cv", "summary", "profile", "contact",
            "experience", "education", "skills", "projects", "objective", "certifications",
            "work experience", "professional experience",
            # Professional designations & job titles
            "engineer", "developer", "architect", "manager", "lead", "analyst",
            "specialist", "consultant", "designer", "director", "administrator",
            "senior", "junior", "principal", "staff", "associate", "intern",
            "technologist", "scientist", "programmer", "officer", "coordinator",
        }
        for line in lines[:3]:
            cleaned_line = line.strip()
            if cleaned_line.lower() in non_name_headers:
                continue
            words = cleaned_line.split()
            if 2 <= len(words) <= 4:
                # If any word in the header line is a professional designation or technical skill, treat as job title header
                tech_skills = _get_technical_skills_set()
                cleaned_words = [re.sub(r"^[^\w]+|[^\w]+$", "", w).lower() for w in words]
                if any(w in non_name_headers or w in tech_skills for w in cleaned_words if w):
                    continue
                if all(re.match(r"^[A-Z][a-zA-Z\x27-]*\.?$", w) for w in words):
                    if not re.search(r"[0-9@/\\_+=;:*]", cleaned_line):
                        names.append(cleaned_line)
                        break

            # Heuristic for unstructured narrative resumes starting with candidate name as subject
            narrative_match = re.match(
                r"^([A-Z][a-zA-Z\x27-]+(?:\s+[A-Z][a-zA-Z\x27-]+)?)\s+(?:has\b|is\b|was\b|graduated\b)",
                cleaned_line,
            )
            if narrative_match:
                cand_subj = narrative_match.group(1).strip()
                first_w = cand_subj.split()[0].lower()
                tech_skills = _get_technical_skills_set()
                if (
                    not PRONOUN_REGEX.match(cand_subj)
                    and first_w not in COMMON_STOPWORDS
                    and first_w not in tech_skills
                    and first_w not in non_name_headers
                ):
                    names.append(cand_subj)
                    break

    return list(dict.fromkeys(names))


_PROTECTED_HEADER = re.compile(
    r"(?im)^[ \t]*(?:age|date of birth|birth date|dob|gender|sex|pronouns?|"
    r"racial identity|race|ethnicity|religion|faith|disability|marital status|"
    r"sexual orientation|nationality|genetic information)[ \t]*[:=][^\r\n]*"
)
_AGE_IN_PROSE = re.compile(r"(?i)\b(?:aged[ \t]+[0-9]{1,3}|[0-9]{1,3}(?:[ \t-]+)years?(?:[ \t-]+)old)\b")


def redact_protected_attributes(text: str) -> str:
    """Remove explicit protected-attribute fields and age statements before relevance analysis."""
    return _AGE_IN_PROSE.sub("", _PROTECTED_HEADER.sub("", text))


def anonymize_text(text: str, candidate_name: Optional[str] = None) -> str:
    """Redacts candidate names, emails, phone numbers, and gendered pronouns from text.

    Args:
        text: Input string (resume snippet, parsed text, or document content).
        candidate_name: Optional explicit candidate name to target for redaction.

    Returns:
        The text with all PII replaced by canonical deterministic tokens:
        - Candidate name: [NAME]
        - Email addresses: [EMAIL]
        - Phone numbers: [PHONE]
        - Gendered pronouns: [PRONOUN]
    """
    if not text or not isinstance(text, str):
        return ""

    result = text

    # 1. Redact Email addresses first (prevents name tokens from breaking email structures)
    result = EMAIL_REGEX.sub(EMAIL_TOKEN, result)

    # 2. Redact Phone numbers
    result = PHONE_REGEX.sub(PHONE_TOKEN, result)

    # 3. Identify candidate names to redact
    names_to_redact: list[str] = []
    if candidate_name and candidate_name.strip():
        names_to_redact.append(candidate_name.strip())
    detected = _detect_names_from_text(result, candidate_name=candidate_name)
    names_to_redact.extend(detected)

    # Redact explicit name label patterns (e.g., "Name: Jane Doe" -> "Name: [NAME]")
    result = NAME_LABEL_REGEX.sub(r"\1" + NAME_TOKEN, result)

    # Generate and redact variations
    all_variations: set[str] = set()
    for name in names_to_redact:
        for var in _generate_name_variations(name):
            all_variations.add(var)

    sorted_variations = sorted(all_variations, key=lambda x: len(x), reverse=True)
    for var in sorted_variations:
        words = var.split()
        if len(words) == 1:
            w = words[0]
            # Single-token name variation: require TitleCase or UPPERCASE
            # to protect normal lowercase English vocabulary
            forms = {re.escape(w.capitalize()), re.escape(w.upper())}
            if w and w[0].isupper():
                forms.add(re.escape(w))
            pat = r"(?<!\w)(?:" + "|".join(forms) + r")(?!\w)"
            result = re.sub(pat, NAME_TOKEN, result)
        else:
            pat = r"(?<!\w)" + r"[\s,-]+".join(re.escape(w) for w in words) + r"(?!\w)"
            result = re.sub(pat, NAME_TOKEN, result, flags=re.IGNORECASE)

    # Collapse adjacent name tokens (e.g., [NAME] [NAME] or [NAME], [NAME] -> [NAME])
    result = re.sub(r"\[NAME\](?:\s*,?\s*\[NAME\])+", NAME_TOKEN, result)

    # Collapse honorifics / prefix titles preceding [NAME] (e.g., "Mr. [NAME]", "Dr. [NAME]" -> "[NAME]")
    result = HONORIFIC_NAME_REGEX.sub(NAME_TOKEN, result)

    # Collapse adjacent name tokens (in case honorific collapse created adjacent tokens)
    result = re.sub(r"\[NAME\](?:\s*,?\s*\[NAME\])+", NAME_TOKEN, result)

    # 4. Redact Gendered and Neutral Pronouns with strict word boundaries
    result = PRONOUN_REGEX.sub(PRONOUN_TOKEN, result)

    # Normalize auxiliary verb agreement after [PRONOUN] to guarantee evaluation invariance
    # (e.g. "[PRONOUN] have" -> "[PRONOUN] has", "[PRONOUN] are" -> "[PRONOUN] is", "[PRONOUN] were" -> "[PRONOUN] was")
    result = re.sub(r"\[PRONOUN\]\s+have\b", "[PRONOUN] has", result)
    result = re.sub(r"\[PRONOUN\]\s+are\b", "[PRONOUN] is", result)
    result = re.sub(r"\[PRONOUN\]\s+were\b", "[PRONOUN] was", result)

    return result


def anonymize_resume(
    resume_dict: dict[str, Any],
    candidate_name: Optional[str] = None,
) -> dict[str, Any]:
    """Anonymizes text fields in a resume dictionary.

    Preserves non-text metadata (e.g. filename, experience_years, skills lists)
    while redacting PII and gendered pronouns across all string fields and nested
    dictionaries (e.g. sections).

    Args:
        resume_dict: Dictionary representing a parsed or raw resume.
        candidate_name: Optional explicit candidate name. If omitted, extracted
            from 'candidate_name' or 'name' fields, or detected heuristically.

    Returns:
        A new dictionary with anonymized text fields and 'anonymized_text' populated.
        The original dictionary is not mutated.
    """
    if not isinstance(resume_dict, dict):
        return {}

    result = copy.deepcopy(resume_dict)

    # 1. Determine candidate name
    target_name = candidate_name
    if not target_name:
        for key in ("candidate_name", "name", "candidate"):
            val = resume_dict.get(key)
            if isinstance(val, str) and val.strip():
                # Avoid using filenames like 'resume.pdf' or synthetic labels like 'Candidate 1'
                if not re.search(r"\.(?:pdf|docx|txt)$", val, re.IGNORECASE):
                    target_name = val.strip()
                    break

    # Metadata keys that should remain untouched
    metadata_keys: set[str] = {
        "filename", "file_name", "file_path", "path", "id", "file", "extension",
    }

    def _anonymize_value(val: Any, key_name: Optional[str] = None) -> Any:
        if isinstance(val, str):
            if key_name in metadata_keys:
                return val
            return anonymize_text(val, candidate_name=target_name)
        elif isinstance(val, dict):
            return {k: _anonymize_value(v, key_name=k) for k, v in val.items()}
        elif isinstance(val, list):
            # Technical skills list should be preserved as-is
            if key_name == "skills":
                return val
            return [_anonymize_value(item, key_name=key_name) for item in val]
        return val

    # 2. Anonymize all string fields
    for k, v in list(result.items()):
        result[k] = _anonymize_value(v, key_name=k)

    # 3. Determine main text field and populate 'anonymized_text'
    main_text = ""
    for text_key in ("text", "raw_text", "cleaned_text"):
        if text_key in resume_dict and isinstance(resume_dict[text_key], str) and resume_dict[text_key].strip():
            main_text = resume_dict[text_key]
            break

    if not main_text and "sections" in resume_dict and isinstance(resume_dict["sections"], dict):
        section_texts = [
            str(v).strip()
            for v in resume_dict["sections"].values()
            if isinstance(v, str) and v.strip()
        ]
        main_text = "\n\n".join(section_texts)

    result["anonymized_text"] = anonymize_text(main_text, candidate_name=target_name)

    return result
