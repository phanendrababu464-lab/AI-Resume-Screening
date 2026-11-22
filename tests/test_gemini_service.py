"""Unit and integration tests for the Google Gemini AI validation service and API endpoint."""

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.services.gemini_service import (
    GeminiValidationResult,
    _clean_json_markdown,
    get_gemini_api_key,
    is_gemini_available,
    validate_candidate_with_gemini,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_clean_json_markdown():
    raw_json = '{"validation_score": 90, "executive_summary": "Great match"}'
    assert _clean_json_markdown(raw_json) == raw_json

    fenced_json = f"```json\n{raw_json}\n```"
    assert _clean_json_markdown(fenced_json) == raw_json

    bare_fences = f"```\n{raw_json}\n```"
    assert _clean_json_markdown(bare_fences) == raw_json


def test_get_gemini_api_key_priority():
    with patch.dict(os.environ, {}, clear=True):
        assert get_gemini_api_key() is None
        assert is_gemini_available() is False

    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-gemini-key"}, clear=True):
        assert get_gemini_api_key() == "test-gemini-key"
        assert is_gemini_available() is True

    # Fallback to GOOGLE_API_KEY if GEMINI_API_KEY not set
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-google-key"}, clear=True):
        assert get_gemini_api_key() == "test-google-key"
        assert is_gemini_available() is True

    # Priority: GEMINI_API_KEY wins over GOOGLE_API_KEY
    with patch.dict(os.environ, {"GEMINI_API_KEY": "primary-key", "GOOGLE_API_KEY": "fallback-key"}, clear=True):
        assert get_gemini_api_key() == "primary-key"


def test_validate_unconfigured():
    with patch.dict(os.environ, {}, clear=True):
        res = validate_candidate_with_gemini(
            job_description="Senior Backend Engineer with Python and FastAPI",
            candidate_name="candidate_01.pdf",
            candidate_text="Experienced Python developer",
            matched_skills=["Python", "FastAPI"],
            missing_skills=["Docker"],
        )
        assert res.status == "unconfigured"
        assert res.validation_score is None
        assert "unconfigured" in res.executive_summary.lower()
        assert "GEMINI_API_KEY" in res.executive_summary
        assert "Python" in res.strengths


def test_validate_mock_success():
    mock_payload = {
        "validation_score": 88,
        "executive_summary": "Strong backend developer with solid API architecture skills.",
        "strengths": ["Extensive FastAPI design", "Clean PostgreSQL database modeling"],
        "risks_or_concerns": ["Limited production Kubernetes exposure"],
        "interview_questions": [
            "How do you handle database migrations in high-traffic deployments?",
            "Can you explain your experience with container orchestration?",
        ],
        "authenticity_assessment": "Authentic project track record demonstrated.",
    }

    mock_response = MagicMock()
    mock_response.text = f"```json\n{import_json(mock_payload)}\n```"

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch.dict(os.environ, {"GEMINI_API_KEY": "mock-key"}, clear=True):
        with patch("google.genai.Client", return_value=mock_client):
            res = validate_candidate_with_gemini(
                job_description="Python Backend Engineer",
                candidate_name="cand_01.pdf",
                candidate_text="Worked on Python and FastAPI APIs.",
                matched_skills=["Python", "FastAPI"],
                missing_skills=["Kubernetes"],
            )
            assert res.status == "success"
            assert res.validation_score == 88
            assert "Strong backend developer" in res.executive_summary
            assert len(res.strengths) == 2
            assert len(res.interview_questions) == 2
            assert res.authenticity_assessment == "Authentic project track record demonstrated."


def test_validate_mock_api_error():
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("Rate limit exceeded 429")

    with patch.dict(os.environ, {"GEMINI_API_KEY": "mock-key"}, clear=True):
        with patch("google.genai.Client", return_value=mock_client):
            res = validate_candidate_with_gemini(
                job_description="Python Engineer",
                candidate_name="cand_01.pdf",
                candidate_text="Resume text",
                matched_skills=["Python"],
            )
            assert res.status == "error"
            assert res.validation_score is None
            assert "rate limit" in res.error_message.lower()


def test_api_validate_endpoint_unconfigured(client: TestClient):
    with patch.dict(os.environ, {}, clear=True):
        response = client.post(
            "/api/resumes/validate",
            json={
                "job_text": "Need Python engineer",
                "candidate_name": "candidate_01.pdf",
                "candidate_text": "Experienced Python coder",
                "matched_skills": ["Python"],
                "missing_skills": ["AWS"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unconfigured"
        assert "GEMINI_API_KEY" in data["executive_summary"]


def test_api_validate_endpoint_empty_job_text(client: TestClient):
    response = client.post(
        "/api/resumes/validate",
        json={
            "job_text": "   ",
            "candidate_name": "candidate_01.pdf",
        },
    )
    assert response.status_code == 400
    assert "Job text cannot be empty" in response.json()["detail"]


def test_api_health_includes_gemini_flag(client: TestClient):
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True):
        res = client.get("/api/health")
        assert res.status_code == 200
        assert res.json()["gemini_available"] is True

    with patch.dict(os.environ, {}, clear=True):
        res = client.get("/api/health")
        assert res.status_code == 200
        assert res.json()["gemini_available"] is False


def import_json(data: dict) -> str:
    import json
    return json.dumps(data)
