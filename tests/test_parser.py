"""Unit tests for the resume parser module (PDF & DOCX)."""

import io
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from src.parser import (
    extract_text,
    extract_text_from_docx,
    extract_text_from_pdf,
)


def test_extract_text_from_docx_valid(sample_docx_stream: io.BytesIO) -> None:
    """Verifies that paragraphs, headings, and table cells are properly extracted from DOCX."""
    text = extract_text_from_docx(sample_docx_stream)
    assert "Senior Software Engineer" in text
    assert "FastAPI" in text
    assert "Docker" in text
    assert "React, TypeScript" in text
    assert "Python, Django, Redis" in text


def test_extract_text_from_docx_invalid_stream() -> None:
    """Verifies ValueError is raised when parsing corrupt DOCX data."""
    corrupt_stream = io.BytesIO(b"Not a real docx file content")
    with pytest.raises(ValueError, match="Failed to extract text from DOCX"):
        extract_text_from_docx(corrupt_stream)


def test_extract_text_from_pdf_mocked() -> None:
    """Verifies text extraction from PDF using a mocked pdfplumber instance."""
    mock_page1 = MagicMock()
    mock_page1.extract_text.return_value = "John Doe\nPython Developer"

    mock_page2 = MagicMock()
    mock_page2.extract_text.return_value = "Skills: Docker, AWS, PostgreSQL"

    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page1, mock_page2]
    mock_pdf.__enter__.return_value = mock_pdf
    mock_pdf.__exit__.return_value = None

    with patch("pdfplumber.open", return_value=mock_pdf):
        dummy_stream = io.BytesIO(b"%PDF-1.4 mock")
        extracted = extract_text_from_pdf(dummy_stream)

        assert "John Doe" in extracted
        assert "Python Developer" in extracted
        assert "Docker, AWS, PostgreSQL" in extracted


def test_extract_text_from_pdf_failure() -> None:
    """Verifies ValueError is raised when pdfplumber encounters an error."""
    with patch("pdfplumber.open", side_effect=Exception("Corrupt PDF bytes")):
        with pytest.raises(ValueError, match="Failed to extract text from PDF"):
            extract_text_from_pdf(io.BytesIO(b"bad bytes"))


def test_extract_text_dispatcher_docx(sample_docx_stream: io.BytesIO) -> None:
    """Tests dispatcher for DOCX using filename parameter."""
    text = extract_text(sample_docx_stream, filename="resume.docx")
    assert "Senior Software Engineer" in text


def test_extract_text_dispatcher_unsupported_format() -> None:
    """Tests that unsupported file extensions raise ValueError."""
    dummy_stream = io.BytesIO(b"some content")
    with pytest.raises(ValueError, match="Unsupported file format"):
        extract_text(dummy_stream, filename="resume.txt")


def test_extract_text_dispatcher_missing_extension() -> None:
    """Tests that missing filename/extension raises ValueError."""
    dummy_stream = io.BytesIO(b"some content")
    with pytest.raises(ValueError, match="Unsupported file format"):
        extract_text(dummy_stream)
