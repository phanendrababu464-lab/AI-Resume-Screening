"""Integration and security test suite for the FastAPI backend (/api/*).

Validates:
- Operational health endpoint (/api/health)
- Sample retrieval endpoints (/api/samples)
- Job parsing and analysis endpoint (/api/jobs/analyze)
- Resume screening endpoint (/api/screen)
- Input validations: wrong file type, size > 5 MB, count > 20, weights sum != 1.0, empty job text
- Fault tolerance: corrupted file among valid files (partial batch recovery)
- Path traversal protection on /api/samples/resume/{filename} (HTTP & unit level)
- CSV export formula injection mitigation (=, +, -, @ single-quote escaping)
- CORS restrictions and absence of host server paths in error messages
"""

import io
from pathlib import Path

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

from src.api import app, clean_error_message, get_sample_resume_file, sanitize_csv_cell

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"


# ---------------------------------------------------------------------------
# 1. Health & Discovery Endpoints
# ---------------------------------------------------------------------------

def test_api_health() -> None:
    """Verifies that the health check endpoint returns 200 OK and expected metadata."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "ai-resume-screening"
    assert "version" in data


def test_api_samples_list() -> None:
    """Verifies that sample job descriptions and synthetic resumes are discovered."""
    response = client.get("/api/samples")
    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
    assert "resumes" in data
    assert len(data["jobs"]) >= 3
    assert len(data["resumes"]) >= 10


# ---------------------------------------------------------------------------
# 2. Path Traversal & Security Protection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "attack_payload",
    [
        "..%2fconfig.py",
        "%2e%2e%2fconfig.py",
        "%2e%2e%2f%2e%2e%2fconfig.py",
        "..%5cconfig.py",
        "%2e%2e%5cconfig.py",
        "/etc/passwd",
        "sub/folder/resume.pdf",
        "C:\\Windows\\win.ini",
        "%2e%2e",
        "%2fetc%2fpasswd",
    ],
)
def test_sample_resume_path_traversal_http_rejected(attack_payload: str) -> None:
    """Confirms GET /api/samples/resume/{filename} rejects encoded traversal requests with HTTP 400."""
    response = client.get(f"/api/samples/resume/{attack_payload}")
    assert response.status_code == 400
    detail = response.json().get("detail", "").lower()
    assert any(term in detail for term in ["traversal", "parent", "absolute", "not allowed", "denied"])


@pytest.mark.parametrize(
    "raw_traversal_payload",
    [
        "../config.py",
        "../../../../etc/passwd",
        "..",
        "/etc/passwd",
        "/Users/test/secret.txt",
        "C:\\Windows\\win.ini",
        "nested/path/file.pdf",
    ],
)
def test_sample_resume_path_traversal_endpoint_direct(raw_traversal_payload: str) -> None:
    """Directly verifies get_sample_resume_file logic blocks any un-encoded path traversal characters with HTTP 400."""
    with pytest.raises(HTTPException) as exc_info:
        get_sample_resume_file(raw_traversal_payload)
    assert exc_info.value.status_code == 400
    detail = str(exc_info.value.detail).lower()
    assert any(term in detail for term in ["traversal", "parent", "absolute", "not allowed", "denied"])


def test_sample_resume_valid_download() -> None:
    """Confirms GET /api/samples/resume/{filename} returns 200 for a valid sample file."""
    response = client.get("/api/samples/resume/resume_01.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert len(response.content) > 100


def test_sample_resume_not_found() -> None:
    """Confirms GET /api/samples/resume/{filename} returns 404 for a non-existent file inside directory."""
    response = client.get("/api/samples/resume/resume_9999_nonexistent.pdf")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 3. Job Analysis Endpoint
# ---------------------------------------------------------------------------

def test_analyze_job_valid() -> None:
    """Verifies /api/jobs/analyze extracts skills and minimum experience from raw text."""
    payload = {
        "text": (
            "Senior Backend Engineer\n"
            "Requirements: Must have 4+ years experience with Python and FastAPI.\n"
            "Preferred: Hands-on Docker and AWS experience."
        )
    }
    response = client.post("/api/jobs/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "Python" in data["required_skills"]
    assert "FastAPI" in data["required_skills"]
    assert "Docker" in data["preferred_skills"]
    assert data["min_experience_years"] == 4.0


def test_analyze_job_empty_text() -> None:
    """Verifies /api/jobs/analyze returns empty structure on blank text without crashing."""
    response = client.post("/api/jobs/analyze", json={"text": "   "})
    assert response.status_code == 200
    data = response.json()
    assert data["required_skills"] == []
    assert data["preferred_skills"] == []
    assert data["min_experience_years"] is None


# ---------------------------------------------------------------------------
# 4. Screening Validations & Error Handling
# ---------------------------------------------------------------------------

def test_screen_with_sample_resumes() -> None:
    """Verifies /api/screen executes end-to-end evaluation with sample data."""
    jd_text = (
        "Job Title: Senior Python Developer\n"
        "Requirements:\n"
        "- Hands-on Python and FastAPI\n"
        "- PostgreSQL database\n"
        "Experience: 3+ years"
    )
    response = client.post(
        "/api/screen",
        data={
            "job_text": jd_text,
            "use_sample_resumes": True,
            "required_skill_weight": 0.50,
            "preferred_skill_weight": 0.20,
            "semantic_weight": 0.20,
            "experience_weight": 0.10,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_candidates"] >= 10
    assert len(data["rankings"]) == data["total_candidates"]
    assert data["recommendation"]["best_candidate"] is not None
    assert "overall" in data["charts"]
    assert "composition" in data["charts"]
    assert "matrix" in data["charts"]


def test_screen_empty_job_text() -> None:
    """Verifies /api/screen rejects empty job description text with HTTP 400."""
    response = client.post(
        "/api/screen",
        data={"job_text": "   ", "use_sample_resumes": True},
    )
    assert response.status_code == 400
    assert "Job description text is required" in response.json()["detail"]


def test_screen_weights_not_summing_to_one() -> None:
    """Verifies /api/screen rejects unbalanced scoring weights with HTTP 400."""
    response = client.post(
        "/api/screen",
        data={
            "job_text": "Python Job",
            "use_sample_resumes": True,
            "required_skill_weight": 0.50,
            "preferred_skill_weight": 0.50,
            "semantic_weight": 0.20,
            "experience_weight": 0.10,  # Sum = 1.30
        },
    )
    assert response.status_code == 400
    assert "weights must sum to 1.00" in response.json()["detail"]


def test_screen_wrong_file_type() -> None:
    """Verifies /api/screen rejects unsupported file extensions with HTTP 400."""
    files = [
        ("files", ("resume.txt", b"Plain text resume content", "text/plain")),
    ]
    response = client.post(
        "/api/screen",
        data={"job_text": "Python Job"},
        files=files,
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_screen_file_over_5mb() -> None:
    """Verifies /api/screen rejects files exceeding 5 MB with HTTP 400."""
    oversized_bytes = b"0" * (5 * 1024 * 1024 + 1024)  # 5 MB + 1 KB
    files = [
        ("files", ("oversized_resume.pdf", oversized_bytes, "application/pdf")),
    ]
    response = client.post(
        "/api/screen",
        data={"job_text": "Python Job"},
        files=files,
    )
    assert response.status_code == 400
    assert "exceeds 5 MB limit" in response.json()["detail"]


def test_screen_more_than_100_files() -> None:
    """Verifies /api/screen rejects batches containing more than 100 files (101 files) with HTTP 400."""
    files = [
        ("files", (f"resume_{i}.pdf", b"%PDF-1.4 sample", "application/pdf"))
        for i in range(101)
    ]
    response = client.post(
        "/api/screen",
        data={"job_text": "Python Job"},
        files=files,
    )
    assert response.status_code == 400
    assert "Maximum of 100 files allowed" in response.json()["detail"]


def test_screen_20_and_100_files_accepted() -> None:
    """Verifies /api/screen accepts batches of 20 files and up to 100 files."""
    sample_pdf = (DATA_DIR / "resumes" / "resume_01.pdf").read_bytes()

    # Test 20 files batch
    files_20 = [
        ("files", (f"resume_{i}.pdf", sample_pdf, "application/pdf"))
        for i in range(20)
    ]
    resp_20 = client.post(
        "/api/screen",
        data={"job_text": "Python Developer. Required: Python."},
        files=files_20,
    )
    assert resp_20.status_code == 200
    assert resp_20.json()["total_candidates"] == 20

    # Test 100 files batch
    files_100 = [
        ("files", (f"resume_{i}.pdf", sample_pdf, "application/pdf"))
        for i in range(100)
    ]
    resp_100 = client.post(
        "/api/screen",
        data={"job_text": "Python Developer. Required: Python."},
        files=files_100,
    )
    assert resp_100.status_code == 200
    assert resp_100.json()["total_candidates"] == 100


def test_screen_total_batch_size_cap_exceeded(monkeypatch) -> None:
    """Reject the oversized request before parsing multipart uploads."""
    monkeypatch.setattr("src.api.MAX_BATCH_SIZE_BYTES", 1024 * 1024)
    chunk = b"A" * (1024 * 1024)
    files = [
        ("files", (f"resume_{i}.pdf", chunk, "application/pdf"))
        for i in range(3)
    ]
    response = client.post(
        "/api/screen",
        data={"job_text": "Python Job"},
        files=files,
    )
    assert response.status_code == 413
    assert "upload limit" in response.json()["detail"]


def test_screen_one_corrupted_file_among_good_ones() -> None:
    """Verifies fault-tolerance: one corrupted file is captured in file_errors while good ones are ranked."""
    good_pdf = (DATA_DIR / "resumes" / "resume_01.pdf").read_bytes()
    corrupt_bytes = b"%PDF-1.4 Corrupted content without headers or valid catalog"

    files = [
        ("files", ("good_candidate.pdf", good_pdf, "application/pdf")),
        ("files", ("corrupt_candidate.pdf", corrupt_bytes, "application/pdf")),
    ]

    response = client.post(
        "/api/screen",
        data={"job_text": "Job Title: Software Engineer\nRequirements: Python"},
        files=files,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_candidates"] == 1
    assert data["rankings"][0]["candidate"] == "good_candidate.pdf"
    assert len(data["file_errors"]) == 1
    assert data["file_errors"][0]["filename"] == "corrupt_candidate.pdf"
    # Confirm no local server paths leak in error description
    assert str(REPO_ROOT) not in data["file_errors"][0]["error"]
    assert "/Users/" not in data["file_errors"][0]["error"]


# ---------------------------------------------------------------------------
# 5. CSV Export & Formula Injection Sanitization
# ---------------------------------------------------------------------------

def test_export_csv_formula_injection_sanitization() -> None:
    """Verifies CSV export prefixes cells starting with formula triggers (=, +, -, @) with a single quote."""
    payload = {
        "job_title": "Senior Engineer",
        "rankings": [
            {
                "rank": 1,
                "candidate": "=SUM(A1:A10)",
                "match_score": 90.0,
                "below_min_experience": False,
                "component_scores": {
                    "required_skill_score": 1.0,
                    "preferred_skill_score": 0.8,
                    "semantic_score": 0.9,
                    "experience_score": 1.0,
                    "tfidf_baseline_score": 0.5,
                },
                "matched_required_skills": ["+CMD()", "Python"],
                "missing_required_skills": ["-10"],
                "related_skills_matched": ["@DDE_EXEC"],
            }
        ],
    }

    response = client.post("/api/export", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    csv_text = response.text

    # Candidate name starting with '=' must be escaped as '=SUM...
    assert "'=SUM(A1:A10)" in csv_text
    # Skills starting with '+', '-', '@' must be escaped
    assert "'+CMD()" in csv_text
    assert "'-10" in csv_text
    assert "'@DDE_EXEC" in csv_text


def test_sanitize_csv_cell_helper() -> None:
    """Direct unit tests for CSV cell sanitization function."""
    assert sanitize_csv_cell("=1+1") == "'=1+1"
    assert sanitize_csv_cell("+cmd|' /C calc'!A0") == "'+cmd|' /C calc'!A0"
    assert sanitize_csv_cell("-15") == "'-15"
    assert sanitize_csv_cell("@SUM") == "'@SUM"
    assert sanitize_csv_cell("Normal Candidate") == "Normal Candidate"
    assert sanitize_csv_cell(95.5) == "95.5"
    assert sanitize_csv_cell(None) == ""


def test_clean_error_message_helper() -> None:
    """Direct unit tests for server path scrubbing helper."""
    msg = f"Failed to open {REPO_ROOT}/src/parser.py on line 42"
    cleaned = clean_error_message(msg)
    assert str(REPO_ROOT) not in cleaned
    assert clean_error_message("/Users/secret/file.txt") == "<path>"
    assert clean_error_message("C:\\Users\\secret\\file.txt") == "<path>"


def test_api_jobs_analyze_multiple_jobs_warning() -> None:
    """Verifies /api/jobs/analyze surfaces has_multiple_jobs and warning message."""
    payload = {
        "text": (
            "Job 1: Backend Developer\n"
            "Required: Python, FastAPI\n\n"
            "Job 2: Data Engineer\n"
            "Required: Spark, SQL\n"
        )
    }
    response = client.post("/api/jobs/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["has_multiple_jobs"] is True
    assert data["multiple_jobs_warning"] is not None


def test_api_screen_weight_redistribution_and_duplicates() -> None:
    """Verifies /api/screen returns effective weights, redistribution note, and duplicate tags."""
    # Two copies of the same real sample resume PDF
    sample_pdf = (DATA_DIR / "resumes" / "resume_01.pdf").read_bytes()
    files = [
        ("files", ("cand_a.pdf", io.BytesIO(sample_pdf), "application/pdf")),
        ("files", ("cand_b.pdf", io.BytesIO(sample_pdf), "application/pdf")),
    ]
    # Job has only required skills, no min experience or preferred
    data = {
        "job_text": "Python Engineer. Required: Python, FastAPI.",
        "required_skill_weight": "0.50",
        "preferred_skill_weight": "0.20",
        "semantic_weight": "0.20",
        "experience_weight": "0.10",
        "experience_penalty": "0.60",
        "renormalize_weights": "true",
    }
    response = client.post("/api/screen", data=data, files=files)
    assert response.status_code == 200
    res = response.json()

    # Check effective weights
    eff_w = res.get("effective_weights", {})
    assert eff_w.get("required", 0) > 0.50
    assert eff_w.get("semantic", 0) > 0.20
    assert "preferred" in res.get("non_applicable_components", [])
    assert "experience" in res.get("non_applicable_components", [])
    assert res.get("weight_redistribution_note") is not None

    # Check tie and duplicate flags on rankings
    rankings = res.get("rankings", [])
    assert len(rankings) == 2
    # Both identical resumes have same score, so tie display T-1
    assert rankings[0]["rank_display"] == "T-1"
    assert rankings[1]["rank_display"] == "T-1"
    assert rankings[1]["is_duplicate"] is True
    assert rankings[1]["duplicate_of"] == "cand_a.pdf"


def test_anonymous_sample_screen_masks_candidate_in_results_and_export():
    response = client.post("/api/screen", data={
        "job_text": "Required: Python and FastAPI",
        "sample_resume_ids": "resume_01",
        "anonymize": "true",
    })
    assert response.status_code == 200
    results = response.json()
    candidate, = results["rankings"]
    assert candidate["candidate"] == "Candidate 1"
    assert candidate["resume_snippet"] == ""
    assert candidate["text_hash"] is None
    assert "resume_01" not in response.text
    exported = client.post("/api/export", json={"rankings": results["rankings"]})
    assert exported.status_code == 200
    assert "Candidate 1" in exported.text


def test_sample_selection_requires_a_known_id():
    response = client.post("/api/screen", data={
        "job_text": "Required: Python",
        "sample_resume_ids": "unknown_sample",
    })
    assert response.status_code == 400
