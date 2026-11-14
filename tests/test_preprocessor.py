"""Unit tests for the preprocessor module."""

from src.preprocessor import clean_text, normalize_for_matching


def test_clean_text_normalizes_whitespace() -> None:
    """Verifies excessive spaces, tabs, and duplicate newlines are sanitized."""
    raw = "Software    Engineer\t\t\n\n\n\nSkills:\tPython"
    cleaned = clean_text(raw)
    assert cleaned == "Software Engineer\n\nSkills: Python"


def test_clean_text_removes_bullet_points() -> None:
    """Verifies various bullet markers are converted to uniform spaces."""
    raw = "• Python\n* Docker\n- Kubernetes\n▪ FastAPI"
    cleaned = clean_text(raw)
    assert "•" not in cleaned
    assert "▪" not in cleaned
    assert "Python" in cleaned
    assert "Docker" in cleaned
    assert "Kubernetes" in cleaned
    assert "FastAPI" in cleaned


def test_clean_text_preserves_technical_tokens() -> None:
    """Verifies that special characters in programming languages and hyphenated tokens are not stripped."""
    raw = "Experienced with C++, C#, .NET Core, Scikit-Learn, and Node.js."
    cleaned = clean_text(raw)
    assert "C++" in cleaned
    assert "C#" in cleaned
    assert ".NET Core" in cleaned
    assert "Node.js" in cleaned
    assert "Scikit-Learn" in cleaned


def test_clean_text_empty_and_none() -> None:
    """Verifies robust handling of empty string or falsy inputs."""
    assert clean_text("") == ""
    assert clean_text(None) == ""  # type: ignore[arg-type]


def test_normalize_for_matching() -> None:
    """Verifies that normalization returns lowercased, clean strings."""
    raw = "  Python   and DOCKER\n\n "
    normalized = normalize_for_matching(raw)
    assert normalized == "python and docker"
