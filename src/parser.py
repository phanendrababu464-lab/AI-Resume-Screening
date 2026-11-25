"""Resume parser module for PDF and DOCX documents.

Extracts raw text from resume files using pdfplumber and python-docx.
Supports both file paths (str, Path) and in-memory binary streams (e.g., io.BytesIO).
"""

from io import BytesIO
from pathlib import Path
import re
from typing import BinaryIO, Union

import docx
import pdfplumber

from src.config import ALLOWED_EXTENSIONS

FileSource = Union[str, Path, BinaryIO, BytesIO]


def extract_text_from_pdf(file_source: FileSource) -> str:
    """Extracts raw text from a PDF file source.

    Args:
        file_source: A filesystem path (str, Path) or a binary stream representing a PDF.

    Returns:
        Extracted text as a single string.

    Raises:
        ValueError: If the PDF cannot be opened or parsed.
    """
    text_segments: list[str] = []
    try:
        with pdfplumber.open(file_source, pages=range(1, 31)) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                page.close()
                if extracted:
                    text_segments.append(extracted)
    except Exception as exc:
        raise ValueError(f"Failed to extract text from PDF: {exc}") from exc

    return "\n".join(text_segments).strip()[:100_000]


def extract_text_from_docx(file_source: FileSource) -> str:
    """Extracts raw text from a DOCX file source, including paragraphs and tables.

    Args:
        file_source: A filesystem path (str, Path) or a binary stream representing a DOCX.

    Returns:
        Extracted text as a single string.

    Raises:
        ValueError: If the DOCX cannot be opened or parsed.
    """
    try:
        doc = docx.Document(file_source)
        text_segments: list[str] = []

        # Extract regular paragraphs
        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            if text:
                text_segments.append(text)

        # Extract table contents (often used in resumes for skills and layout)
        for table in doc.tables:
            for row in table.rows:
                row_texts = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_texts:
                    text_segments.append(" | ".join(row_texts))

        return "\n".join(text_segments).strip()[:100_000]
    except Exception as exc:
        raise ValueError(f"Failed to extract text from DOCX: {exc}") from exc


def extract_text(file_source: FileSource, filename: str | None = None) -> str:
    """Dispatches text extraction based on file extension.

    Args:
        file_source: A filesystem path or binary stream.
        filename: Optional explicit filename (required if file_source is a stream).

    Returns:
        Extracted plain text from the resume.

    Raises:
        ValueError: If the file type is unsupported or cannot be determined.
    """
    extension: str | None = None

    if isinstance(file_source, (str, Path)):
        extension = Path(file_source).suffix.lower()
    elif filename:
        extension = Path(filename).suffix.lower()

    if not extension or extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file format '{extension}'. Allowed formats: {sorted(ALLOWED_EXTENSIONS)}"
        )

    if extension == ".pdf":
        return extract_text_from_pdf(file_source)
    elif extension == ".docx":
        return extract_text_from_docx(file_source)

    raise ValueError(f"Unhandled file extension: {extension}")


# ==============================================================================
# Resume Section Splitting & Fallback Heuristic
# ==============================================================================

SECTION_HEADING_PATTERNS: dict[str, re.Pattern[str]] = {
    "skills": re.compile(
        r"^(?:technical\s+skills?|core\s+competencies|technologies|tech\s+stack|"
        r"tools\s*(?:&|and)\s*technologies|tools\s*(?:&|and)\s*skills|skills\s*(?:&|and)\s*tools|"
        r"key\s+skills?|skills\s*(?:&|and)\s*abilities|skills?\s*(?:&|and)\s*expertise|"
        r"areas\s+of\s+expertise|programming\s+languages|"
        r"technical\s+(?:expertise|proficiencies|competencies)|"
        r"it\s+skills?|computer\s+skills?|skillset|skills)$",
        re.IGNORECASE,
    ),
    "experience": re.compile(
        r"^(?:professional\s+work\s+experience|work\s+experience|professional\s+experience|"
        r"employment\s+history|work\s+history|career\s+history|job\s+history|professional\s+background|"
        r"work\s*(?:&|and)\s*leadership|relevant\s+experience|work\s+background|"
        r"internships?(?:\s+experience)?|practical\s+experience|experience)$",
        re.IGNORECASE,
    ),
    "education": re.compile(
        r"^(?:academic\s+(?:background|history|qualifications|credentials|education)|"
        r"educational\s+(?:background|qualifications)|"
        r"education\s*(?:&|and)\s*(?:certifications|credentials|training)|"
        r"degrees?|qualifications|education)$",
        re.IGNORECASE,
    ),
    "projects": re.compile(
        r"^(?:key\s+projects?|personal\s+projects?|academic\s+projects?|"
        r"technical\s+projects?|featured\s+projects?|project\s+experience|"
        r"projects\s*(?:&|and)\s*achievements|projects\s*(?:&|and)\s*activities|"
        r"personal\s*(?:&|and)\s*open\s*source\s*projects?|"
        r"notable\s+projects?|selected\s+projects?|recent\s+projects?|projects)$",
        re.IGNORECASE,
    ),
    "other": re.compile(
        r"^(?:professional\s+summary|career\s+(?:objective|synopsis|summary|overview)|"
        r"synopsis|summary(?:\s+of\s+qualifications)?|"
        r"executive\s+summary|objective|profile|about\s+me|certifications?(?:\s*(?:&|and)\s*licenses?)?|"
        r"licenses?|certificates?|awards?(?:\s*(?:&|and)\s*honors?)?|honors?|publications?|"
        r"interests|languages?|extracurricular(?:\s+activities)?|volunteer(?:\s+experience)?|"
        r"volunteering|references?|contact(?:\s+info(?:rmation)?)?|personal\s+information)$",
        re.IGNORECASE,
    ),
}

def _clean_heading(text: str) -> str:
    """Cleans potential section heading text.

    Strips markdown symbols, decorative characters, leading list numerals
    (e.g. '1. ', '(1) ', '(A) ', roman numerals 'I. '), and trailing colons/punctuation.
    """
    cleaned = text.strip()
    # Strip outer markdown and decorative punctuation
    cleaned = re.sub(r"^[#*\-=_~\[\]\(\)\s:;.,]+|[#*\-=_~\[\]\(\)\s:;.,]+$", "", cleaned)
    # Strip leading list markers/numerals (e.g. "1. ", "(1) ", "1) ", "A. ", "(A) ", "I. ", "IV. ")
    cleaned = re.sub(
        r"^(?:\[?\d+[.)\]]|\(\d+\)|\[?[a-zA-Z][.)\]]|\([a-zA-Z]\)|\[?[ivxIVX]+[.)\]]|\([ivxIVX]+\))\s*",
        "",
        cleaned,
    )
    # Strip any remaining decorative wrappers or trailing punctuation
    cleaned = re.sub(r"^[#*\-=_~\[\]\(\)\s:;.,]+|[#*\-=_~\[\]\(\)\s:;.,]+$", "", cleaned)
    return cleaned.strip()


_EDU_KEYWORDS = [
    r"\bbachelor(?:\x27s)?\b", r"\bmaster(?:\x27s)?\b", r"\bph\.?d\.?\b",
    r"\bb\.?s\.?\b", r"\bm\.?s\.?\b", r"\bb\.?a\.?\b", r"\bm\.?a\.?\b",
    r"\bb\.?tech\.?\b", r"\bm\.?tech\.?\b", r"\bdegree\b", r"\bdoctorate\b",
    r"\bdiploma\b", r"\bassociates?(?:\x27s)?\b", r"\buniversity\b", r"\bcollege\b",
    r"\bschool\b", r"\bpolytechnic\b", r"\binstitute\b", r"\bacademy\b",
    r"\bgpa\b", r"\bcgpa\b", r"\bgraduated\b", r"\bgraduation\b", r"\balumnus\b",
    r"\bcoursework\b", r"\bacademic\b", r"\bcurriculum\b",
]

_EXP_KEYWORDS = [
    r"\bsoftware\s+engineer\b", r"\bdeveloper\b", r"\bprogrammer\b", r"\barchitect\b",
    r"\bmanager\b", r"\bintern\b", r"\binternship\b", r"\banalyst\b", r"\blead\b",
    r"\bdirector\b", r"\bconsultant\b", r"\bspecialist\b", r"\bscientist\b",
    r"\bworked\s+at\b", r"\bemployed\b", r"\bemployment\b", r"\bresponsibilities\b",
    r"\b(?:19|20)\d{2}\s*[-–—to]+\s*(?:(?:19|20)\d{2}|present|current)\b",
    r"\b\d+\+?\s+years?(?:\s+of)?\s+experience\b",
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(?:19|20)\d{2}\b",
]

_PROJ_KEYWORDS = [
    r"\bbuilt\b", r"\bdeveloped\b", r"\bimplemented\b", r"\bgithub\b", r"\bgitlab\b",
    r"\brepository\b", r"\brepo\b", r"\bprojects?\b", r"\bcreated\b", r"\blaunched\b",
    r"\bspearheaded\b", r"\bopen-source\b", r"\bopen\s+source\b", r"\bportfolio\b",
    r"\bprototype\b",
]

_SKILL_KEYWORDS = [
    r"\bskills?\b", r"\btechnologies\b", r"\bproficient\b", r"\bproficiencies\b",
    r"\btech\s+stack\b", r"\bprogramming\s+languages?\b", r"\btools\b",
    r"\bcompetenc(?:y|ies)\b",
]

_OTHER_KEYWORDS = [
    r"\bcontact\b", r"\bemail\b", r"\bphone\b", r"\baddress\b",
    r"\bhobbies\b", r"\binterests\b", r"\breferences\b",
    r"\bcertificat(?:e|ions?)\b", r"\bawards?\b", r"\bhonors?\b",
    r"\bpublications?\b", r"\bvolunteer\b", r"\blanguages?\b",
    r"\bsummary\b", r"\bobjective\b", r"\bsynopsis\b",
]


def _score_fallback_chunk(chunk: str) -> str:
    """Classifies an unformatted chunk into education, experience, projects, skills, or other."""
    c_lower = chunk.lower()
    edu_score = sum(1 for p in _EDU_KEYWORDS if re.search(p, c_lower))
    exp_score = sum(1 for p in _EXP_KEYWORDS if re.search(p, c_lower))
    proj_score = sum(1 for p in _PROJ_KEYWORDS if re.search(p, c_lower))
    skill_score = sum(1 for p in _SKILL_KEYWORDS if re.search(p, c_lower))
    other_score = sum(1 for p in _OTHER_KEYWORDS if re.search(p, c_lower))

    scores = {
        "education": edu_score,
        "experience": exp_score,
        "projects": proj_score,
        "skills": skill_score,
        "other": other_score,
    }
    max_k = max(scores, key=scores.get)
    if scores[max_k] == 0:
        return "other"

    # Disambiguate ties between experience and projects
    if scores["experience"] > 0 and scores["experience"] == scores["projects"]:
        if any(
            re.search(p, c_lower)
            for p in (r"\bsoftware\s+engineer\b", r"\bdeveloper\b", r"\bmanager\b", r"\bintern\b", r"\d{4}\s*[-–—to]\s*(?:\d{4}|present)")
        ):
            return "experience"
    return max_k


def split_resume_sections(text: str) -> dict[str, str]:
    """Splits resume plain text into standard sections.

    Standard sections:
        - 'skills': Technical proficiencies, programming languages, tools.
        - 'experience': Professional work history, roles, employment dates.
        - 'education': Degrees, universities, academic background.
        - 'projects': Key projects, repositories, portfolio items.
        - 'other': Summaries, certifications, awards, contact info, or unclassified text.

    Uses heading detection as the primary strategy. If fewer than 2 standard headings
    are detected (e.g. narrative or unformatted resumes), falls back to a heuristic
    classifier ensuring no text is dropped.

    Args:
        text: Plain text extracted from resume.

    Returns:
        Dict mapping section names to their extracted text content (empty string if missing).
    """
    sections: dict[str, str] = {
        "skills": "",
        "experience": "",
        "education": "",
        "projects": "",
        "other": "",
    }

    if not text or not isinstance(text, str) or not text.strip():
        return sections

    lines = text.splitlines()

    # Detect candidate heading lines
    detected_headings: list[tuple[int, str, str]] = []
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        cleaned = _clean_heading(stripped)
        # Headings are short (1-6 words, <= 45 chars)
        if 1 <= len(cleaned.split()) <= 6 and len(cleaned) <= 45:
            for sec_name, pattern in SECTION_HEADING_PATTERNS.items():
                if pattern.match(cleaned):
                    detected_headings.append((idx, sec_name, stripped))
                    break

    # Primary Strategy: At least 2 standard headings recognized
    if len(detected_headings) >= 2:
        first_heading_idx = detected_headings[0][0]
        if first_heading_idx > 0:
            pre_heading = "\n".join(
                l.strip() for l in lines[:first_heading_idx] if l.strip()
            ).strip()
            if pre_heading:
                sections["other"] = pre_heading

        for i, (start_idx, sec_name, _) in enumerate(detected_headings):
            end_idx = detected_headings[i + 1][0] if i + 1 < len(detected_headings) else len(lines)
            content_lines = [l.strip() for l in lines[start_idx + 1: end_idx] if l.strip()]
            content = "\n".join(content_lines).strip()
            if content:
                if sections[sec_name]:
                    sections[sec_name] += "\n\n" + content
                else:
                    sections[sec_name] = content

        return sections

    # Fallback Mechanism: 0 or 1 headings found (narrative / unformatted text)
    # Break text into chunks (by lines, or by sentences if single block)
    raw_chunks: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # If line contains multiple sentences, split to allow fine-grained classification
        if len(stripped) > 80 and re.search(r"[.!?]\s+[A-Z0-9]", stripped):
            sub_chunks = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", stripped)
            for sc in sub_chunks:
                sc_str = sc.strip()
                if sc_str:
                    raw_chunks.append(sc_str)
        else:
            raw_chunks.append(stripped)

    # Classify each chunk without dropping any text
    classified_chunks: dict[str, list[str]] = {
        "skills": [],
        "experience": [],
        "education": [],
        "projects": [],
        "other": [],
    }

    current_active_section: str | None = None

    for chunk in raw_chunks:
        # Check if the chunk itself is a single heading line
        cleaned_h = _clean_heading(chunk)
        matched_heading_sec = None
        if 1 <= len(cleaned_h.split()) <= 6 and len(cleaned_h) <= 45:
            for sec_name, pattern in SECTION_HEADING_PATTERNS.items():
                if pattern.match(cleaned_h):
                    matched_heading_sec = sec_name
                    break

        if matched_heading_sec:
            current_active_section = matched_heading_sec
            classified_chunks[matched_heading_sec].append(chunk)
        else:
            c_lower = chunk.lower()
            scores = {
                "education": sum(1 for p in _EDU_KEYWORDS if re.search(p, c_lower)),
                "experience": sum(1 for p in _EXP_KEYWORDS if re.search(p, c_lower)),
                "projects": sum(1 for p in _PROJ_KEYWORDS if re.search(p, c_lower)),
                "skills": sum(1 for p in _SKILL_KEYWORDS if re.search(p, c_lower)),
                "other": sum(1 for p in _OTHER_KEYWORDS if re.search(p, c_lower)),
            }
            if scores["experience"] > 0 and scores["experience"] == scores["projects"]:
                if any(
                    re.search(p, c_lower)
                    for p in (r"\bsoftware\s+engineer\b", r"\bdeveloper\b", r"\bmanager\b", r"\bintern\b", r"\d{4}\s*[-–—to]\s*(?:\d{4}|present)")
                ):
                    scores["experience"] += 1

            best_sec = max(scores, key=scores.get)
            best_score = scores[best_sec]

            if current_active_section is not None:
                current_sec_score = scores.get(current_active_section, 0)
                # Switch section if another section clearly scores higher
                if best_score > current_sec_score and best_score > 0 and best_sec != current_active_section:
                    current_active_section = best_sec
                    classified_chunks[best_sec].append(chunk)
                else:
                    classified_chunks[current_active_section].append(chunk)
            else:
                if best_score > 0:
                    current_active_section = best_sec
                    classified_chunks[best_sec].append(chunk)
                else:
                    classified_chunks["other"].append(chunk)

    for sec in sections:
        sections[sec] = "\n".join(classified_chunks[sec]).strip()

    return sections
