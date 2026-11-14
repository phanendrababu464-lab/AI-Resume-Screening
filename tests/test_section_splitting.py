"""Comprehensive unit tests for resume section splitting and fallback mechanisms."""

from __future__ import annotations

import io
from pathlib import Path
import pytest

from src.parser import (
    extract_text_from_docx,
    extract_text_from_pdf,
    split_resume_sections,
)


def test_split_resume_sections_empty_and_whitespace() -> None:
    """Verifies that empty string, None, or pure whitespace returns empty sections."""
    empty_result = split_resume_sections("")
    assert empty_result == {
        "skills": "",
        "experience": "",
        "education": "",
        "projects": "",
        "other": "",
    }

    whitespace_result = split_resume_sections("   \n\t  \n  ")
    assert whitespace_result == {
        "skills": "",
        "experience": "",
        "education": "",
        "projects": "",
        "other": "",
    }


def test_split_resume_sections_standard_headings() -> None:
    """Verifies extraction when standard resume section headings are present."""
    resume_text = """
John Doe
john.doe@example.com | (555) 019-2834 | New York, NY

TECHNICAL SKILLS
Languages: Python, Go, C++, SQL
Tools: Docker, Kubernetes, Git, AWS

WORK EXPERIENCE
Senior Backend Engineer | Acme Corp | 2021 - Present
- Designed and scaled microservices handling 50k RPS.
- Migrated monolith to Kubernetes and Terraform.

Software Engineer | Beta Startup | 2018 - 2021
- Developed REST APIs in FastAPI and PostgreSQL.

EDUCATION
Stanford University
Bachelor of Science in Computer Science, GPA: 3.9

KEY PROJECTS
Distributed KV Store (github.com/johndoe/kv-store)
- Implemented Raft consensus in Go from scratch.
"""
    sections = split_resume_sections(resume_text)

    # All standard keys must exist
    assert set(sections.keys()) == {"skills", "experience", "education", "projects", "other"}

    # Header / contact info before first heading goes to 'other'
    assert "John Doe" in sections["other"]
    assert "john.doe@example.com" in sections["other"]

    # Technical skills
    assert "Python, Go, C++, SQL" in sections["skills"]
    assert "Docker, Kubernetes" in sections["skills"]

    # Work experience
    assert "Senior Backend Engineer" in sections["experience"]
    assert "Acme Corp" in sections["experience"]
    assert "Beta Startup" in sections["experience"]

    # Education
    assert "Stanford University" in sections["education"]
    assert "Bachelor of Science" in sections["education"]

    # Projects
    assert "Distributed KV Store" in sections["projects"]
    assert "Raft consensus" in sections["projects"]


def test_split_resume_sections_heading_variations() -> None:
    """Tests various case patterns, punctuation (colons), and markdown formatting on headings."""
    resume_text = """
### Professional Summary
Passionate software developer with 6+ years of experience.

## Skills:
Python, Rust, Docker, PostgreSQL

## Professional Experience:
Lead Engineer at FinTech Inc (2020 - 2024)
- Architected payment gateway.

## Academic Background:
M.S. in Computer Engineering, Carnegie Mellon University

## Featured Projects:
Open-source machine learning pipeline on GitHub.
"""
    sections = split_resume_sections(resume_text)

    assert "Passionate software developer" in sections["other"]
    assert "Python, Rust" in sections["skills"]
    assert "Lead Engineer at FinTech Inc" in sections["experience"]
    assert "Carnegie Mellon University" in sections["education"]
    assert "Open-source machine learning pipeline" in sections["projects"]


def test_split_resume_sections_multiple_headings_same_category() -> None:
    """Tests that multiple headings mapping to the same section (e.g. Experience and Internships) are combined."""
    resume_text = """
SKILLS
Python, SQL

WORK EXPERIENCE
Software Developer at Google (2020 - 2022)

INTERNSHIPS
Engineering Intern at Microsoft (Summer 2019)

EDUCATION
BS in CS, UC Berkeley
"""
    sections = split_resume_sections(resume_text)

    assert "Software Developer at Google" in sections["experience"]
    assert "Engineering Intern at Microsoft" in sections["experience"]
    assert "BS in CS" in sections["education"]
    assert "Python, SQL" in sections["skills"]


def test_split_resume_sections_fallback_narrative_no_headings() -> None:
    """Verifies heuristic fallback when 0 headings are present in narrative text, ensuring NO text is dropped."""
    narrative_resume = (
        "Alice Smith is a software engineer with 5 years of experience at TechCorp from 2019 to 2024.\n"
        "She graduated with a Bachelor of Science in Computer Science from Stanford University in 2019.\n"
        "She built and launched an open-source distributed database hosted on GitHub.\n"
        "Proficient in Python, Go, Docker, Kubernetes, and PostgreSQL.\n"
        "Contact: alice.smith@example.com | San Francisco, CA."
    )

    sections = split_resume_sections(narrative_resume)

    # Verify classification of contents
    assert "Stanford University" in sections["education"] or "Bachelor of Science" in sections["education"]
    assert "software engineer" in sections["experience"] or "TechCorp" in sections["experience"]
    assert "GitHub" in sections["projects"] or "open-source" in sections["projects"]
    assert "Python" in sections["skills"] or "Docker" in sections["skills"]
    assert "alice.smith@example.com" in sections["other"] or "Contact" in sections["other"]

    # Verify NO TEXT IS DROPPED: Every non-empty line must appear in one of the sections
    combined_output = " ".join(sections.values())
    for line in narrative_resume.splitlines():
        cleaned_line = line.strip()
        if cleaned_line:
            # Check that line words exist in the output
            assert all(word in combined_output for word in cleaned_line.split())


def test_split_resume_sections_fallback_single_heading() -> None:
    """Verifies that when only 1 heading is detected, fallback mechanism activates and separates sections."""
    single_heading_resume = """
EDUCATION
Bachelor of Science from MIT (2018-2022)

Software Engineer at Stripe from 2022 to 2024 developing payment infrastructure.
Built an open-source analytics dashboard on GitHub.
Proficient in Java, Go, Kubernetes, and AWS.
"""
    sections = split_resume_sections(single_heading_resume)

    # Heading detection requires >= 2 headings; with only 1 heading, fallback separates the rest
    assert "Bachelor of Science" in sections["education"] or "MIT" in sections["education"]
    assert "Software Engineer at Stripe" in sections["experience"]
    assert "open-source analytics dashboard" in sections["projects"]
    assert "Java, Go, Kubernetes" in sections["skills"]


def test_split_resume_sections_docx_extracted_format(sample_docx_stream: io.BytesIO) -> None:
    """Tests section splitting on realistic text extracted from DOCX document."""
    raw_text = extract_text_from_docx(sample_docx_stream)
    assert len(raw_text) > 0

    # Simulate realistic resume formatting with extracted text
    resume_text = f"""
TECHNICAL SKILLS
{raw_text}

EXPERIENCE
Senior Developer at Enterprise Solutions from 2020 to 2024

EDUCATION
Master of Science in Software Engineering, State University

PROJECTS
Developed high-throughput messaging system on GitHub
"""
    sections = split_resume_sections(resume_text)
    assert "FastAPI" in sections["skills"] or "Python" in sections["skills"]
    assert "Senior Developer at Enterprise Solutions" in sections["experience"]
    assert "State University" in sections["education"]
    assert "messaging system" in sections["projects"]


def test_split_resume_sections_unclassified_text_preserved_in_other() -> None:
    """Verifies that arbitrary unclassified sentences and metadata are safely preserved in 'other'."""
    resume_text = """
Jane Doe
Phone: +1-202-555-0143
Email: jane@example.com
Hobbies: Marathon running, chess, classical guitar.
Available for relocation immediately.
"""
    sections = split_resume_sections(resume_text)
    assert "Jane Doe" in sections["other"]
    assert "jane@example.com" in sections["other"]
    assert "Marathon running" in sections["other"]
    assert "Available for relocation" in sections["other"]


def test_split_resume_sections_expanded_headings() -> None:
    """Tests newly expanded heading patterns for skills, experience, education, projects, and other."""
    resume_text_1 = """
AREAS OF EXPERTISE
Python, Go, Distributed Systems, Cloud Architecture

WORK AND LEADERSHIP
Engineering Manager at FinTech Corp (2020 - 2024)
- Led squad of 8 engineers.

EDUCATIONAL QUALIFICATIONS
B.Tech in Information Technology, National Institute of Technology

PROJECTS & ACHIEVEMENTS
Led architecture migration to Kubernetes saving $500k annually.

CAREER SYNOPSIS
Experienced engineering leader with track record of high-scale deliverables.
"""
    sec1 = split_resume_sections(resume_text_1)
    assert "Python, Go" in sec1["skills"]
    assert "Engineering Manager at FinTech Corp" in sec1["experience"]
    assert "B.Tech in Information Technology" in sec1["education"]
    assert "Kubernetes saving $500k" in sec1["projects"]
    assert "Experienced engineering leader" in sec1["other"]

    resume_text_2 = """
SKILLS & TOOLS
Docker, Terraform, Git, PostgreSQL

PROFESSIONAL WORK EXPERIENCE
Staff Engineer at Cloud Platform (2019 - Present)

ACADEMIC EDUCATION
Master of Science in Software Engineering, Carnegie Mellon

PERSONAL AND OPEN SOURCE PROJECTS
Created high-speed JSON parser in Rust on GitHub.

CAREER OVERVIEW
Dedicated systems programmer with 10+ years experience.
"""
    sec2 = split_resume_sections(resume_text_2)
    assert "Docker, Terraform" in sec2["skills"]
    assert "Staff Engineer at Cloud Platform" in sec2["experience"]
    assert "Carnegie Mellon" in sec2["education"]
    assert "high-speed JSON parser in Rust" in sec2["projects"]
    assert "Dedicated systems programmer" in sec2["other"]

    resume_text_3 = """
TOOLS & SKILLS
React, TypeScript, CSS, GraphQL

WORK HISTORY
Frontend Developer at WebCorp (2021 - 2023)

EDUCATION & CREDENTIALS
B.S. in Computer Science, Stanford University

PROJECTS & ACTIVITIES
Open-source design system maintainer.

SYNOPSIS
Creative UI engineer.
"""
    sec3 = split_resume_sections(resume_text_3)
    assert "React, TypeScript" in sec3["skills"]
    assert "Frontend Developer at WebCorp" in sec3["experience"]
    assert "Stanford University" in sec3["education"]
    assert "Open-source design system" in sec3["projects"]
    assert "Creative UI engineer" in sec3["other"]


def test_split_resume_sections_noisy_heading_cleaning() -> None:
    """Verifies that headings with markdown symbols, leading list numerals, roman numerals, and trailing colons clean properly."""
    resume_text = """
### 1. TECHNICAL SKILLS: ###
Python, Rust, Docker, Kubernetes

=== PROFESSIONAL WORK EXPERIENCE ===:
Senior Software Engineer at Alpha Systems (2020 - 2024)

** ACADEMIC EDUCATION **
B.S. in Computer Science, MIT (2016 - 2020)

[A] KEY PROJECTS:
Distributed storage engine with Raft consensus.

(IV) CAREER SYNOPSIS:
Specialist in distributed databases and distributed consensus.
"""
    sections = split_resume_sections(resume_text)
    assert "Python, Rust, Docker" in sections["skills"]
    assert "Senior Software Engineer at Alpha Systems" in sections["experience"]
    assert "B.S. in Computer Science, MIT" in sections["education"]
    assert "Distributed storage engine" in sections["projects"]
    assert "Specialist in distributed databases" in sections["other"]


def test_split_resume_sections_competencies_fallback() -> None:
    """Verifies narrative fallback on 'competencies' categorized into skills."""
    narrative = "My core competencies include Python, Go, and Kubernetes."
    sections = split_resume_sections(narrative)
    assert "Python, Go, and Kubernetes" in sections["skills"]
    assert sections["other"] == "" or "Python" not in sections["other"]


def test_split_resume_sections_single_heading_active_section() -> None:
    """Verifies that single heading maintains active section for subsequent content chunks."""
    text = (
        "SKILLS\n"
        "Python, Docker, AWS\n"
        "Worked at Google from 2020 to 2023 as Software Engineer.\n"
        "Graduated with B.S. in Computer Science from MIT in 2020."
    )
    sections = split_resume_sections(text)
    assert "Python, Docker, AWS" in sections["skills"]
    assert "Worked at Google" in sections["experience"]
    assert "MIT" in sections["education"]

