"""Automated verification and static audit for Web/API Decoupling and Streamlit Retirement (Requirement R1)."""

import ast
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.services.screening_service import verify_schemas_path

REPO_ROOT = Path(__file__).resolve().parent.parent
STREAMLIT_APP_PATH = REPO_ROOT / "app" / "streamlit_app.py"
LEGACY_APP_PATH = REPO_ROOT / "src" / "app.py"
API_PATH = REPO_ROOT / "src" / "api.py"
REQUIREMENTS_PATH = REPO_ROOT / "requirements.txt"
RUN_APP_PATH = REPO_ROOT / "run_app.sh"


def test_streamlit_and_legacy_app_are_retired() -> None:
    """R1 Audit: Verifies app/streamlit_app.py, src/app.py, and app/ are retired and do not exist."""
    assert not STREAMLIT_APP_PATH.exists(), f"Retired file still exists: {STREAMLIT_APP_PATH}"
    assert not RUN_APP_PATH.exists(), f"Retired launcher still exists: {RUN_APP_PATH}"
    assert not LEGACY_APP_PATH.exists(), f"Retired file still exists: {LEGACY_APP_PATH}"
    assert not (REPO_ROOT / "app").exists(), f"Retired directory still exists: {REPO_ROOT / 'app'}"


def test_api_has_zero_domain_business_logic_imports() -> None:
    """R1 Audit: Verifies src/api.py imports ONLY service layer and schemas."""
    assert API_PATH.exists(), f"Missing {API_PATH}"

    tree = ast.parse(API_PATH.read_text(encoding="utf-8"))

    forbidden_prefixes = (
        "src.parser",
        "src.preprocessor",
        "src.ranker",
        "src.skill_extractor",
        "src.job_parser",
        "src.anonymizer",
        "spacy",
        "sentence_transformers",
        "sklearn",
        "pdfplumber",
        "docx",
    )

    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    for mod in imported_modules:
        for forbidden in forbidden_prefixes:
            assert not mod.startswith(forbidden), (
                f"Violation of R1 Decoupling: src/api.py illegally imports '{mod}'."
            )

    # Positively assert required service layer imports
    assert any("src.services.screening_service" in m for m in imported_modules), (
        "src/api.py must import from src.services.screening_service"
    )
    assert any("src.schemas" in m for m in imported_modules), (
        "src/api.py must import from src.schemas"
    )


def test_requirements_has_no_streamlit_dependency() -> None:
    """R1 Audit: Verifies requirements.txt does not contain streamlit dependency."""
    assert REQUIREMENTS_PATH.exists(), f"Missing {REQUIREMENTS_PATH}"
    reqs_text = REQUIREMENTS_PATH.read_text(encoding="utf-8")
    assert "streamlit" not in reqs_text.lower(), "requirements.txt must not contain streamlit"


def test_verify_schemas_path_guard() -> None:
    """Verifies that the environment guard function correctly detects inside vs outside schemas paths."""
    # Path inside repo root must return True
    inside_path = REPO_ROOT / "src" / "schemas.py"
    assert verify_schemas_path(REPO_ROOT, inside_path) is True

    # Path outside repo root must return False
    outside_path = Path("/Users/phanendra/Desktop/untitled folder 2/src/schemas.py")
    assert verify_schemas_path(REPO_ROOT, outside_path) is False

    outside_tmp = Path("/tmp/other_project/src/schemas.py")
    assert verify_schemas_path(REPO_ROOT, outside_tmp) is False


def test_screening_endpoint_disabled_when_weights_invalid() -> None:
    """Verifies that the screening endpoint returns 400 Bad Request when weights do not sum to 1.00."""
    client = TestClient(app)
    # Adjust required weight slider so sum is 0.5 + 0.5 + 0.2 + 0.1 = 1.30
    response = client.post(
        "/api/screen",
        data={
            "job_text": "Software Engineer. Required: Python.",
            "use_sample_resumes": True,
            "required_skill_weight": 0.50,
            "preferred_skill_weight": 0.50,
            "semantic_weight": 0.20,
            "experience_weight": 0.10,
        },
    )
    assert response.status_code == 400
    assert "weights must sum to 1.00" in response.json()["detail"]
