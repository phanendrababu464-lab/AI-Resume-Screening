"""Automated validation tests for synthetic data assets and repository hygiene.

Validates Milestone M5 Acceptance Criteria:
1. Repository Cleanliness: No stray planning files in root; allowed files/directories only.
2. Synthetic Data Structure: Exactly 10 resumes (5 .pdf, 5 .docx) and 3 job descriptions (.txt).
3. Synthetic Resume Parsing: parse_resumes() produces valid ParsedResume models with complete sections.
4. Synthetic Job Parsing: analyze_job() produces valid JobAnalysis models with required and preferred skills.
5. Candidate Ranking & Scoring: rank() computes valid CandidateRanking instances with verified mathematics.
6. Demographic Invariance: Evaluation invariance across candidate demographic alterations on synthetic data.
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from src.config import BASE_DIR, DATA_DIR
from src.schemas import (
    CandidateRanking,
    ComponentScores,
    JobAnalysis,
    ParsedResume,
    ResumeSections,
)
from src.services.screening_service import analyze_job, parse_resumes, rank

RESUMES_DIR: Path = DATA_DIR / "resumes"
JOB_DESCRIPTIONS_DIR: Path = DATA_DIR / "job_descriptions"


# ==============================================================================
# Shared Fixtures
# ==============================================================================

@pytest.fixture(scope="module")
def resume_files() -> list[Path]:
    """Returns sorted list of resume file paths from data/resumes."""
    assert RESUMES_DIR.exists() and RESUMES_DIR.is_dir(), (
        f"Directory missing: {RESUMES_DIR}. Worker must generate synthetic resumes first."
    )
    files = sorted([f for f in RESUMES_DIR.iterdir() if not f.name.startswith(".")])
    return files


@pytest.fixture(scope="module")
def job_files() -> list[Path]:
    """Returns sorted list of job description file paths from data/job_descriptions."""
    assert JOB_DESCRIPTIONS_DIR.exists() and JOB_DESCRIPTIONS_DIR.is_dir(), (
        f"Directory missing: {JOB_DESCRIPTIONS_DIR}. Worker must generate synthetic job descriptions first."
    )
    files = sorted([f for f in JOB_DESCRIPTIONS_DIR.iterdir() if not f.name.startswith(".")])
    return files


@pytest.fixture(scope="module")
def parsed_resumes(resume_files: list[Path]) -> list[ParsedResume]:
    """Parses all synthetic resumes using screening_service.parse_resumes."""
    return parse_resumes(resume_files)


@pytest.fixture(scope="module")
def analyzed_jobs(job_files: list[Path]) -> list[JobAnalysis]:
    """Parses all synthetic job descriptions using screening_service.analyze_job."""
    jobs: list[JobAnalysis] = []
    for jf in job_files:
        text = jf.read_text(encoding="utf-8")
        job = analyze_job(text)
        jobs.append(job)
    return jobs


# ==============================================================================
# 1. Repository Cleanliness Tests
# ==============================================================================

class TestRepositoryCleanliness:
    """Validates that repository root contains no stray planning files or artifacts."""

    ALLOWED_ROOT_FILES = {
        ".env",
        ".gitignore",
        ".python-version",
        ".vercelignore",
        "README.md",
        "requirements.txt",
        "run_app.sh",
        "run_web.sh",
        "run_backend.sh",
        "pyproject.toml",
        "uv.lock",
        "vercel.json",
        "Procfile",
        "render.yaml",
    }

    ALLOWED_ROOT_DIRS = {
        "api",
        "data",
        "frontend",
        "src",
        "tests",
        "docs",
        ".pytest_cache",
        ".venv",
        ".git",
        "__pycache__",
    }

    DISALLOWED_PLANNING_KEYWORDS = [
        "plan",
        "todo",
        "task",
        "dispatch",
        "briefing",
        "progress",
        "handoff",
        "scratchpad",
        "notes",
    ]

    def test_no_stray_planning_files_in_root(self) -> None:
        """Verifies that no stray planning files exist in repository root."""
        root_items = list(BASE_DIR.iterdir())
        root_files = [f for f in root_items if f.is_file() and not f.name.startswith(".")]

        for f in root_files:
            lower_name = f.name.lower()
            for kw in self.DISALLOWED_PLANNING_KEYWORDS:
                assert kw not in lower_name, (
                    f"Stray planning file '{f.name}' found in repository root. "
                    f"Per Acceptance Criteria, all planning files must be kept under docs/teamwork/."
                )

        for f in root_files:
            if f.suffix in {".md", ".txt"}:
                assert f.name in self.ALLOWED_ROOT_FILES, (
                    f"Unauthorized root document '{f.name}'. Only {self.ALLOWED_ROOT_FILES} permitted in root."
                )

    def test_allowed_root_entries(self) -> None:
        """Verifies repository root contains only authorized folders and files, and Streamlit is retired."""
        assert not (BASE_DIR / "app").exists(), "Streamlit app directory must be retired"
        assert not (BASE_DIR / "src" / "app.py").exists(), "Legacy Streamlit src/app.py must be retired"
        for item in BASE_DIR.iterdir():
            if item.name in {".venv", ".git"}:
                continue
            if item.is_dir():
                assert item.name in self.ALLOWED_ROOT_DIRS, f"Unexpected directory in root: {item.name}"
            elif item.is_file():
                assert item.name in self.ALLOWED_ROOT_FILES, f"Unexpected file in root: {item.name}"

    def test_no_os_junk_files(self) -> None:
        """Verifies no OS junk files (.DS_Store, Thumbs.db, backup files) exist in repo."""
        disallowed_names = {".DS_Store", "Thumbs.db"}
        disallowed_suffixes = {".orig", ".bak", ".swp", ".tmp"}
        for root, dirs, files in os.walk(BASE_DIR):
            if any(p in root for p in ["/.venv", "/.git", "/.pytest_cache"]):
                continue
            for f in files:
                assert f not in disallowed_names, f"Found OS junk file: {Path(root) / f}"
                assert Path(f).suffix not in disallowed_suffixes, f"Found temporary/backup file: {Path(root) / f}"


# ==============================================================================
# 2. Synthetic Data Structure Tests
# ==============================================================================

class TestSyntheticDataStructure:
    """Validates dataset file counts, formats, and physical properties."""

    def test_resumes_file_count_and_extensions(self, resume_files: list[Path]) -> None:
        """Verifies exactly 10 resumes exist in data/resumes (5 .pdf, 5 .docx)."""
        assert len(resume_files) == 10, (
            f"Expected exactly 10 resumes in data/resumes/, found {len(resume_files)}"
        )

        pdf_files = [f for f in resume_files if f.suffix.lower() == ".pdf"]
        docx_files = [f for f in resume_files if f.suffix.lower() == ".docx"]

        assert len(pdf_files) == 5, f"Expected exactly 5 .pdf resumes, found {len(pdf_files)}"
        assert len(docx_files) == 5, f"Expected exactly 5 .docx resumes, found {len(docx_files)}"

        for f in resume_files:
            assert f.stat().st_size > 200, f"Resume file {f.name} is unexpectedly small ({f.stat().st_size} bytes)"

    def test_job_descriptions_file_count_and_extensions(self, job_files: list[Path]) -> None:
        """Verifies exactly 3 job descriptions exist in data/job_descriptions (.txt)."""
        assert len(job_files) == 3, (
            f"Expected exactly 3 job descriptions in data/job_descriptions/, found {len(job_files)}"
        )

        for f in job_files:
            assert f.suffix.lower() == ".txt", f"Job description {f.name} must be a .txt file"
            assert f.stat().st_size > 100, f"Job description {f.name} is unexpectedly small ({f.stat().st_size} bytes)"


# ==============================================================================
# 3. Synthetic Resume Ingestion & Section Parsing Tests
# ==============================================================================

class TestSyntheticResumeParsing:
    """Validates that every synthetic resume parses into a complete ParsedResume model."""

    def test_parsed_resume_count(self, parsed_resumes: list[ParsedResume]) -> None:
        """Verifies all 10 resumes parse successfully."""
        assert len(parsed_resumes) == 10

    @pytest.mark.parametrize("idx", list(range(10)))
    def test_individual_resume_model_integrity(self, parsed_resumes: list[ParsedResume], idx: int) -> None:
        """Verifies individual ParsedResume model fields."""
        resume = parsed_resumes[idx]
        assert isinstance(resume, ParsedResume)
        assert len(resume.filename) > 0
        assert len(resume.raw_text.strip()) > 50, f"{resume.filename} has empty or trivial raw text"
        assert len(resume.cleaned_text.strip()) > 50, f"{resume.filename} has empty cleaned text"

    @pytest.mark.parametrize("idx", list(range(10)))
    def test_resume_sections_non_empty(self, parsed_resumes: list[ParsedResume], idx: int) -> None:
        """Verifies every synthetic resume has non-empty standard sections."""
        resume = parsed_resumes[idx]
        assert isinstance(resume.sections, ResumeSections)
        assert len(resume.sections.skills.strip()) > 0, f"{resume.filename} has empty skills section"
        assert len(resume.sections.experience.strip()) > 0, f"{resume.filename} has empty experience section"
        assert len(resume.sections.education.strip()) > 0, f"{resume.filename} has empty education section"
        assert len(resume.sections.projects.strip()) > 0, f"{resume.filename} has empty projects section"

    @pytest.mark.parametrize("idx", list(range(10)))
    def test_resume_extracted_skills(self, parsed_resumes: list[ParsedResume], idx: int) -> None:
        """Verifies every synthetic resume extracts at least 3 valid technical skills."""
        resume = parsed_resumes[idx]
        assert isinstance(resume.skills, list)
        assert len(resume.skills) >= 3, (
            f"{resume.filename} extracted only {len(resume.skills)} skills ({resume.skills}); expected >= 3"
        )
        for skill in resume.skills:
            assert isinstance(skill, str) and skill.strip(), f"Invalid skill token: {skill!r}"

    @pytest.mark.parametrize("idx", list(range(10)))
    def test_resume_experience_years(self, parsed_resumes: list[ParsedResume], idx: int) -> None:
        """Verifies every synthetic resume has extracted candidate experience years."""
        resume = parsed_resumes[idx]
        assert resume.experience_years is not None, f"{resume.filename} has None experience_years"
        assert resume.experience_years >= 1.0, f"{resume.filename} experience_years ({resume.experience_years}) < 1.0"


# ==============================================================================
# 4. Synthetic Job Description Parsing Tests
# ==============================================================================

class TestSyntheticJobDescriptionParsing:
    """Validates that every synthetic job description parses into a complete JobAnalysis model."""

    def test_job_count(self, analyzed_jobs: list[JobAnalysis]) -> None:
        """Verifies all 3 job descriptions parse successfully."""
        assert len(analyzed_jobs) == 3

    @pytest.mark.parametrize("idx", [0, 1, 2])
    def test_individual_job_analysis(self, analyzed_jobs: list[JobAnalysis], idx: int) -> None:
        """Verifies individual JobAnalysis model fields."""
        job = analyzed_jobs[idx]
        assert isinstance(job, JobAnalysis)
        assert len(job.raw_text.strip()) > 50
        assert len(job.cleaned_text.strip()) > 50

    @pytest.mark.parametrize("idx", [0, 1, 2])
    def test_job_required_and_preferred_skills(self, analyzed_jobs: list[JobAnalysis], idx: int) -> None:
        """Verifies each job contains both required and preferred skills, and minimum experience."""
        job = analyzed_jobs[idx]
        assert len(job.required_skills) >= 2, f"Job {idx} has < 2 required skills: {job.required_skills}"
        assert len(job.preferred_skills) >= 1, f"Job {idx} has < 1 preferred skills: {job.preferred_skills}"
        assert set(job.all_skills) >= (set(job.required_skills) | set(job.preferred_skills))
        assert job.min_experience_years is not None, f"Job {idx} has None min_experience_years"
        assert job.min_experience_years >= 1.0, f"Job {idx} min_experience_years ({job.min_experience_years}) < 1.0"


# ==============================================================================
# 5. Candidate Ranking, Scoring & Mathematical Verification Tests
# ==============================================================================

class TestSyntheticScreeningAndRanking:
    """Validates multi-candidate ranking against all synthetic job descriptions."""

    @pytest.mark.parametrize("job_idx", [0, 1, 2])
    def test_ranking_resumes_against_job(
        self,
        analyzed_jobs: list[JobAnalysis],
        parsed_resumes: list[ParsedResume],
        job_idx: int,
    ) -> None:
        """Verifies ranking all 10 resumes against each synthetic job description."""
        job = analyzed_jobs[job_idx]
        rankings = rank(job=job, resumes=parsed_resumes)

        assert len(rankings) == 10
        assert [r.rank for r in rankings] == list(range(1, 11))

        # Descending sort by match_score
        for i in range(len(rankings) - 1):
            assert rankings[i].match_score >= rankings[i + 1].match_score

        # Score discrimination: ensures resumes receive differentiated scores
        score_spread = rankings[0].match_score - rankings[-1].match_score
        assert score_spread >= 15.0, f"Insufficient score discrimination: {score_spread:.2f} points"

    @pytest.mark.parametrize("job_idx", [0, 1, 2])
    def test_component_scores_and_composite_math(
        self,
        analyzed_jobs: list[JobAnalysis],
        parsed_resumes: list[ParsedResume],
        job_idx: int,
    ) -> None:
        """Verifies component scores bounds and composite formula calculation."""
        job = analyzed_jobs[job_idx]
        rankings = rank(job=job, resumes=parsed_resumes)

        for r in rankings:
            assert isinstance(r, CandidateRanking)
            assert 0.0 <= r.match_score <= 100.0
            comp = r.component_scores
            assert isinstance(comp, ComponentScores)
            assert 0.0 <= comp.required_skill_score <= 1.0
            assert 0.0 <= comp.preferred_skill_score <= 1.0
            assert 0.0 <= comp.semantic_score <= 1.0
            assert 0.0 <= comp.experience_score <= 1.0
            assert comp.tfidf_baseline_score is not None
            assert 0.0 <= comp.tfidf_baseline_score <= 1.0

            # Mathematical composite verification (default weights: 0.5, 0.2, 0.2, 0.1, penalty 0.6)
            expected_raw = (
                0.5 * comp.required_skill_score
                + 0.2 * comp.preferred_skill_score
                + 0.2 * comp.semantic_score
                + 0.1 * comp.experience_score
            )
            if r.below_min_experience:
                expected_raw *= 0.6
            expected_score = round(expected_raw * 100.0, 2)
            assert abs(r.match_score - expected_score) <= 0.02, (
                f"Composite score discrepancy for {r.candidate}: got {r.match_score}, expected {expected_score}"
            )

    @pytest.mark.parametrize("job_idx", [0, 1, 2])
    def test_matched_and_missing_skills_consistency(
        self,
        analyzed_jobs: list[JobAnalysis],
        parsed_resumes: list[ParsedResume],
        job_idx: int,
    ) -> None:
        """Verifies skill breakdown consistency against job description requirements."""
        job = analyzed_jobs[job_idx]
        rankings = rank(job=job, resumes=parsed_resumes)

        req_set = set(job.required_skills)
        pref_set = set(job.preferred_skills)

        for r in rankings:
            matched_req = set(r.matched_required_skills)
            missing_req = set(r.missing_required_skills)
            matched_pref = set(r.matched_preferred_skills)

            assert matched_req <= req_set
            assert missing_req == req_set - matched_req
            assert set(r.missing_skills) == missing_req
            assert matched_pref <= pref_set
            assert set(r.matched_skills) == matched_req | matched_pref


# ==============================================================================
# 6. Demographic Invariance Validation Tests
# ==============================================================================

class TestSyntheticDemographicInvariance:
    """Validates demographic evaluation invariance across candidate demographic alterations on synthetic resumes."""

    DEMOGRAPHIC_VARIANTS = [
        "David Miller",
        "Maria Garcia",
        "Priya Patel",
        "Wei Chen",
        "Alex Taylor",
        "Fatima Al-Mansoor",
    ]

    @pytest.mark.parametrize("job_idx", [0, 1, 2])
    @pytest.mark.parametrize("resume_idx", list(range(10)))
    def test_demographic_invariance_on_synthetic_resumes(
        self,
        parsed_resumes: list[ParsedResume],
        analyzed_jobs: list[JobAnalysis],
        resume_idx: int,
        job_idx: int,
    ) -> None:
        """Verifies that altering candidate name across demographic profiles produces exactly identical scores."""
        base_resume = parsed_resumes[resume_idx]
        target_job = analyzed_jobs[job_idx]

        raw_lines = base_resume.raw_text.splitlines()
        assert len(raw_lines) >= 3, f"Resume {base_resume.filename} text too short for variant test"

        # Construct demographic variants by substituting the candidate name header
        variants: list[ParsedResume] = []
        for name in self.DEMOGRAPHIC_VARIANTS:
            new_lines = list(raw_lines)
            for idx, line in enumerate(new_lines):
                if line.strip():
                    new_lines[idx] = name
                    break
            variant_text = "\n".join(new_lines)
            safe_name = name.replace(" ", "_")
            pr = ParsedResume(
                filename=f"variant_{safe_name}_{base_resume.filename}",
                raw_text=variant_text,
                cleaned_text=variant_text,
                skills=list(base_resume.skills),
                experience_years=base_resume.experience_years,
            )
            variants.append(pr)

        # Rank base resume and all demographic variants against the target job
        all_eval_resumes = [base_resume] + variants
        rankings = rank(job=target_job, resumes=all_eval_resumes)
        assert len(rankings) == len(all_eval_resumes)

        ref = rankings[0]
        for v in rankings[1:]:
            assert v.match_score == ref.match_score, (
                f"Score divergence on {base_resume.filename} against job {job_idx}: "
                f"{v.candidate} got {v.match_score}, ref got {ref.match_score}"
            )
            assert v.component_scores.required_skill_score == ref.component_scores.required_skill_score
            assert v.component_scores.preferred_skill_score == ref.component_scores.preferred_skill_score
            assert v.component_scores.semantic_score == ref.component_scores.semantic_score
            assert v.component_scores.experience_score == ref.component_scores.experience_score
            assert v.component_scores.tfidf_baseline_score == ref.component_scores.tfidf_baseline_score
            assert v.matched_skills == ref.matched_skills
            assert v.missing_skills == ref.missing_skills
