"""Text preprocessing and normalization module for resumes and job descriptions.

Prepares text for skill extraction and semantic embedding while preserving
technical nomenclature such as 'C++', 'C#', '.NET', and 'Node.js'.
"""

import re
import unicodedata


def clean_text(text: str) -> str:
    """Cleans raw text by normalizing unicode characters, bullet points, and whitespace.

    Preserves essential technical characters (+, #, ., /, -) used in programming languages
    and technical acronyms.

    Args:
        text: Raw text string from resumes or job descriptions.

    Returns:
        Cleaned, normalized string.
    """
    if not text or not isinstance(text, str):
        return ""

    # Normalize unicode representations (NFKD)
    normalized = unicodedata.normalize("NFKD", text)

    # Standardize bullet points and list markers into spaces
    # Includes common bullets: \u2022 (•), \u25AA (▪), \u25CF (●), etc.
    # Preserves intra-word hyphens (e.g., Scikit-Learn) while removing list bullets
    normalized = re.sub(
        r"[\u2022\u2023\u25E6\u2043\u2219\u00B7\u25AA\u25AB\u25CF\u25CB]\s*",
        " ",
        normalized,
    )
    normalized = re.sub(r"(?:^|(?<=[\r\n\s]))[\*\-]\s+", " ", normalized)

    # Replace control characters (excluding newline and tab)
    normalized = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F\u200B-\u200D\uFEFF]", " ", normalized)

    # Standardize spaces and tabs
    normalized = re.sub(r"[ \t]+", " ", normalized)

    # Strip line-level whitespace and sanitize duplicate empty lines
    lines = [line.strip() for line in normalized.split("\n")]
    normalized = "\n".join(lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)

    return normalized.strip()


def normalize_for_matching(text: str) -> str:
    """Produces a lowercased, whitespace-normalized string for pattern matching.

    Args:
        text: Input string.

    Returns:
        Lowercased and normalized string.
    """
    cleaned = clean_text(text)
    return cleaned.lower()
