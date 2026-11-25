"""Exercise the browser workspace API contract and live worker behavior."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient

import src.api as api
from src.services.insights import generate_insights
from src.services.screening_service import extract_evidenced_experience

client = TestClient(api.app)
SAMPLES = api.DATA_DIR / "resumes"


def test_screen_hybrid_equation_overrides_and_comparison():
    files = [("files", (name, (SAMPLES / name).read_bytes(), "application/octet-stream"))
             for name in ("resume_01.pdf", "resume_06.docx")]
    form = {"job_text": "Build APIs and maintain PostgreSQL databases.",
            "job_title": "API engineer", "required_skills": "Python, PostgreSQL",
            "preferred_skills": "Docker", "min_experience_years": "4"}
    response = client.post("/api/screen", data=form, files=files)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["effective_weights"] == {"semantic": .4, "keyword": .2, "skills": .3, "experience": .1}
    assert data["job"]["job_title"] == "API engineer"
    assert set(data["job"]["required_skills"]) == {"Python", "PostgreSQL"}
    assert data["job"]["min_experience_years"] == 4
    rows = data["rankings"]
    assert len({row["candidate_id"] for row in rows}) == 2
    assert rows[0]["match_score"] >= rows[1]["match_score"]
    for row in rows:
        scores = row["component_scores"]
        expected = 100 * sum((scores[key] or 0) * weight for key, weight in (
            ("semantic_score", .4), ("tfidf_baseline_score", .2),
            ("skill_score", .3), ("experience_score", .1),
        ))
        assert row["match_score"] == pytest.approx(expected, abs=.012)
        contributions = [item["contribution"] for item in data["charts"]["composition"] if item["candidate"] == row["candidate"]]
        assert sum(contributions) == pytest.approx(row["match_score"])
    comparison = client.post("/api/compare", json={"candidates": rows})
    assert comparison.status_code == 200
    assert [row["candidate"] for row in rows] == [row["label"] for row in comparison.json()["candidates"]]


def test_unknown_experience_is_explicit(sample_docx_stream):
    response = client.post("/api/screen", data={
        "job_text": "Engineer skilled in Python", "min_experience_years": "5",
    }, files={"files": ("resume.docx", sample_docx_stream.read(), "application/octet-stream")})
    assert response.status_code == 200
    candidate = response.json()["rankings"][0]
    assert candidate["experience_years"] is None
    assert candidate["component_scores"]["experience_score"] is None
    assert candidate["below_min_experience"] is False


@pytest.mark.parametrize(("text", "expected"), [
    ("3 years of professional experience building APIs.", 3),
    ("Graduated from a 4 year course. Volunteer for 2 years.", None),
    ("Certificate valid for 5 years.", None),
    ("200 years of experience", None),
])
def test_conservative_experience(text, expected):
    assert extract_evidenced_experience(text) == expected


def test_import_and_spoofed_documents(sample_docx_stream):
    imported = client.post("/api/jobs/document", files={"file": ("role.docx", sample_docx_stream.read(), "application/octet-stream")})
    assert imported.status_code == 200
    assert "FastAPI" in imported.json()["text"]
    fake = client.post("/api/jobs/document", files={"file": ("role.pdf", b"not a pdf", "application/pdf")})
    assert fake.status_code == 422
    wrong_mime = client.post("/api/jobs/document", files={"file": ("role.pdf", b"%PDF-fake", "text/plain")})
    assert wrong_mime.status_code == 400


def test_cors_only_allows_configured_origins():
    for origin, expected in [
        ("https://ai-resume-screening-three-kohl.vercel.app", True),
        ("https://arbitrary-other-project.vercel.app", False),
    ]:
        response = client.options("/api/screen", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
        assert ("access-control-allow-origin" in response.headers) is expected


def test_liveness_readiness_and_bounded_inference(monkeypatch):
    import asyncio

    started = threading.Event()
    release = threading.Event()

    def work():
        started.set()
        assert release.wait(10)
        return {}

    def fail():
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(api, "get_sentence_model", fail)
    with TestClient(api.app) as live:
        assert live.get("/api/health").status_code == 200
        for _ in range(100):
            response = live.get("/api/ready")
            if response.json() == {"status": "failed"}:
                break
        assert response.status_code == 503
        assert response.json() == {"status": "failed"}
        api.app.state.models = "ready"
        monkeypatch.setattr(api, "analyze_job", lambda text: api.JobAnalysis(raw_text=text, **work()))
        with ThreadPoolExecutor(max_workers=2) as pool:
            ticket = pool.submit(live.post, "/api/jobs/analyze", json={"text": "first"})
            try:
                assert started.wait(5)
                assert live.get("/api/health").status_code == 200
                async def saturate():
                    first = asyncio.create_task(api.run_ml(work))
                    try:
                        await asyncio.sleep(0)
                        with pytest.raises(api.HTTPException) as exc:
                            await api.run_ml(work)
                        assert exc.value.status_code == 503
                    finally:
                        release.set()
                        await first
                live.portal.call(saturate)
                assert ticket.result(timeout=5).status_code == 200
            finally:
                release.set()


def test_gemini_structured_output_filters_fabricated_evidence(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-test-key")
    resume = "Maintained Python API services with FastAPI."
    mock = MagicMock()
    generate = mock.__enter__.return_value.models.generate_content
    generate.return_value.text = json.dumps({
        "summary": "FastAPI experience is relevant to the role.",
        "strengths": ["FastAPI"], "experience_observations": [], "missing_qualifications": [],
        "areas_to_verify": [], "interview_questions": ["How did you version the API?"],
        "supporting_quotes": [resume, "This sentence does not exist."],
    })
    monkeypatch.setattr("google.genai.Client", lambda **kwargs: mock)
    result = generate_insights("Find a Python engineer", resume, ["Python"], [])
    assert result.status == "success"
    assert result.analysis.supporting_quotes == [resume]
    assert "untrusted" in generate.call_args.kwargs["config"].system_instruction
    generate.side_effect = httpx.ReadTimeout("test")
    assert generate_insights("Role", resume, [], []).status == "timeout"


def test_gemini_unconfigured_preserves_extracted_results(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    response = client.post("/api/insights", json={"job_text": "Build APIs", "candidate_name": "Candidate"})
    assert response.status_code == 200
    assert response.json()["status"] == "unconfigured"
    assert response.json()["analysis"] is None


def test_empty_resume_is_rejected_and_multipart_file_is_closed(monkeypatch):
    from io import BytesIO

    from docx import Document
    from starlette.datastructures import UploadFile

    contents = BytesIO()
    Document().save(contents)
    opened = []
    close = UploadFile.close

    async def remember(self):
        opened.append(self.file)
        await close(self)

    monkeypatch.setattr(UploadFile, "close", remember)
    result = client.post("/api/screen", data={"job_text": "Build Python APIs"}, files={
        "files": ("empty.docx", contents.getvalue(), "application/octet-stream"),
    })
    assert result.status_code == 422
    assert result.headers["cache-control"] == "no-store"
    assert opened and all(file.closed for file in opened)


@pytest.mark.parametrize(("code", "status"), [(429, "quota"), (404, "model_unavailable")])
def test_insights_reports_provider_availability(monkeypatch, code, status):
    from google.genai.errors import ClientError

    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-test-key")
    mock = MagicMock()
    mock.__enter__.return_value.models.generate_content.side_effect = ClientError(
        code, {"error": {"code": code, "message": "provider error"}}
    )
    monkeypatch.setattr("google.genai.Client", lambda **kwargs: mock)
    assert generate_insights("Role", "Resume", [], []).status == status



def test_api_import_leaves_heavy_models_for_background_startup():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-c", "import src.api, sys; assert not {'torch', 'spacy', 'sentence_transformers'} & sys.modules.keys()"],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr


def test_protected_fields_are_removed_before_modern_relevance_scoring():
    from src.schemas import WeightConfig
    from src.services.screening_service import rank

    base = "Built FastAPI services in Python and maintained PostgreSQL."
    resumes = [
        {"name": "first", "text": "Gender: Male\nAge: 28\nReligion: Hindu\n" + base},
        {"name": "second", "text": "Gender: Female\nAge: 51\nReligion: Jewish\n" + base},
    ]
    ranks = rank("Build FastAPI services with Python and PostgreSQL.", resumes,
                 WeightConfig(semantic_weight=.4, skill_weight=.3))
    assert ranks[0].match_score == ranks[1].match_score


def test_protected_terms_cannot_be_explicit_skill_criteria(sample_docx_stream):
    result = client.post("/api/screen", data={"job_text": "Engineer", "required_skills": "Python, Gender"}, files={
        "files": ("resume.docx", sample_docx_stream.read(), "application/octet-stream"),
    })
    assert result.status_code == 422
    assert "technical skills" in result.json()["detail"]
