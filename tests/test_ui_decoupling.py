"""Automated verification and static audit for Streamlit UI Decoupling (Requirement R1)."""

import ast
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

REPO_ROOT = Path(__file__).resolve().parent.parent
STREAMLIT_APP_PATH = REPO_ROOT / "app" / "streamlit_app.py"
LEGACY_APP_PATH = REPO_ROOT / "src" / "app.py"


def test_ui_has_zero_domain_business_logic_imports() -> None:
    """R1 Audit: Verifies app/streamlit_app.py imports ONLY service layer and schemas."""
    assert STREAMLIT_APP_PATH.exists(), f"Missing {STREAMLIT_APP_PATH}"

    tree = ast.parse(STREAMLIT_APP_PATH.read_text(encoding="utf-8"))

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
                f"Violation of R1 Decoupling: app/streamlit_app.py illegally imports '{mod}'."
            )

    # Positively assert required service layer imports
    assert any("src.services.screening_service" in m for m in imported_modules), (
        "app/streamlit_app.py must import from src.services.screening_service"
    )
    assert any("src.schemas" in m for m in imported_modules), (
        "app/streamlit_app.py must import from src.schemas"
    )


def test_legacy_app_wrapper_delegates_to_streamlit_app() -> None:
    """R1 Audit: Verifies src/app.py delegates to app.streamlit_app."""
    assert LEGACY_APP_PATH.exists(), f"Missing {LEGACY_APP_PATH}"
    tree = ast.parse(LEGACY_APP_PATH.read_text(encoding="utf-8"))

    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    assert any("app.streamlit_app" in m for m in imported_modules), (
        "src/app.py must import from app.streamlit_app"
    )


def test_app_renders_smoke_test() -> None:
    """R1 Smoke Test: Headless execution of app/streamlit_app.py."""
    at = AppTest.from_file(str(STREAMLIT_APP_PATH)).run(timeout=30)
    assert not at.exception, f"app/streamlit_app.py crashed on render: {at.exception}"
    assert len(at.title) > 0
    assert "AI-Based Resume Screening System" in at.title[0].value


def test_legacy_app_wrapper_renders_smoke_test() -> None:
    """R1 Smoke Test: Headless execution of src/app.py wrapper."""
    # Ensure sys.modules does not retain shadowed 'app' from prior AppTest runs
    import sys
    if "app" in sys.modules and not hasattr(sys.modules["app"], "__path__"):
        del sys.modules["app"]

    at_legacy = AppTest.from_file(str(LEGACY_APP_PATH)).run(timeout=30)
    assert not at_legacy.exception, f"src/app.py crashed on render: {at_legacy.exception}"


def test_verify_schemas_path_guard() -> None:
    """Verifies that the environment guard function correctly detects inside vs outside schemas paths."""
    from app.streamlit_app import verify_schemas_path

    # Path inside repo root must return True
    inside_path = REPO_ROOT / "src" / "schemas.py"
    assert verify_schemas_path(REPO_ROOT, inside_path) is True

    # Path outside repo root must return False
    outside_path = Path("/Users/phanendra/Desktop/untitled folder 2/src/schemas.py")
    assert verify_schemas_path(REPO_ROOT, outside_path) is False

    outside_tmp = Path("/tmp/other_project/src/schemas.py")
    assert verify_schemas_path(REPO_ROOT, outside_tmp) is False


def test_screening_button_disabled_when_weights_invalid() -> None:
    """Verifies that the screening button is disabled and an error message is shown when weights != 1.00."""
    at = AppTest.from_file(str(STREAMLIT_APP_PATH)).run(timeout=20)
    assert not at.exception

    # Default weights sum to 1.00 -> button is enabled
    assert len(at.button) > 0
    assert at.button[0].disabled is False

    # Adjust required weight slider so sum is 0.8 + 0.2 + 0.2 + 0.1 = 1.30
    at.slider[0].set_value(0.8).run(timeout=20)
    assert not at.exception
    assert at.button[0].disabled is True
    assert len(at.error) > 0
    assert "Screening disabled: total scoring weights sum to 1.30" in at.error[0].value

