"""Comprehensive, opaque-box, requirement-driven E2E test suite for AI-Based Resume Screening System.

Covers:
- Zero-Mock Test Helpers: In-memory PDF 1.4 byte generation and DOCX generation.
- Tier 1: Feature Coverage (R1 Service Layer, R2 Section Splitting & Job Parsing,
          R3 Skill Extraction Edge Cases, R4 4-Component Scoring, R5 Anonymization & Invariance)
- Tier 2: Boundary & Corner Cases (R1-R5 edge/boundary conditions)
- Tier 3: Pairwise Combinatorial Matrix (12 parameterized tests covering 100% of 30 pairs)
- Tier 4: Real-World Multi-Candidate Application Scenarios (5 Workloads)
- Automated Evaluation Invariance Mathematical Proof Tests (4 tests)

Zero-Mock Policy:
- Absolutely NO unittest.mock or @patch for model inference, parsing, or scoring.
- Executes real sentence-transformers inference on CPU.
- Uses genuine in-memory PDF 1.4 and DOCX byte generation.
"""

import io
import math
import os
import re
import statistics
from pathlib import Path
from typing import Any, BinaryIO, Optional, Union

import docx
import numpy as np
import pandas as pd
import pytest

# Configure offline sentence transformers execution
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

# Domain modules (Tier 3 Core Domain & Processing Engines)
from src.anonymizer import anonymize_resume, anonymize_text
from src.job_parser import parse_job_description
from src.parser import extract_text, split_resume_sections
from src.ranker import ResumeRanker
from src.skill_extractor import TechnicalSkillExtractor

# Service layer modules (Tier 2 Service / Application Layer - Milestone M4)
try:
    from src.schemas import (
        CandidateRanking,
        ComponentScores,
        JobAnalysis,
        ParsedResume,
        ResumeSections,
        WeightConfig,
    )
    from src.services.screening_service import analyze_job, parse_resumes, rank

    _SERVICE_LAYER_AVAILABLE = True
    _SERVICE_LAYER_ERROR = None
except ImportError as _err:
    _SERVICE_LAYER_AVAILABLE = False
    _SERVICE_LAYER_ERROR = _err
    JobAnalysis = None
    ResumeSections = None
    ParsedResume = None
    WeightConfig = None
    ComponentScores = None
    CandidateRanking = None
    analyze_job = None
    parse_resumes = None
    rank = None


def _require_service_layer():
    """Validates that the service layer (Milestone M4) is importable before test execution."""
    if not _SERVICE_LAYER_AVAILABLE:
        raise ImportError(
            f"Service layer (Milestone M4) not available: {_SERVICE_LAYER_ERROR}"
        )


# ==============================================================================
# SECTION 0: ZERO-MOCK IN-MEMORY TEST HELPERS
# ==============================================================================

def create_in_memory_docx(
    paragraphs: list[str],
    tables: Optional[list[list[list[str]]]] = None,
) -> io.BytesIO:
    """Generates a valid in-memory DOCX stream with headings, paragraphs, and tables."""
    doc = docx.Document()
    for p in paragraphs:
        if p.startswith("# "):
            doc.add_heading(p[2:], level=1)
        elif p.startswith("## "):
            doc.add_heading(p[3:], level=2)
        elif p.startswith("### "):
            doc.add_heading(p[4:], level=3)
        else:
            doc.add_paragraph(p)
    if tables:
        for tbl_data in tables:
            t = doc.add_table(rows=len(tbl_data), cols=len(tbl_data[0]))
            for r_idx, row in enumerate(tbl_data):
                for c_idx, val in enumerate(row):
                    t.cell(r_idx, c_idx).text = val
    stream = io.BytesIO()
    doc.save(stream)
    stream.seek(0)
    return stream


def create_in_memory_pdf(text_lines: list[str]) -> io.BytesIO:
    """Generates a valid, unmocked PDF 1.4 byte stream containing extractable text."""
    stream_lines = ["BT", "/F1 12 Tf", "16 TL", "72 720 Td"]
    for i, line in enumerate(text_lines):
        safe_line = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if i == 0:
            stream_lines.append(f"({safe_line}) Tj")
        else:
            stream_lines.append("T*")
            stream_lines.append(f"({safe_line}) Tj")
    stream_lines.append("ET")
    stream_content = "\n".join(stream_lines)
    stream_bytes = stream_content.encode("latin-1")
    length = len(stream_bytes)

    pdf_template = (
        f"%PDF-1.4\n"
        f"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        f"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        f"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
        f"4 0 obj << /Length {length} >>\n"
        f"stream\n"
        f"{stream_content}\n"
        f"endstream\n"
        f"endobj\n"
        f"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
        f"xref\n0 6\n"
        f"0000000000 65535 f \n"
        f"0000000010 00000 n \n"
        f"0000000060 00000 n \n"
        f"0000000117 00000 n \n"
        f"0000000250 00000 n \n"
        f"0000000350 00000 n \n"
        f"trailer << /Size 6 /Root 1 0 R >>\n"
        f"startxref\n500\n%%EOF"
    )
    stream = io.BytesIO(pdf_template.encode("latin-1"))
    stream.seek(0)
    return stream


# ==============================================================================
# SECTION 1: TIER 1 - FEATURE COVERAGE (R1 - R5)
# ==============================================================================

# --- R1: Service Layer & Schemas ---

def test_tier1_r1_analyze_job_valid_text():
    """R1: Verifies analyze_job parses required/preferred skills and experience."""
    _require_service_layer()
    jd_text = (
        "Senior Backend Engineer\n\n"
        "Requirements (Must Have):\n"
        "- Hands-on experience with Python and FastAPI\n"
        "- Minimum 4 years of software engineering experience\n\n"
        "Preferred Qualifications (Nice to Have):\n"
        "- Experience with Docker and AWS\n"
        "- Knowledge of PostgreSQL"
    )
    analysis = analyze_job(jd_text)
    assert isinstance(analysis, JobAnalysis)
    assert "Python" in analysis.required_skills
    assert "FastAPI" in analysis.required_skills
    assert "Docker" in analysis.preferred_skills
    assert "AWS" in analysis.preferred_skills
    assert analysis.min_experience_years == 4.0
    assert set(analysis.all_skills) >= {"Python", "FastAPI", "Docker", "AWS", "PostgreSQL"}
    assert len(analysis.cleaned_text) > 0
    assert analysis.raw_text == jd_text


def test_tier1_r1_parse_resumes_file_paths(tmp_path: Path):
    """R1: Verifies parse_resumes parses temporary DOCX and PDF file paths."""
    _require_service_layer()
    docx_file = tmp_path / "candidate_a.docx"
    pdf_file = tmp_path / "candidate_b.pdf"

    docx_stream = create_in_memory_docx(["# Candidate A", "## SKILLS", "Python, FastAPI"])
    docx_file.write_bytes(docx_stream.getvalue())

    pdf_stream = create_in_memory_pdf(["Candidate B", "SKILLS: Docker, AWS"])
    pdf_file.write_bytes(pdf_stream.getvalue())

    parsed_list = parse_resumes([str(docx_file), str(pdf_file)])
    assert len(parsed_list) == 2
    assert all(isinstance(r, ParsedResume) for r in parsed_list)
    assert parsed_list[0].filename == "candidate_a.docx"
    assert parsed_list[1].filename == "candidate_b.pdf"
    assert isinstance(parsed_list[0].sections, ResumeSections)
    assert "Python" in parsed_list[0].raw_text
    assert "Docker" in parsed_list[1].raw_text


def test_tier1_r1_parse_resumes_in_memory_streams():
    """R1: Verifies parse_resumes handles in-memory file streams with filenames."""
    _require_service_layer()
    stream = create_in_memory_docx(["# Alex River", "## SKILLS", "Python, Docker, PostgreSQL"])
    stream.name = "alex_river.docx"

    parsed_list = parse_resumes([stream])
    assert len(parsed_list) == 1
    resume = parsed_list[0]
    assert isinstance(resume, ParsedResume)
    assert resume.filename == "alex_river.docx"
    assert "Python" in resume.raw_text


def test_tier1_r1_rank_with_default_weights():
    """R1: Verifies rank function with default WeightConfig."""
    _require_service_layer()
    jd = analyze_job("Senior Engineer. Required: Python, FastAPI. Preferred: Docker. 4 years exp.")
    cand_a = ParsedResume(
        filename="cand_a.txt",
        raw_text="Python and FastAPI senior developer with 5 years experience.",
        cleaned_text="Python and FastAPI senior developer with 5 years experience.",
        skills=["Python", "FastAPI"],
        experience_years=5.0,
    )
    cand_b = ParsedResume(
        filename="cand_b.txt",
        raw_text="Frontend engineer with Docker and CSS with 2 years experience.",
        cleaned_text="Frontend engineer with Docker and CSS with 2 years experience.",
        skills=["Docker"],
        experience_years=2.0,
    )

    rankings = rank(job=jd, resumes=[cand_a, cand_b], weights=None)
    assert len(rankings) == 2
    assert all(isinstance(r, CandidateRanking) for r in rankings)
    assert rankings[0].rank == 1 and rankings[1].rank == 2
    assert rankings[0].match_score >= rankings[1].match_score
    assert rankings[0].candidate == "cand_a.txt"
    assert isinstance(rankings[0].component_scores, ComponentScores)
    assert rankings[0].component_scores.tfidf_baseline_score is not None


def test_tier1_r1_rank_with_custom_weight_config():
    """R1: Verifies rank function under customized WeightConfig."""
    _require_service_layer()
    jd = analyze_job("Engineer. Required: Python, FastAPI. Preferred: Docker.")
    cand_1 = ParsedResume(
        filename="cand_1.txt",
        raw_text="Python, FastAPI developer.",
        cleaned_text="Python, FastAPI developer.",
        skills=["Python", "FastAPI"],
        experience_years=4.0,
    )
    cand_2 = ParsedResume(
        filename="cand_2.txt",
        raw_text="Docker developer with high semantic similarity to engineer role.",
        cleaned_text="Docker developer with high semantic similarity to engineer role.",
        skills=["Docker"],
        experience_years=4.0,
    )

    weights_heavy_req = WeightConfig(
        required_skill_weight=0.8,
        preferred_skill_weight=0.1,
        semantic_weight=0.05,
        experience_weight=0.05,
    )
    rankings_custom = rank(job=jd, resumes=[cand_1, cand_2], weights=weights_heavy_req)
    rankings_default = rank(job=jd, resumes=[cand_1, cand_2], weights=None)

    score_diff_custom = rankings_custom[0].match_score - rankings_custom[1].match_score
    score_diff_default = rankings_default[0].match_score - rankings_default[1].match_score
    assert score_diff_custom > score_diff_default


def test_tier1_r1_schemas_serialization_and_defaults():
    """R1: Verifies Pydantic v2 schema defaults, validations, and serialization."""
    _require_service_layer()
    wc = WeightConfig()
    assert wc.required_skill_weight == 0.5
    assert wc.preferred_skill_weight == 0.2
    assert wc.semantic_weight == 0.2
    assert wc.experience_weight == 0.1
    assert math.isclose(
        wc.required_skill_weight + wc.preferred_skill_weight + wc.semantic_weight + wc.experience_weight,
        1.0,
    )

    cr = CandidateRanking(
        rank=1,
        candidate="Alice",
        match_score=88.5,
        component_scores=ComponentScores(
            required_skill_score=1.0,
            preferred_skill_score=0.5,
            semantic_score=0.8,
            experience_score=1.0,
            tfidf_baseline_score=0.75,
        ),
        matched_skills=["Python", "FastAPI"],
        missing_skills=[],
        matched_required_skills=["Python", "FastAPI"],
        matched_preferred_skills=[],
        missing_required_skills=[],
    )
    dumped = cr.model_dump()
    assert dumped["candidate"] == "Alice"
    assert dumped["match_score"] == 88.5
    validated = CandidateRanking.model_validate(dumped)
    assert validated.candidate == "Alice"


# --- R2: Resume Section Splitting & Job Parsing ---

def test_tier1_r2_split_sections_standard_headings():
    """R2: Verifies splitting resume text with standard headings."""
    text = (
        "ALICE DEVELOPER\n\n"
        "SKILLS\nPython, Docker, FastAPI, PostgreSQL\n\n"
        "EXPERIENCE\nSenior Engineer at Tech Corp (2020-2024)\nDeveloped microservices.\n\n"
        "EDUCATION\nBachelor of Science in Computer Science, State University\n\n"
        "PROJECTS\nOpen-source distributed cache system."
    )
    sections = split_resume_sections(text)
    assert isinstance(sections, dict)
    assert set(sections.keys()) >= {"skills", "experience", "education", "projects", "other"}
    assert "Python, Docker" in sections["skills"]
    assert "Tech Corp" in sections["experience"]
    assert "State University" in sections["education"]
    assert "distributed cache" in sections["projects"]


def test_tier1_r2_split_sections_heading_synonyms():
    """R2: Verifies splitting resume text using synonym section headings."""
    text = (
        "CORE COMPETENCIES\nGo, Kubernetes, AWS\n\n"
        "WORK HISTORY\nLead Architect at Cloud Inc (2019-2023)\n\n"
        "ACADEMIC BACKGROUND\nMS in Software Engineering\n\n"
        "KEY PROJECTS\nCloud-native orchestration engine."
    )
    sections = split_resume_sections(text)
    assert "Go, Kubernetes, AWS" in sections["skills"]
    assert "Cloud Inc" in sections["experience"]
    assert "Software Engineering" in sections["education"]
    assert "orchestration engine" in sections["projects"]


def test_tier1_r2_job_parse_required_cue_phrases():
    """R2: Verifies job parsing identifies required skills via cue phrases."""
    text = (
        "Software Engineer Position\n"
        "Requirements (Must Have):\n"
        "- Hands-on proficiency with Python and PostgreSQL\n"
        "- Minimum qualifications: Experience with Docker containers"
    )
    parsed = parse_job_description(text)
    assert "Python" in parsed["required_skills"]
    assert "PostgreSQL" in parsed["required_skills"]
    assert "Docker" in parsed["required_skills"]
    assert "Docker" not in parsed.get("preferred_skills", [])


def test_tier1_r2_job_parse_preferred_cue_phrases():
    """R2: Verifies job parsing identifies preferred skills via cue phrases."""
    text = (
        "Backend Engineer\n"
        "Required Skills:\n"
        "- Python\n"
        "Preferred Qualifications:\n"
        "- Kubernetes and Terraform\n"
        "- Bonus points: Experience with GraphQL"
    )
    parsed = parse_job_description(text)
    assert "Python" in parsed["required_skills"]
    assert "Kubernetes" in parsed["preferred_skills"]
    assert "Terraform" in parsed["preferred_skills"]
    assert "GraphQL" in parsed["preferred_skills"]
    assert "Kubernetes" not in parsed["required_skills"]


def test_tier1_r2_job_parse_experience_years_extraction():
    """R2: Verifies experience years extraction from job description text."""
    text = (
        "Senior Staff Engineer\n"
        "Qualifications:\n"
        "- Must have at least 5+ years of hands-on experience building backend systems."
    )
    parsed = parse_job_description(text)
    assert parsed["min_experience_years"] == 5.0


def test_tier1_r2_extract_text_docx_tables_and_sections():
    """R2: Verifies DOCX extraction and section splitting over tables and text."""
    stream = create_in_memory_docx(
        paragraphs=["# Jane Doe", "## EXPERIENCE", "Backend Engineer for 4 years."],
        tables=[[["Frontend", "React, TypeScript"], ["Backend", "Python, Django"]]],
    )
    text = extract_text(stream, filename="resume.docx")
    assert len(text) > 0
    assert "React" in text and "TypeScript" in text
    assert "Python" in text and "Django" in text
    sections = split_resume_sections(text)
    assert len(sections["experience"]) > 0 or len(sections["skills"]) > 0


# --- R3: Skill Extraction Edge Cases ---

def test_tier1_r3_cpp_and_csharp_subspan_resolution():
    """R3: Verifies C++ and C# are matched and sub-span 'C' is filtered."""
    extractor = TechnicalSkillExtractor()
    skills = extractor.extract_skills("Proficient in C++ and C# system programming.")
    assert "C++" in skills
    assert "C#" in skills
    assert "C" not in skills


def test_tier1_r3_dotnet_and_nodejs_variations():
    """R3: Verifies .NET and Node.js variations are extracted accurately."""
    extractor = TechnicalSkillExtractor()
    skills = extractor.extract_skills("Experienced in .NET microservices and Node.js backend development.")
    assert ".NET" in skills
    assert "Node.js" in skills


def test_tier1_r3_single_letter_r_standalone():
    """R3: Verifies standalone uppercase 'R' matches as a programming language."""
    extractor = TechnicalSkillExtractor()
    skills = extractor.extract_skills("Data Scientist proficient in Python, R, and SQL for statistical analysis.")
    assert "R" in skills
    assert "Python" in skills
    assert "SQL" in skills


def test_tier1_r3_java_vs_javascript_disambiguation():
    """R3: Verifies JavaScript does not falsely match Java."""
    extractor = TechnicalSkillExtractor()
    skills_js = extractor.extract_skills("Frontend specialist working with JavaScript and React.")
    assert "JavaScript" in skills_js
    assert "Java" not in skills_js

    skills_java = extractor.extract_skills("Backend architect designing microservices in Java and Spring Boot.")
    assert "Java" in skills_java
    assert "JavaScript" not in skills_java


def test_tier1_r3_alias_normalization():
    """R3: Verifies skill aliases are normalized to canonical taxonomy names."""
    extractor = TechnicalSkillExtractor()
    skills = extractor.extract_skills("Tech stack: JS, TS, K8s, NodeJS, and Postgres.")
    assert "JavaScript" in skills and "JS" not in skills
    assert "TypeScript" in skills and "TS" not in skills
    assert "Kubernetes" in skills and "K8s" not in skills
    assert "Node.js" in skills and "NodeJS" not in skills
    assert "PostgreSQL" in skills and "Postgres" not in skills


def test_tier1_r3_plural_normalization():
    """R3: Verifies plural nouns are mapped to canonical singular/plural skills."""
    extractor = TechnicalSkillExtractor()
    skills = extractor.extract_skills("Automated deployments with Dockers and designed REST APIs for Microservices.")
    assert "Docker" in skills
    assert "Microservices" in skills
    assert any(s in skills for s in ["REST API", "RESTful APIs"])


# --- R4: 4-Component Scoring & TF-IDF Cosine Baseline ---

def test_tier1_r4_four_component_score_calculation():
    """R4: Verifies the 4-component weighted scoring formula."""
    _require_service_layer()
    jd = analyze_job(
        "Backend Engineer.\nRequired: Python, Docker.\nPreferred: AWS, Kubernetes.\nMin 4 years exp."
    )
    cand = ParsedResume(
        filename="cand.txt",
        raw_text="Experienced engineer in Python and AWS with 4 years software development.",
        cleaned_text="Experienced engineer in Python and AWS with 4 years software development.",
        skills=["Python", "AWS"],
        experience_years=4.0,
    )
    weights = WeightConfig(
        required_skill_weight=0.5,
        preferred_skill_weight=0.2,
        semantic_weight=0.2,
        experience_weight=0.1,
    )
    rankings = rank(job=jd, resumes=[cand], weights=weights)
    assert len(rankings) == 1
    r = rankings[0]
    # Required: 1/2 = 0.5, Preferred: 1/2 = 0.5, Experience: 4/4 = 1.0
    assert r.component_scores.required_skill_score == 0.5
    assert r.component_scores.preferred_skill_score == 0.5
    assert r.component_scores.experience_score == 1.0

    expected_score = round(
        (0.5 * 0.5 + 0.2 * 0.5 + 0.2 * r.component_scores.semantic_score + 0.1 * 1.0) * 100,
        2,
    )
    assert abs(r.match_score - expected_score) <= 0.05


def test_tier1_r4_tfidf_baseline_computation():
    """R4: Verifies TF-IDF baseline computation is present in component scores."""
    _require_service_layer()
    jd = analyze_job("Senior Python and Docker Architect building distributed services.")
    cand1 = ParsedResume(
        filename="c1.txt",
        raw_text="Python and Docker architect building cloud services.",
        cleaned_text="Python and Docker architect building cloud services.",
        skills=["Python", "Docker"],
        experience_years=5.0,
    )
    cand2 = ParsedResume(
        filename="c2.txt",
        raw_text="PHP and MySQL frontend web developer.",
        cleaned_text="PHP and MySQL frontend web developer.",
        skills=["PHP", "MySQL"],
        experience_years=2.0,
    )
    rankings = rank(job=jd, resumes=[cand1, cand2])
    assert all(r.component_scores.tfidf_baseline_score is not None for r in rankings)
    assert all(0.0 <= r.component_scores.tfidf_baseline_score <= 1.0 for r in rankings)
    assert rankings[0].component_scores.tfidf_baseline_score > rankings[1].component_scores.tfidf_baseline_score


def test_tier1_r4_ranking_order_descending():
    """R4: Verifies ranking results are strictly ordered in descending match score."""
    _require_service_layer()
    jd = analyze_job("Engineer. Required: Python, Docker. Preferred: AWS. 5 years exp.")
    strong = ParsedResume(
        filename="strong.txt",
        raw_text="Senior engineer with Python, Docker, and AWS. 5 years experience.",
        cleaned_text="Senior engineer with Python, Docker, and AWS. 5 years experience.",
        skills=["Python", "Docker", "AWS"],
        experience_years=5.0,
    )
    medium = ParsedResume(
        filename="medium.txt",
        raw_text="Developer with Python and 2 years experience.",
        cleaned_text="Developer with Python and 2 years experience.",
        skills=["Python"],
        experience_years=2.0,
    )
    weak = ParsedResume(
        filename="weak.txt",
        raw_text="Graphic designer focusing on marketing brochures.",
        cleaned_text="Graphic designer focusing on marketing brochures.",
        skills=[],
        experience_years=1.0,
    )
    rankings = rank(job=jd, resumes=[weak, strong, medium])
    assert [r.candidate for r in rankings] == ["strong.txt", "medium.txt", "weak.txt"]
    assert [r.rank for r in rankings] == [1, 2, 3]
    assert rankings[0].match_score > rankings[1].match_score > rankings[2].match_score


def test_tier1_r4_missing_required_skills_output():
    """R4: Verifies missing required skills are explicitly reported."""
    _require_service_layer()
    jd = analyze_job("Backend Lead. Required: Python, FastAPI, PostgreSQL.")
    cand = ParsedResume(
        filename="alice.txt",
        raw_text="Developer with Python experience.",
        cleaned_text="Developer with Python experience.",
        skills=["Python"],
        experience_years=3.0,
    )
    rankings = rank(job=jd, resumes=[cand])
    r = rankings[0]
    assert set(r.matched_required_skills) == {"Python"}
    assert set(r.missing_required_skills) == {"FastAPI", "PostgreSQL"}
    assert set(r.missing_skills) == {"FastAPI", "PostgreSQL"}


def test_tier1_r4_custom_weight_configuration_impact():
    """R4: Verifies impact of custom weight shifts between skill and semantic weights."""
    _require_service_layer()
    jd = analyze_job("Python and PostgreSQL Engineer.")
    cand = ParsedResume(
        filename="dev.txt",
        raw_text="Python and PostgreSQL engineer.",
        cleaned_text="Python and PostgreSQL engineer.",
        skills=["Python", "PostgreSQL"],
        experience_years=3.0,
    )
    weights_skill_heavy = WeightConfig(required_skill_weight=0.9, preferred_skill_weight=0.0, semantic_weight=0.05, experience_weight=0.05)
    weights_sem_heavy = WeightConfig(required_skill_weight=0.1, preferred_skill_weight=0.0, semantic_weight=0.85, experience_weight=0.05)

    r_skill = rank(job=jd, resumes=[cand], weights=weights_skill_heavy)[0]
    r_sem = rank(job=jd, resumes=[cand], weights=weights_sem_heavy)[0]

    # Required skills match 100% (1.0), so 90% weighting yields higher score than 10%
    assert r_skill.match_score >= r_sem.match_score


def test_tier1_r4_legacy_dataframe_compatibility():
    """R4: Verifies backward compatibility of ResumeRanker returning 7-column DataFrame."""
    ranker = ResumeRanker()
    jd = "Python and Docker engineer."
    candidates = [
        {"name": "Alice.pdf", "text": "Python and Docker engineer with 5 years exp.", "skills": ["Python", "Docker"]},
        {"name": "Bob.docx", "text": "Junior developer with HTML.", "skills": []},
    ]
    df = ranker.rank_candidates(jd, candidates)
    assert isinstance(df, pd.DataFrame)
    expected_cols = [
        "rank",
        "candidate",
        "match_score",
        "semantic_score",
        "skill_overlap_score",
        "matched_skills",
        "missing_skills",
    ]
    assert list(df.columns) == expected_cols
    assert len(df) == 2


# --- R5: Candidate Anonymization & Evaluation Invariance ---

def test_tier1_r5_anonymize_email_formats():
    """R5: Verifies email formats are redacted to [EMAIL]."""
    text = "Contact alex.smith@domain.com or engineer_12@sub.co.org for inquiries."
    sanitized = anonymize_text(text)
    assert "alex.smith@domain.com" not in sanitized
    assert "engineer_12@sub.co.org" not in sanitized
    assert "[EMAIL]" in sanitized


def test_tier1_r5_anonymize_phone_numbers():
    """R5: Verifies phone numbers are redacted to [PHONE]."""
    text = "Call +1 (555) 234-5678 or reach mobile at 555-876-5432."
    sanitized = anonymize_text(text)
    assert "+1 (555) 234-5678" not in sanitized
    assert "555-876-5432" not in sanitized
    assert "[PHONE]" in sanitized


def test_tier1_r5_anonymize_candidate_name():
    """R5: Verifies candidate names are redacted to [NAME]."""
    text = "Johnathan Doe is a senior architect. Johnathan Doe developed FastAPI apps."
    sanitized = anonymize_text(text, candidate_name="Johnathan Doe")
    assert "Johnathan Doe" not in sanitized
    assert "[NAME]" in sanitized


def test_tier1_r5_anonymize_pronouns():
    """R5: Verifies gendered pronouns are neutralized to [PRONOUN]."""
    text = "She architected the infrastructure. He tested the service. Her leadership was recognized by him."
    sanitized = anonymize_text(text)
    assert not re.search(r"\b(he|she|him|her)\b", sanitized, re.IGNORECASE)
    assert "[PRONOUN]" in sanitized


def test_tier1_r5_anonymize_resume_dict():
    """R5: Verifies anonymize_resume produces an anonymized dictionary copy."""
    resume_dict = {
        "name": "Jane Smith",
        "raw_text": "Jane Smith: jane@test.com, (555) 123-4567. She knows Python.",
        "sections": {"experience": "Jane worked at Acme. Her code was stellar."},
    }
    sanitized_dict = anonymize_resume(resume_dict)
    assert "anonymized_text" in sanitized_dict
    assert "jane@test.com" not in sanitized_dict["anonymized_text"]
    assert "(555) 123-4567" not in sanitized_dict["anonymized_text"]
    assert "Jane Smith" not in sanitized_dict["anonymized_text"]
    assert sanitized_dict is not resume_dict


def test_tier1_r5_evaluation_invariance_male_vs_female():
    """R5: Proves evaluation invariance between male and female demographic identities."""
    _require_service_layer()
    jd = analyze_job("Senior Engineer. 5 years exp. Required: Python, Docker, FastAPI, PostgreSQL.")
    base_text = (
        "{name}\nEmail: {email} | Phone: {phone}\n"
        "EXPERIENCE\n{pronoun} has 5 years experience with Python, Docker, FastAPI, and PostgreSQL.\n"
        "SKILLS\nPython, Docker, FastAPI, PostgreSQL\n"
    )

    text_m = base_text.format(name="David Miller", email="david.miller@example.com", phone="555-0101", pronoun="He")
    text_f = base_text.format(name="Fatima Al-Mansoor", email="fatima.almansoor@example.com", phone="555-0202", pronoun="She")

    anon_m = anonymize_text(text_m, candidate_name="David Miller")
    anon_f = anonymize_text(text_f, candidate_name="Fatima Al-Mansoor")

    res_m = ParsedResume(filename="male.txt", raw_text=text_m, cleaned_text=anon_m, experience_years=5.0)
    res_f = ParsedResume(filename="female.txt", raw_text=text_f, cleaned_text=anon_f, experience_years=5.0)

    rankings = rank(job=jd, resumes=[res_m, res_f])
    score_a = rankings[0].match_score
    score_b = rankings[1].match_score
    assert abs(score_a - score_b) == 0.0
    assert rankings[0].component_scores.model_dump() == rankings[1].component_scores.model_dump()


# ==============================================================================
# SECTION 2: TIER 2 - BOUNDARY & CORNER CASES (R1 - R5)
# ==============================================================================

# --- R1 Boundary & Corner Cases ---

def test_tier2_r1_analyze_job_empty_and_whitespace():
    """R1 Boundary: Verifies analyze_job handles empty and whitespace strings safely."""
    _require_service_layer()
    res1 = analyze_job("")
    res2 = analyze_job("   \n\t   ")
    assert isinstance(res1, JobAnalysis)
    assert res1.required_skills == []
    assert res1.preferred_skills == []
    assert res1.all_skills == []
    assert res1.min_experience_years is None
    assert isinstance(res2, JobAnalysis)
    assert res2.required_skills == []


def test_tier2_r1_parse_resumes_empty_list():
    """R1 Boundary: Verifies parse_resumes handles empty list."""
    _require_service_layer()
    assert parse_resumes([]) == []


def test_tier2_r1_parse_resumes_malformed_stream():
    """R1 Corner: Verifies parse_resumes raises ValueError on corrupted stream."""
    _require_service_layer()
    corrupted = io.BytesIO(b"NOT_A_VALID_HEADER_OR_DOCX_OR_PDF")
    corrupted.name = "corrupt.pdf"
    with pytest.raises(ValueError):
        parse_resumes([corrupted])


def test_tier2_r1_rank_empty_resumes():
    """R1 Boundary: Verifies rank handles empty resume candidate list."""
    _require_service_layer()
    jd = analyze_job("Software Engineer Python")
    assert rank(job=jd, resumes=[]) == []


def test_tier2_r1_rank_zero_weights():
    """R1 Corner: Verifies all zero weights do not cause ZeroDivisionError."""
    _require_service_layer()
    jd = analyze_job("Engineer. Required: Python, Docker.")
    cand = ParsedResume(
        filename="cand.txt",
        raw_text="Python and Docker developer.",
        cleaned_text="Python and Docker developer.",
        skills=["Python", "Docker"],
        experience_years=3.0,
    )
    zero_weights = WeightConfig(
        required_skill_weight=0.0,
        preferred_skill_weight=0.0,
        semantic_weight=0.0,
        experience_weight=0.0,
    )
    rankings = rank(job=jd, resumes=[cand], weights=zero_weights)
    assert len(rankings) == 1
    assert rankings[0].match_score == 0.0
    assert rankings[0].component_scores.required_skill_score == 1.0


def test_tier2_r1_weight_config_validation_bounds():
    """R1 Validation: Verifies WeightConfig rejects negative or out-of-range weights."""
    _require_service_layer()
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        WeightConfig(required_skill_weight=-0.1)
    with pytest.raises(ValidationError):
        WeightConfig(semantic_weight=1.5)


# --- R2 Boundary & Corner Cases ---

def test_tier2_r2_split_sections_empty_string():
    """R2 Boundary: Verifies section splitting on empty string returns empty dictionary."""
    sections = split_resume_sections("")
    assert isinstance(sections, dict)
    assert all(sections[k] == "" for k in ["skills", "experience", "education", "projects", "other"])


def test_tier2_r2_split_sections_zero_headings_fallback():
    """R2 Fallback: Verifies 0 headings narrative resume activates heuristic fallback."""
    narrative = (
        "I am a software engineer with 6 years of experience building microservices. "
        "I graduated from Stanford University with a Bachelor of Science in Computer Science. "
        "My core competencies include Python, Go, and Kubernetes. "
        "Recently, I created an open-source analytics platform."
    )
    sections = split_resume_sections(narrative)
    assert isinstance(sections, dict)
    total_preserved = " ".join(sections.values())
    assert len(total_preserved) >= len(narrative) * 0.85
    assert "Stanford" in sections["education"] or "Bachelor" in sections["education"]
    assert "software engineer" in sections["experience"]
    assert "Python" in total_preserved


def test_tier2_r2_split_sections_single_heading():
    """R2 Fallback: Verifies single heading resume retains all text without truncation."""
    single_heading_text = (
        "SKILLS\nPython, Docker, AWS\n\n"
        "Worked at Google for 4 years managing cloud infrastructure. "
        "Holds a degree in Mathematics from Oxford."
    )
    sections = split_resume_sections(single_heading_text)
    total_preserved = " ".join(sections.values())
    assert "SKILLS" in sections["skills"] or "Python, Docker, AWS" in sections["skills"]
    assert "Google" in sections["experience"]
    assert "Oxford" in sections["education"]
    assert "Python, Docker, AWS" in total_preserved


def test_tier2_r2_job_parse_no_cue_phrases():
    """R2 Boundary: Verifies job parsing defaults skills to required when no cue phrases exist."""
    flat_jd = "Looking for a software engineer proficient in Python, Docker, and PostgreSQL."
    parsed = parse_job_description(flat_jd)
    assert set(parsed["required_skills"]) >= {"Python", "Docker", "PostgreSQL"}
    assert parsed["preferred_skills"] == []
    assert parsed["min_experience_years"] is None


def test_tier2_r2_split_sections_noisy_markdown_headings():
    """R2 Corner: Verifies noisy headers (markdown hashes, equal signs, colons) are parsed."""
    noisy_text = (
        "### TECHNICAL SKILLS: ###\nPython, Redis\n\n"
        "=== PROFESSIONAL EXPERIENCE ===:\nDeveloped backend APIs.\n\n"
        "** ACADEMIC BACKGROUND **\nBS in Computer Engineering"
    )
    sections = split_resume_sections(noisy_text)
    assert "Python, Redis" in sections["skills"]
    assert "Developed backend APIs" in sections["experience"]
    assert "BS in Computer Engineering" in sections["education"]


def test_tier2_r2_job_parse_decimal_and_range_experience():
    """R2 Corner: Verifies experience range with decimals extracts the minimum bound."""
    text = "Candidate must have 3.5 to 5 years of commercial software experience."
    parsed = parse_job_description(text)
    assert parsed["min_experience_years"] == 3.5


# --- R3 Boundary & Corner Cases ---

def test_tier2_r3_single_letter_r_false_positive_rejection():
    """R3 Boundary: Verifies 'R' in R&D or 'Toys R Us' is rejected."""
    extractor = TechnicalSkillExtractor()
    skills = extractor.extract_skills("Managed R&D initiatives at Toys R Us. Evaluated R-squared statistical metrics.")
    assert "R" not in skills


def test_tier2_r3_standalone_c_language():
    """R3 Boundary: Verifies standalone 'C' language matches without triggering C++ or C#."""
    extractor = TechnicalSkillExtractor()
    skills = extractor.extract_skills("Embedded firmware programming in C and Linux device driver development.")
    assert "C" in skills
    assert "C++" not in skills
    assert "C#" not in skills


def test_tier2_r3_punctuation_boundary_conditions():
    """R3 Corner: Verifies skills with punctuation (.NET, Node.js, C#, C++) strip trailing punctuation."""
    extractor = TechnicalSkillExtractor()
    skills = extractor.extract_skills("Key tools: C++, C#, .NET, and Node.js.")
    assert "C++" in skills
    assert "C#" in skills
    assert ".NET" in skills
    assert "Node.js" in skills
    assert not any(s.endswith((".", ",")) for s in skills)


def test_tier2_r3_empty_and_no_skills_text():
    """R3 Boundary: Verifies text with zero technical skills returns empty list."""
    extractor = TechnicalSkillExtractor()
    skills = extractor.extract_skills("Responsible for greeting visitors, filing documents in folders, and ordering supplies.")
    assert skills == []


def test_tier2_r3_casing_variations_dotnet_and_nodejs():
    """R3 Corner: Verifies casing variations of Node.js and .NET are recognized."""
    extractor = TechnicalSkillExtractor()
    skills = extractor.extract_skills("Built services using nodejs, Node.JS, DOTNET, .net core, and c#.")
    assert "Node.js" in skills
    assert any(s in skills for s in [".NET", ".NET Core"])
    assert "C#" in skills


def test_tier2_r3_case_sensitive_single_r_guard():
    """R3 Corner: Verifies lowercase 'r' does not falsely match language 'R'."""
    extractor = TechnicalSkillExtractor()
    skills = extractor.extract_skills("The letter r is common in regular expressions, but R is a language.")
    assert "R" in skills
    # Count occurrences of 'R'
    assert skills.count("R") == 1


# --- R4 Boundary & Corner Cases ---

def test_tier2_r4_candidate_zero_skills():
    """R4 Boundary: Verifies candidate with zero matching skills produces 0.0 skill scores."""
    _require_service_layer()
    jd = analyze_job("Engineer. Required: Python, FastAPI.")
    cand = ParsedResume(
        filename="admin.txt",
        raw_text="Administrative assistant filing paper documents.",
        cleaned_text="Administrative assistant filing paper documents.",
        skills=[],
        experience_years=1.0,
    )
    rankings = rank(job=jd, resumes=[cand])
    assert len(rankings) == 1
    r = rankings[0]
    assert r.component_scores.required_skill_score == 0.0
    assert r.component_scores.preferred_skill_score == 0.0
    assert r.matched_skills == []
    assert set(r.missing_required_skills) == {"Python", "FastAPI"}
    assert r.match_score >= 0.0


def test_tier2_r4_candidate_all_skills_and_excess_experience():
    """R4 Corner: Verifies candidate with 100% skills and excess experience caps components at 1.0."""
    _require_service_layer()
    jd = analyze_job("Engineer. Required: Python, Docker. Preferred: AWS. Min 3 years exp.")
    cand = ParsedResume(
        filename="expert.txt",
        raw_text="Python, Docker, and AWS expert with 10 years experience.",
        cleaned_text="Python, Docker, and AWS expert with 10 years experience.",
        skills=["Python", "Docker", "AWS"],
        experience_years=10.0,
    )
    rankings = rank(job=jd, resumes=[cand])
    r = rankings[0]
    assert r.component_scores.required_skill_score == 1.0
    assert r.component_scores.preferred_skill_score == 1.0
    assert r.component_scores.experience_score == 1.0
    assert r.missing_required_skills == []


def test_tier2_r4_job_has_zero_skills():
    """R4 Boundary: Verifies JD with zero technical skills handles scoring without ZeroDivisionError."""
    _require_service_layer()
    jd = analyze_job("Energetic communicator needed for dynamic startup environment.")
    cand = ParsedResume(
        filename="c.txt",
        raw_text="Energetic communicator with great enthusiasm.",
        cleaned_text="Energetic communicator with great enthusiasm.",
        skills=[],
        experience_years=2.0,
    )
    rankings = rank(job=jd, resumes=[cand])
    assert len(rankings) == 1
    assert rankings[0].match_score >= 0.0


def test_tier2_r4_zero_weights_all_components():
    """R4 Corner: Verifies zero weights produce 0.0 match_score for all candidates."""
    _require_service_layer()
    jd = analyze_job("Python Developer.")
    cand = ParsedResume(filename="c.txt", raw_text="Python developer.", cleaned_text="Python developer.", skills=["Python"], experience_years=3.0)
    zero_weights = WeightConfig(required_skill_weight=0.0, preferred_skill_weight=0.0, semantic_weight=0.0, experience_weight=0.0)
    rankings = rank(job=jd, resumes=[cand], weights=zero_weights)
    assert rankings[0].match_score == 0.0
    assert isinstance(rankings[0].component_scores, ComponentScores)


def test_tier2_r4_empty_candidate_text():
    """R4 Boundary: Verifies candidate with empty text scores 0.0 without crash."""
    _require_service_layer()
    jd = analyze_job("Python Developer.")
    empty_cand = ParsedResume(filename="empty.txt", raw_text="", cleaned_text="", skills=[], experience_years=0.0)
    valid_cand = ParsedResume(filename="valid.txt", raw_text="Python developer.", cleaned_text="Python developer.", skills=["Python"], experience_years=3.0)

    rankings = rank(job=jd, resumes=[empty_cand, valid_cand])
    empty_r = [r for r in rankings if r.candidate == "empty.txt"][0]
    assert empty_r.match_score == 0.0
    assert empty_r.component_scores.semantic_score == 0.0
    assert empty_r.component_scores.tfidf_baseline_score == 0.0
    assert empty_r.rank == 2


def test_tier2_r4_identical_job_and_candidate_text():
    """R4 Corner: Verifies identical candidate and JD text yields near-perfect scores (>=0.99)."""
    _require_service_layer()
    text = "Senior Python and FastAPI Backend Engineer with Docker and PostgreSQL expertise."
    jd = analyze_job(text)
    cand = ParsedResume(filename="identical.txt", raw_text=text, cleaned_text=text, skills=["Python", "FastAPI", "Docker", "PostgreSQL"], experience_years=5.0)

    rankings = rank(job=jd, resumes=[cand])
    r = rankings[0]
    assert r.component_scores.semantic_score >= 0.99
    assert r.component_scores.tfidf_baseline_score >= 0.99
    assert r.component_scores.required_skill_score == 1.0


# --- R5 Boundary & Corner Cases ---

def test_tier2_r5_pronouns_inside_words_not_corrupted():
    """R5 Regex Boundary: Verifies pronouns inside words (hero, theme, adhered) are not corrupted."""
    text = "The hero theme adhered to the schema without hesitation. He liked their stylesheet."
    sanitized = anonymize_text(text)
    assert "hero" in sanitized
    assert "theme" in sanitized
    assert "adhered" in sanitized
    assert "schema" in sanitized
    assert "hesitation" in sanitized
    assert "stylesheet" in sanitized
    assert "He" not in sanitized


def test_tier2_r5_no_pii_clean_text():
    """R5 Boundary: Verifies text without PII is unchanged by anonymization."""
    text = "Experienced backend developer specializing in distributed systems, PostgreSQL, and Linux."
    sanitized = anonymize_text(text)
    assert sanitized == text


def test_tier2_r5_candidate_name_colliding_with_skill():
    """R5 Corner: Verifies redacting candidate name 'Ruby Miller' preserves technical skill 'Ruby'."""
    text = "Ruby Miller is a Senior Ruby on Rails developer with deep expertise in Ruby and PostgreSQL."
    sanitized = anonymize_text(text, candidate_name="Ruby Miller")
    assert "Ruby Miller" not in sanitized
    extractor = TechnicalSkillExtractor()
    skills = extractor.extract_skills(sanitized)
    assert "Ruby" in skills


def test_tier2_r5_international_phone_and_tagged_emails():
    """R5 Corner: Verifies international phones and tagged emails are redacted."""
    text = (
        "Contact: candidate+tag.99@sub.engineering.ac.uk\n"
        "UK Phone: +44 20 7946 0958\n"
        "India Phone: +91-98765-43210\n"
        "US Phone: (800) 555-0199 ext. 12"
    )
    sanitized = anonymize_text(text)
    assert "candidate+tag.99@sub.engineering.ac.uk" not in sanitized
    assert "+44 20 7946 0958" not in sanitized
    assert "+91-98765-43210" not in sanitized
    assert "[EMAIL]" in sanitized
    assert "[PHONE]" in sanitized


def test_tier2_r5_multi_demographic_score_invariance():
    """R5 Invariance: Verifies zero variance across 5 ethnic and cultural identities."""
    _require_service_layer()
    jd = analyze_job("Software Engineer. Required: Python, Docker, FastAPI. 5 years exp.")
    template = (
        "{name}\nEmail: {email} | Phone: {phone}\n"
        "EXPERIENCE\n{pronoun} has 5 years experience with Python, Docker, and FastAPI.\n"
        "SKILLS\nPython, Docker, FastAPI\n"
    )
    demographics = [
        {"name": "Liam O'Connor", "email": "liam@example.ie", "phone": "+353 1 234 5678", "pronoun": "He"},
        {"name": "Priya Sharma", "email": "priya@example.in", "phone": "+91 98765 43210", "pronoun": "She"},
        {"name": "Wei Zhang", "email": "wei@example.cn", "phone": "+86 10 1234 5678", "pronoun": "He"},
        {"name": "Fatima Al-Mansoor", "email": "fatima@example.ae", "phone": "+971 4 123 4567", "pronoun": "She"},
        {"name": "Kwame Mensah", "email": "kwame@example.gh", "phone": "+233 20 123 4567", "pronoun": "He"},
    ]

    resumes = []
    for i, d in enumerate(demographics):
        raw = template.format(**d)
        anon = anonymize_text(raw, candidate_name=d["name"])
        resumes.append(ParsedResume(filename=f"cand_{i}.txt", raw_text=raw, cleaned_text=anon, experience_years=5.0))

    rankings = rank(job=jd, resumes=resumes)
    scores = [r.match_score for r in rankings]
    assert len(set(scores)) == 1
    assert statistics.variance(scores) == 0.0


def test_tier2_r5_case_insensitive_pronoun_neutralization():
    """R5 Corner: Verifies uppercase and lowercase pronouns are neutralized."""
    text = "SHE led the sprint. HE managed deployments. HER designs were approved. HIS tests passed."
    sanitized = anonymize_text(text)
    assert not re.search(r"\b(she|he|her|his)\b", sanitized, re.IGNORECASE)


# ==============================================================================
# SECTION 3: TIER 3 - PAIRWISE COMBINATORIAL TEST SUITE (12 COMBINATIONS)
# ==============================================================================

@pytest.mark.parametrize(
    "test_id,file_format,skill_type,weight_type,section_format",
    [
        ("TC-P01", "pdf", "standard", "default", "headings"),
        ("TC-P02", "pdf", "edge", "custom", "fallback"),
        ("TC-P03", "pdf", "standard", "custom", "fallback"),
        ("TC-P04", "pdf", "edge", "default", "headings"),
        ("TC-P05", "docx", "standard", "custom", "headings"),
        ("TC-P06", "docx", "edge", "default", "fallback"),
        ("TC-P07", "docx", "standard", "default", "fallback"),
        ("TC-P08", "docx", "edge", "custom", "headings"),
        ("TC-P09", "text", "standard", "default", "fallback"),
        ("TC-P10", "text", "edge", "custom", "headings"),
        ("TC-P11", "text", "standard", "custom", "headings"),
        ("TC-P12", "text", "edge", "default", "fallback"),
    ],
)
def test_tier3_pairwise_combinatorial_execution(
    test_id: str,
    file_format: str,
    skill_type: str,
    weight_type: str,
    section_format: str,
):
    """Tier 3: Executes unmocked pairwise combination covering 100% of 30 factor pairs."""
    _require_service_layer()

    # 1. Job Description Setup
    if skill_type == "standard":
        jd_text = (
            "Senior Backend Engineer. Must have 5 years experience. "
            "Required: Python, Docker, PostgreSQL. Preferred: AWS, Git."
        )
        expected_req = ["Python", "Docker", "PostgreSQL"]
    else:
        jd_text = (
            "Senior Systems Engineer. Must have 4 years experience. "
            "Required: C#, C++, Node.js, R. Preferred: .NET, Kubernetes."
        )
        expected_req = ["C#", "C++", "Node.js", "R"]

    job_analysis = analyze_job(jd_text)
    for skill in expected_req:
        assert any(skill.lower() == s.lower() for s in job_analysis.required_skills)

    # 2. Content Preparation
    if section_format == "headings":
        if skill_type == "standard":
            content_lines = [
                "# Candidate Standard",
                "## EXPERIENCE",
                "5 years of experience in backend systems developing with Python, Docker, and PostgreSQL.",
                "## SKILLS",
                "Python, Docker, PostgreSQL, AWS, Git",
                "## EDUCATION",
                "BS Computer Science",
            ]
        else:
            content_lines = [
                "# Candidate Edge",
                "## EXPERIENCE",
                "4 years developing low latency software using C# and C++. Managed Node.js microservices and R models.",
                "## SKILLS",
                "C#, C++, Node.js, R, .NET, K8s",
                "## EDUCATION",
                "BS Computer Engineering",
            ]
    else:
        # Fallback unstructured prose
        if skill_type == "standard":
            content_lines = [
                "Candidate Standard is a seasoned developer with 5 years of software engineering experience. "
                "The engineer specializes in backend services using Python, Docker, and PostgreSQL. "
                "Also uses AWS and Git extensively. Graduated with a BS in Computer Science."
            ]
        else:
            content_lines = [
                "Candidate Edge has spent 4 years building systems using C# and C++ for financial analytics. "
                "Also writes microservices with Node.js and quantitative scripts in standalone R. "
                "Deploys containers to K8s and works with .NET. Holds a BS in Computer Engineering."
            ]

    # 3. Format Handling (Zero Mock)
    if file_format == "pdf":
        stream = create_in_memory_pdf(content_lines)
        stream.name = f"{test_id}.pdf"
        parsed_resumes = parse_resumes([stream])
    elif file_format == "docx":
        stream = create_in_memory_docx(content_lines)
        stream.name = f"{test_id}.docx"
        parsed_resumes = parse_resumes([stream])
    else:
        raw_text = "\n".join(content_lines)
        parsed_resumes = [
            ParsedResume(
                filename=f"{test_id}.txt",
                raw_text=raw_text,
                cleaned_text=raw_text,
                skills=[],
                experience_years=5.0 if skill_type == "standard" else 4.0,
            )
        ]

    assert len(parsed_resumes) == 1
    resume = parsed_resumes[0]
    assert len(resume.raw_text.strip()) > 0

    # 4. Weights Configuration
    if weight_type == "default":
        weights = WeightConfig(required_skill_weight=0.5, preferred_skill_weight=0.2, semantic_weight=0.2, experience_weight=0.1)
    else:
        weights = WeightConfig(required_skill_weight=0.7, preferred_skill_weight=0.1, semantic_weight=0.1, experience_weight=0.1)

    # 5. Ranking Execution
    rankings = rank(job=job_analysis, resumes=[resume], weights=weights)
    assert len(rankings) == 1
    res = rankings[0]

    # 6. Validations
    assert isinstance(res.match_score, float)
    assert 0.0 <= res.match_score <= 100.0
    assert res.component_scores.required_skill_score > 0.0
    assert res.component_scores.semantic_score > 0.0
    assert res.component_scores.experience_score > 0.0

    if skill_type == "edge":
        matched_lower = [s.lower() for s in res.matched_skills]
        assert "c#" in matched_lower
        assert "c++" in matched_lower
        assert "node.js" in matched_lower
        assert "r" in matched_lower
        # Sub-span 'c' alone should not appear
        assert "c" not in [s for s in matched_lower if s not in ["c#", "c++"]]
    else:
        matched_lower = [s.lower() for s in res.matched_skills]
        assert "python" in matched_lower
        assert "docker" in matched_lower
        assert "postgresql" in matched_lower


# ==============================================================================
# SECTION 4: TIER 4 - REAL-WORLD APPLICATION SCENARIOS (5 WORKLOADS)
# ==============================================================================

def test_tier4_scenario1_senior_python_backend_screening():
    """Scenario 1: Senior Python Backend Engineer Screening (4 candidates)."""
    _require_service_layer()
    jd_text = (
        "Position: Senior Python Backend Engineer\n"
        "Experience: Minimum 5 years of professional software engineering experience.\n\n"
        "Required Qualifications:\n"
        "- Must have at least 5 years of experience in backend development.\n"
        "- Strong proficiency in Python and FastAPI framework.\n"
        "- Hands-on experience with Docker containerization and PostgreSQL relational databases.\n\n"
        "Preferred Qualifications:\n"
        "- Nice to have experience with Redis caching and Kubernetes orchestration.\n"
        "- Familiarity with AWS cloud services and CI/CD pipelines is a plus."
    )
    job = analyze_job(jd_text)

    # Candidate 1: Alice (Senior Python Lead) - PDF stream
    p1 = create_in_memory_pdf([
        "Alice Senior Python",
        "EXPERIENCE",
        "6 years building distributed backend systems in Python, FastAPI, Docker, and PostgreSQL.",
        "SKILLS",
        "Python, FastAPI, Docker, PostgreSQL, Redis, AWS, CI/CD",
    ])
    p1.name = "Alice_Senior_Python.pdf"

    # Candidate 2: Bob (Mid Python Dev) - DOCX stream
    p2 = create_in_memory_docx([
        "# Bob Mid Python",
        "## EXPERIENCE",
        "3 years developing backend scripts with Python, Docker, and PostgreSQL.",
        "## SKILLS",
        "Python, Docker, PostgreSQL, Git",
    ])
    p2.name = "Bob_Mid_Python.docx"

    # Candidate 3: Charlie (Junior Django Dev) - PDF stream
    p3 = create_in_memory_pdf([
        "Charlie Junior Django",
        "EXPERIENCE",
        "1 year junior developer experience with Python and Django.",
        "SKILLS",
        "Python, Django, SQLite, Git",
    ])
    p3.name = "Charlie_Junior_Django.pdf"

    # Candidate 4: Dana (Frontend Dev) - DOCX stream
    p4 = create_in_memory_docx([
        "# Dana Frontend Dev",
        "## EXPERIENCE",
        "4 years developing React, TypeScript, HTML, CSS applications.",
        "## SKILLS",
        "React, TypeScript, HTML, CSS, Next.js",
    ])
    p4.name = "Dana_Frontend_Dev.docx"

    parsed_resumes = parse_resumes([p1, p2, p3, p4])
    rankings = rank(job=job, resumes=parsed_resumes)

    assert len(rankings) == 4
    assert [r.candidate for r in rankings] == [
        "Alice_Senior_Python.pdf",
        "Bob_Mid_Python.docx",
        "Charlie_Junior_Django.pdf",
        "Dana_Frontend_Dev.docx",
    ]
    assert rankings[0].match_score > rankings[1].match_score > rankings[2].match_score > rankings[3].match_score
    assert rankings[0].missing_required_skills == []
    assert "FastAPI" in rankings[1].missing_required_skills
    assert len(rankings[2].missing_required_skills) >= 2


def test_tier4_scenario2_fullstack_react_typescript_screening():
    """Scenario 2: Full-Stack React/TypeScript Developer Screening (4 candidates)."""
    _require_service_layer()
    jd_text = (
        "Job Title: Full-Stack React/TypeScript Developer\n"
        "Years of Experience: At least 3 years required.\n\n"
        "Requirements (Must-Have):\n"
        "- Must possess strong production experience with React and TypeScript.\n"
        "- Required hands-on development in Node.js backend services and Next.js SSR applications.\n\n"
        "Desired (Nice-to-Have):\n"
        "- Preferred knowledge of GraphQL APIs and PostgreSQL databases.\n"
        "- Experience with Docker containers is a bonus."
    )
    job = analyze_job(jd_text)

    # Candidate 1: Elena (uses aliases: TS, NodeJS, React.js)
    p1 = create_in_memory_docx([
        "# Elena FullStack Lead",
        "## EXPERIENCE",
        "4 years building full-stack applications. Expertise in TS, NodeJS, React.js, and Next.js.",
        "## SKILLS",
        "TS, NodeJS, React.js, Next.js, GraphQL, PostgreSQL",
    ])
    p1.name = "Elena_FullStack_Lead.docx"

    # Candidate 2: Frank (Frontend only, missing Node.js)
    p2 = create_in_memory_pdf([
        "Frank Frontend Focus",
        "EXPERIENCE",
        "3 years experience in React, TypeScript, and Next.js.",
        "SKILLS",
        "React, TypeScript, Next.js, Redux, HTML, CSS",
    ])
    p2.name = "Frank_Frontend_Focus.pdf"

    # Candidate 3: George (Backend Node only, missing React & TS)
    p3 = create_in_memory_docx([
        "# George Backend Node",
        "## EXPERIENCE",
        "3 years developing backend APIs with Node.js and Express.",
        "## SKILLS",
        "Node.js, Express.js, MongoDB, JavaScript",
    ])
    p3.name = "George_Backend_Node.docx"

    # Candidate 4: Hannah (Legacy Java developer - must NOT match JavaScript!)
    p4 = create_in_memory_pdf([
        "Hannah Legacy Java",
        "EXPERIENCE",
        "6 years developing enterprise Java microservices with Spring Boot.",
        "SKILLS",
        "Java, Spring Boot, Oracle Database",
    ])
    p4.name = "Hannah_Legacy_Java.pdf"

    parsed = parse_resumes([p1, p2, p3, p4])
    rankings = rank(job=job, resumes=parsed)

    elena = rankings[0]
    assert elena.candidate == "Elena_FullStack_Lead.docx"
    assert {"TypeScript", "Node.js", "React", "Next.js"}.issubset(set(elena.matched_skills))

    hannah = rankings[3]
    assert "JavaScript" not in hannah.matched_skills
    assert rankings[0].match_score > rankings[1].match_score > rankings[2].match_score > rankings[3].match_score


def test_tier4_scenario3_cloud_devops_platform_screening():
    """Scenario 3: Cloud & DevOps Platform Engineer Screening (4 candidates)."""
    _require_service_layer()
    jd_text = (
        "Title: Cloud & DevOps Platform Engineer\n"
        "Experience: 4+ years in site reliability or cloud engineering.\n\n"
        "Required Skills & Experience:\n"
        "- Essential: Deep expertise in AWS cloud architecture and Kubernetes container orchestration.\n"
        "- Must have production proficiency with Terraform IaC and Linux systems administration.\n\n"
        "Preferred Qualifications:\n"
        "- Experience with Ansible configuration management and Prometheus monitoring.\n"
        "- Scripting in Python is a strong plus."
    )
    job = analyze_job(jd_text)

    # Candidate 1: Ian (uses alias K8s for Kubernetes)
    p1 = create_in_memory_pdf([
        "Ian DevOps Specialist",
        "EXPERIENCE",
        "5 years as DevOps Lead. Architected multi-region K8s clusters on AWS with Terraform and Linux.",
        "SKILLS",
        "AWS, K8s, Terraform, Linux, Prometheus, Python",
    ])
    p1.name = "Ian_DevOps_Specialist.pdf"

    # Candidate 2: Julia (Missing Kubernetes)
    p2 = create_in_memory_docx([
        "# Julia Cloud Engineer",
        "## EXPERIENCE",
        "4 years managing cloud infrastructure on AWS using Terraform and Linux.",
        "## SKILLS",
        "AWS, Terraform, Linux, Bash, Git",
    ])
    p2.name = "Julia_Cloud_Engineer.docx"

    # Candidate 3: Kevin (SysAdmin, missing AWS/K8s/Terraform)
    p3 = create_in_memory_pdf([
        "Kevin SysAdmin",
        "EXPERIENCE",
        "6 years administering Linux systems with Ansible and Apache.",
        "SKILLS",
        "Linux, Unix, Bash, Ansible, Apache",
    ])
    p3.name = "Kevin_SysAdmin.pdf"

    # Candidate 4: Laura (Data analyst)
    p4 = create_in_memory_docx([
        "# Laura Data Analyst",
        "## EXPERIENCE",
        "3 years in SQL, Snowflake, Tableau, ETL.",
        "## SKILLS",
        "SQL, Snowflake, Tableau",
    ])
    p4.name = "Laura_Data_Analyst.docx"

    parsed = parse_resumes([p1, p2, p3, p4])
    rankings = rank(job=job, resumes=parsed)

    assert rankings[0].candidate == "Ian_DevOps_Specialist.pdf"
    assert "Kubernetes" in rankings[0].matched_skills
    assert "Kubernetes" in rankings[1].missing_required_skills
    assert rankings[0].match_score > rankings[1].match_score > rankings[2].match_score > rankings[3].match_score


def test_tier4_scenario4_ml_data_scientist_screening():
    """Scenario 4: Machine Learning / Data Scientist Screening (4 candidates)."""
    _require_service_layer()
    jd_text = (
        "Position: Machine Learning / Data Scientist\n"
        "Experience Requirement: Minimum 4 years of experience in ML or data science.\n\n"
        "Mandatory Requirements:\n"
        "- Must be proficient in Python and R programming languages.\n"
        "- Required hands-on modeling with PyTorch and Scikit-Learn.\n\n"
        "Bonus Qualifications:\n"
        "- Preferred skills include TensorFlow, Docker, Pandas, and NumPy."
    )
    job = analyze_job(jd_text)

    # Candidate 1: Dr. Michael (has standalone 'R' and hyphenated 'Scikit-Learn')
    p1 = create_in_memory_pdf([
        "Dr Michael ML",
        "EXPERIENCE",
        "5 years experience in machine learning. Expertise in statistical modeling using R and Python.",
        "SKILLS",
        "Python, R, PyTorch, Scikit-Learn, TensorFlow, Pandas",
    ])
    p1.name = "Dr_Michael_ML.pdf"

    # Candidate 2: Nora (worked in R&D division, does NOT know 'R')
    p2 = create_in_memory_docx([
        "# Nora Python Engineer",
        "## EXPERIENCE",
        "4 years in Corporate R&D Division developing PyTorch and Scikit-Learn models in Python.",
        "## SKILLS",
        "Python, PyTorch, Scikit-Learn, Docker",
    ])
    p2.name = "Nora_Python_Engineer_RnD.docx"

    # Candidate 3: Oliver (Statistician, missing PyTorch and Scikit-Learn)
    p3 = create_in_memory_pdf([
        "Oliver Statistician",
        "EXPERIENCE",
        "5 years statistical modeling in R, Python, Pandas, NumPy.",
        "SKILLS",
        "R, Python, Pandas, NumPy",
    ])
    p3.name = "Oliver_Statistician.pdf"

    # Candidate 4: Patricia (Web dev)
    p4 = create_in_memory_docx([
        "# Patricia Web Dev",
        "## EXPERIENCE",
        "4 years in PHP, MySQL, HTML, CSS.",
        "## SKILLS",
        "PHP, MySQL, HTML, CSS",
    ])
    p4.name = "Patricia_Web_Dev.docx"

    parsed = parse_resumes([p1, p2, p3, p4])
    rankings = rank(job=job, resumes=parsed)

    michael = rankings[0]
    nora = rankings[1]

    assert michael.candidate == "Dr_Michael_ML.pdf"
    assert "R" in michael.matched_skills
    assert "Scikit-Learn" in michael.matched_skills

    assert nora.candidate == "Nora_Python_Engineer_RnD.docx"
    assert "R" not in nora.matched_skills
    assert "R" in nora.missing_required_skills
    assert michael.match_score > nora.match_score


def test_tier4_scenario5_unstructured_narrative_screening():
    """Scenario 5: Unstructured Narrative Resume Screening with Missing Headings (3 candidates)."""
    _require_service_layer()
    jd_text = (
        "Senior Backend Engineer. 4 years experience required. "
        "Required: Python, Docker, PostgreSQL, REST API."
    )
    job = analyze_job(jd_text)

    # Quinn: Continuous narrative prose with 0 headings
    quinn_text = (
        "Quinn has been working as a professional software engineer for the past 5 years. "
        "During this time, Quinn architected distributed backend services in Python, "
        "containerized services using Docker, and managed high-concurrency databases in PostgreSQL. "
        "Quinn regularly designed and deployed REST API endpoints and integrated Redis caches. "
        "Quinn graduated with a Bachelor of Science in Computer Science from State University in 2019."
    )
    quinn_res = ParsedResume(
        filename="Quinn_Narrative.txt",
        raw_text=quinn_text,
        cleaned_text=quinn_text,
        skills=[],
        experience_years=5.0,
    )

    # Riley: Single heading DOCX
    riley_stream = create_in_memory_docx([
        "# ABOUT ME",
        "Riley has 5 years of software engineering experience. Proficient in Python, Docker, and PostgreSQL. "
        "Built REST API microservices and holds a BS in Computer Science.",
    ])
    riley_stream.name = "Riley_SingleHeading.docx"

    # Sam: Standard structured benchmark PDF
    sam_stream = create_in_memory_pdf([
        "Sam Structured Benchmark",
        "EXPERIENCE",
        "5 years software engineering. Built distributed backend services in Python, Docker, and PostgreSQL.",
        "SKILLS",
        "Python, Docker, PostgreSQL, REST API",
        "EDUCATION",
        "BS Computer Science",
    ])
    sam_stream.name = "Sam_Benchmark.pdf"

    parsed_riley = parse_resumes([riley_stream])[0]
    parsed_sam = parse_resumes([sam_stream])[0]

    rankings = rank(job=job, resumes=[quinn_res, parsed_riley, parsed_sam])
    quinn = [r for r in rankings if "Quinn" in r.candidate][0]
    sam = [r for r in rankings if "Sam" in r.candidate][0]

    assert {"Python", "Docker", "PostgreSQL"}.issubset(set(quinn.matched_skills))
    # Unstructured narrative should achieve a score within 5% of structured benchmark
    assert abs(quinn.match_score - sam.match_score) <= 5.0
    assert quinn.component_scores.required_skill_score == sam.component_scores.required_skill_score


# ==============================================================================
# SECTION 5: AUTOMATED EVALUATION INVARIANCE MATHEMATICAL PROOFS (4 TESTS)
# ==============================================================================

def test_evaluation_invariance_proof_name_perturbation():
    """Mathematical Proof 1: Proves match score is bit-for-bit invariant to candidate name changes."""
    _require_service_layer()
    base_text = (
        "{name}\n"
        "Email: developer@example.com | Phone: 555-0100\n"
        "EXPERIENCE\n"
        "Senior Software Engineer with 5 years of experience building Python and FastAPI microservices.\n"
        "Managed PostgreSQL databases and deployed containers via Docker.\n"
        "SKILLS\n"
        "Python, FastAPI, Docker, PostgreSQL, AWS\n"
        "EDUCATION\n"
        "BS Computer Science\n"
    )
    names = [
        "Jonathan Edwards",
        "Aisha Al-Mansoor",
        "Wei Zhang",
        "Elena Rostova",
        "Kwame Mensah",
        "Maria Garcia-Rodriguez",
    ]
    jd = analyze_job("Senior Python Engineer. 5 years experience. Required: Python, FastAPI, Docker, PostgreSQL.")

    resumes = []
    for i, name in enumerate(names):
        raw = base_text.format(name=name)
        anon = anonymize_text(raw, candidate_name=name)
        resumes.append(ParsedResume(filename=f"res_{i}.txt", raw_text=raw, cleaned_text=anon, experience_years=5.0))

    rankings = rank(job=jd, resumes=resumes)
    scores = [r.match_score for r in rankings]
    base_score = scores[0]

    for i, s in enumerate(scores):
        diff = abs(s - base_score)
        assert diff == 0.0, f"Name invariance violated: {names[i]} got {s} vs baseline {base_score}"
        assert rankings[i].component_scores.required_skill_score == rankings[0].component_scores.required_skill_score
        assert rankings[i].component_scores.semantic_score == rankings[0].component_scores.semantic_score
        assert rankings[i].matched_skills == rankings[0].matched_skills


def test_evaluation_invariance_proof_contact_info_perturbation():
    """Mathematical Proof 2: Proves score equivalence across diverse international contact details."""
    _require_service_layer()
    template = (
        "Candidate Identity\n"
        "Email: {email}\n"
        "Phone: {phone}\n"
        "EXPERIENCE\n"
        "4 years developing React and TypeScript applications with Docker.\n"
        "SKILLS\n"
        "React, TypeScript, Docker\n"
    )
    contacts = [
        ("dev.one@gmail.com", "+1 (555) 234-5678"),
        ("candidate.two@oxford.ac.uk", "+44 20 7946 0912"),
        ("tech_lead@corp.de", "030 1234567"),
        ("dev3@techstartup.io", "555-0199-88"),
    ]
    jd = analyze_job("Frontend Developer. Required: React, TypeScript, Docker. 4 years experience.")

    resumes = []
    for i, (e, p) in enumerate(contacts):
        raw = template.format(email=e, phone=p)
        anon = anonymize_text(raw)
        resumes.append(ParsedResume(filename=f"contact_{i}.txt", raw_text=raw, cleaned_text=anon, experience_years=4.0))

    rankings = rank(job=jd, resumes=resumes)
    base_score = rankings[0].match_score

    for r in rankings:
        assert abs(r.match_score - base_score) == 0.0


def test_evaluation_invariance_proof_pronoun_perturbation():
    """Mathematical Proof 3: Proves score equivalence across masculine, feminine, and neutral pronouns."""
    _require_service_layer()
    text_masculine = (
        "Alex Developer\n"
        "EXPERIENCE\n"
        "He has 5 years of experience. He built Python and Docker backend services by himself. "
        "His core responsibility was managing his team's PostgreSQL databases.\n"
        "SKILLS\n"
        "Python, Docker, PostgreSQL\n"
    )
    text_feminine = (
        "Alex Developer\n"
        "EXPERIENCE\n"
        "She has 5 years of experience. She built Python and Docker backend services by herself. "
        "Her core responsibility was managing her team's PostgreSQL databases.\n"
        "SKILLS\n"
        "Python, Docker, PostgreSQL\n"
    )
    text_neutral = (
        "Alex Developer\n"
        "EXPERIENCE\n"
        "They have 5 years of experience. They built Python and Docker backend services by themselves. "
        "Their core responsibility was managing their team's PostgreSQL databases.\n"
        "SKILLS\n"
        "Python, Docker, PostgreSQL\n"
    )

    jd = analyze_job("Senior Python Developer. 5 years experience. Required: Python, Docker, PostgreSQL.")

    res_m = ParsedResume(filename="he.txt", raw_text=text_masculine, cleaned_text=anonymize_text(text_masculine, "Alex Developer"), experience_years=5.0)
    res_f = ParsedResume(filename="she.txt", raw_text=text_feminine, cleaned_text=anonymize_text(text_feminine, "Alex Developer"), experience_years=5.0)
    res_n = ParsedResume(filename="they.txt", raw_text=text_neutral, cleaned_text=anonymize_text(text_neutral, "Alex Developer"), experience_years=5.0)

    rankings = rank(job=jd, resumes=[res_m, res_f, res_n])
    score_m = rankings[0].match_score
    score_f = rankings[1].match_score
    score_n = rankings[2].match_score

    assert abs(score_m - score_f) == 0.0, f"Masculine vs Feminine score difference: {abs(score_m - score_f)}"
    assert abs(score_m - score_n) == 0.0, f"Masculine vs Neutral score difference: {abs(score_m - score_n)}"


def test_evaluation_invariance_proof_full_demographic_matrix():
    """Mathematical Proof 4: Simultaneously perturbs Name, Email, Phone, and Pronouns."""
    _require_service_layer()
    template = (
        "{name}\n"
        "Email: {email} | Phone: {phone}\n"
        "EXPERIENCE\n"
        "{pronoun_sub} has 4 years of experience as a Cloud Engineer. {pronoun_sub} deployed AWS "
        "infrastructure using Terraform and managed {pronoun_poss} team's Kubernetes clusters.\n"
        "SKILLS\n"
        "AWS, Terraform, Kubernetes, Linux\n"
        "EDUCATION\n"
        "BS Information Systems\n"
    )

    demographics = [
        {"name": "James Smith", "email": "james.smith@email.com", "phone": "555-100-2000", "pronoun_sub": "He", "pronoun_poss": "his"},
        {"name": "Fatima Zahra", "email": "fatima.zahra@domain.org", "phone": "+971 4 123 4567", "pronoun_sub": "She", "pronoun_poss": "her"},
        {"name": "Li Na", "email": "li.na@tech.cn", "phone": "+86 10 6543 2100", "pronoun_sub": "She", "pronoun_poss": "her"},
        {"name": "Jordan Taylor", "email": "jtaylor@modern.io", "phone": "(555) 987-6543", "pronoun_sub": "They", "pronoun_poss": "their"},
    ]

    jd = analyze_job("Cloud Engineer. 4 years experience. Required: AWS, Terraform, Kubernetes, Linux.")

    resumes = []
    for i, d in enumerate(demographics):
        raw = template.format(**d)
        anon = anonymize_text(raw, candidate_name=d["name"])
        resumes.append(ParsedResume(filename=f"candidate_{i}.txt", raw_text=raw, cleaned_text=anon, experience_years=4.0))

    rankings = rank(job=jd, resumes=resumes)
    scores = [r.match_score for r in rankings]
    diff = max(scores) - min(scores)
    assert diff == 0.0, f"Demographic matrix variation detected: diff={diff}"
    first_dump = rankings[0].component_scores.model_dump()
    assert all(r.component_scores.model_dump() == first_dump for r in rankings)
