"""Pytest fixtures and sample data for unit tests."""

import io
from pathlib import Path
from typing import Generator
import pytest
import docx


@pytest.fixture
def sample_docx_stream() -> io.BytesIO:
    """Creates an in-memory DOCX file containing sample resume text and a table."""
    doc = docx.Document()
    doc.add_heading("Jane Doe - Senior Software Engineer", level=1)
    doc.add_paragraph("Experienced Backend Developer specializing in Python, FastAPI, and Docker.")
    doc.add_paragraph("Proficient in AWS cloud architecture, CI/CD pipelines, and PostgreSQL.")

    # Add a table (simulating common resume layout)
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Frontend"
    table.cell(0, 1).text = "React, TypeScript"
    table.cell(1, 0).text = "Backend"
    table.cell(1, 1).text = "Python, Django, Redis"

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


@pytest.fixture
def sample_skills_data() -> list[str]:
    """Sample list of technical skills for extractor testing."""
    return [
        "Python",
        "FastAPI",
        "Docker",
        "Kubernetes",
        "PostgreSQL",
        "AWS",
        "React",
        "TypeScript",
        "C++",
        ".NET",
        "Machine Learning",
    ]


@pytest.fixture
def sample_job_description() -> str:
    """Sample technical job description."""
    return (
        "Seeking a Senior Python Engineer with hands-on experience in FastAPI, "
        "PostgreSQL, Docker, and Kubernetes. AWS and CI/CD experience is required."
    )


@pytest.fixture
def sample_candidates() -> list[dict[str, str]]:
    """Sample candidate resumes with varying relevance to the job description."""
    return [
        {
            "name": "Alex_Python_Expert.pdf",
            "text": (
                "Senior Software Engineer with 7 years of Python, FastAPI, Docker, and Kubernetes. "
                "Architected scalable microservices on AWS and managed PostgreSQL databases."
            ),
        },
        {
            "name": "Bob_Frontend_Dev.docx",
            "text": (
                "Frontend Specialist with deep expertise in React, TypeScript, HTML, and CSS. "
                "Minor experience in Python scripts."
            ),
        },
        {
            "name": "Charlie_Java_Dev.pdf",
            "text": (
                "Java backend engineer specialized in Spring Boot, Oracle Database, and Jenkins. "
                "Looking to transition into Python."
            ),
        },
    ]
