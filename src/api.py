"""FastAPI Backend for Resume Screening Web Application.

Exposes REST endpoints for:
- Health check (/api/health)
- Samples retrieval (/api/samples)
- Sample resume binary retrieval (/api/samples/resume/{filename:path})
- Real-time job analysis (/api/jobs/analyze)
- Resume screening & ranking (/api/screen)
- Results export to CSV (/api/export)

## Production architecture notes (Render free tier)

The /api/screen endpoint performs CPU-bound ML inference (SentenceTransformer.encode)
that can take 5-8 seconds on first call (cold model load) and <0.3s on subsequent warm
calls. On Render's free tier, one uvicorn worker handles all requests.

ROOT CAUSE OF 502/503/429:
- `async def screen_resumes_endpoint` calls `rank()` synchronously inside the event loop.
- `rank()` calls `SentenceTransformer.encode()` which is a pure CPU blocking operation.
- While encode() runs, the event loop is fully blocked → no other request (including
  /api/health) can be processed → Render's upstream proxy eventually times out → 502.
- Subsequent health checks pile up → 429 (rate limit hit on the proxy level) or 503.

FIX: Run the CPU-bound screening work in a thread-pool executor via
asyncio.get_event_loop().run_in_executor() so the event loop stays free to serve
health checks and other lightweight requests while screening is in progress.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from contextlib import asynccontextmanager
import csv
import io
import logging
import os
from pathlib import Path
import re
import time
from typing import Any, Optional
import urllib.parse

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from src.config import (
    MAX_BATCH_SIZE_BYTES,
    MAX_FILE_SIZE_BYTES,
    MAX_RESUMES_PER_BATCH,
)
from src.schemas import (
    CandidateRanking,
    JobAnalysis,
    Recommendation,
    WeightConfig,
)
from src.services.gemini_service import (
    GeminiValidationResult,
    is_gemini_available,
    validate_candidate_with_gemini,
)
from src.services.screening_service import (
    analyze_job,
    build_recommendation,
    get_applicable_components,
    get_candidate_breakdown_chart_data,
    get_overall_ranking_chart_data,
    get_score_composition_chart_data,
    get_skill_matrix_chart_data,
    get_sentence_model,
    parse_resumes,
    rank,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

MAX_FILES_COUNT = MAX_RESUMES_PER_BATCH
ALLOWED_FILE_EXTENSIONS = {".pdf", ".docx"}

# ---------------------------------------------------------------------------
# Thread-pool for CPU-bound ML inference
# A single-thread pool prevents memory spikes from simultaneous model calls
# on a constrained host (Render free tier has 512 MB RAM shared).
# ---------------------------------------------------------------------------
_SCREENING_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="screening_worker",
)

@asynccontextmanager
async def lifespan(application: FastAPI):
    await _warm_up_model()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="AI Resume Screening API",
    description="Backend API powering the Resume Screening web application.",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# CORS Configuration: Local dev + Vercel deployed frontend domains
# ---------------------------------------------------------------------------
default_allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://ai-resume-screening-three-kohl.vercel.app",
]

cors_origins_env = os.getenv("CORS_ORIGINS", "").strip()
if cors_origins_env:
    env_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip() and o.strip() != "*"]
    allowed_origins = list(dict.fromkeys(default_allowed_origins + env_origins))
else:
    allowed_origins = default_allowed_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^https://.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Warm up ML model on startup (avoid first-request cold-start penalty)
# ---------------------------------------------------------------------------
async def _warm_up_model() -> None:
    """Pre-load SentenceTransformer in the screening thread-pool on startup.

    Prevents the first real /api/screen request from blocking 5-8 seconds
    while the model is loaded from disk.
    """
    loop = asyncio.get_event_loop()

    def _load() -> None:
        t0 = time.time()
        try:
            model = get_sentence_model()
            # Run one encode to populate torch JIT caches
            model.encode(["warmup"], show_progress_bar=False, convert_to_numpy=True)
            logger.info("SentenceTransformer warm-up complete in %.2fs", time.time() - t0)
        except Exception as exc:  # pragma: no cover
            logger.warning("SentenceTransformer warm-up failed (non-fatal): %s", exc)

    await loop.run_in_executor(_SCREENING_EXECUTOR, _load)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clean_error_message(err_msg: str) -> str:
    """Sanitizes error messages to prevent exposing server filesystem paths."""
    if not err_msg:
        return ""
    cleaned = str(err_msg)
    if str(REPO_ROOT) in cleaned:
        cleaned = cleaned.replace(str(REPO_ROOT), ".")
    # Redact absolute Unix file paths (/Users/..., /home/..., /var/...)
    cleaned = re.sub(r'(/[a-zA-Z0-9_\-\.]+)+/[a-zA-Z0-9_\-\.]+', '<path>', cleaned)
    # Redact absolute Windows file paths (C:\...)
    cleaned = re.sub(r'[A-Za-z]:\\[a-zA-Z0-9_\-\\.]+', '<path>', cleaned)
    return cleaned


def sanitize_csv_cell(value: Any) -> Any:
    """Prefixes cell values starting with formula characters (=, +, -, @) with a single quote."""
    if value is None:
        return ""
    val_str = str(value)
    if val_str and val_str[0] in ("=", "+", "-", "@"):
        return f"'{val_str}"
    return val_str


# ---------------------------------------------------------------------------
# CPU-bound screening worker (runs in thread-pool, not event loop)
# ---------------------------------------------------------------------------

def _run_screening_sync(
    files_to_parse: list[Any],
    job_text: str,
    weights: WeightConfig,
    anonymize: bool = False,
) -> tuple[JobAnalysis, list[Any], list[Any], list[CandidateRanking], Recommendation, dict[str, Any], list[str], dict[str, float], Optional[str]]:
    """Execute the full ML screening pipeline synchronously.

    Intended to be called via run_in_executor() so the FastAPI event loop
    is never blocked during CPU-heavy SentenceTransformer inference.

    Returns:
        (job_analysis, parsed_resumes, file_errors, rankings, recommendation,
         charts, non_app_comp, eff_w, note)
    """
    file_errors: list[Any] = []

    job_analysis = analyze_job(job_text)
    app_comp, non_app_comp, eff_w, note = get_applicable_components(job_analysis, weights)

    # Parse all resumes, collecting per-file errors without aborting batch
    parsed_resumes: list[Any] = []
    for index, item in enumerate(files_to_parse, start=1):
        fname = getattr(item, "name", str(item))
        base_name = f"Candidate {index}" if anonymize else Path(fname).name
        try:
            prs = parse_resumes([item])
            if anonymize:
                for resume in prs:
                    resume.filename = base_name
            if prs:
                parsed_resumes.extend(prs)
        except Exception as exc:
            safe_msg = "Could not parse resume." if anonymize else clean_error_message(str(exc))
            logger.warning("Resume parse error for %s: %s", base_name, safe_msg)
            file_errors.append({"filename": base_name, "error": safe_msg})

    if not parsed_resumes:
        raise ValueError("All provided resumes failed text extraction.")

    # Rank candidates (this calls SentenceTransformer.encode internally)
    t0 = time.time()
    rankings = rank(job=job_analysis, resumes=parsed_resumes, weights=weights)
    logger.info(
        "Ranked %d candidates in %.2fs", len(rankings), time.time() - t0
    )

    if anonymize:
        for candidate in rankings:
            candidate.resume_snippet = ""
            candidate.text_hash = None

    recommendation = build_recommendation(rankings, job_analysis)

    # Chart datasets
    overall_chart = get_overall_ranking_chart_data(rankings)
    composition_chart = get_score_composition_chart_data(rankings, weights)
    matrix_chart = get_skill_matrix_chart_data(rankings, job_analysis)
    breakdowns = {r.candidate: get_candidate_breakdown_chart_data(r) for r in rankings}

    charts: dict[str, Any] = {
        "overall": overall_chart,
        "composition": composition_chart,
        "matrix": matrix_chart,
        "breakdowns": breakdowns,
    }

    return (
        job_analysis,
        parsed_resumes,
        file_errors,
        rankings,
        recommendation,
        charts,
        non_app_comp,
        eff_w,
        note,
    )


# ---------------------------------------------------------------------------
# Request & Response Models
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    service: str = "ai-resume-screening"
    max_resumes_per_batch: int = MAX_RESUMES_PER_BATCH
    gemini_available: bool = False


class ValidateResumeRequest(BaseModel):
    job_text: str
    candidate_name: str
    candidate_text: Optional[str] = ""
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)


class SampleJobItem(BaseModel):
    id: str
    title: str
    filename: str
    text: str


class SampleResumeItem(BaseModel):
    id: str
    filename: str
    size: int


class SamplesResponse(BaseModel):
    jobs: list[SampleJobItem]
    resumes: list[SampleResumeItem]


class JobAnalyzeRequest(BaseModel):
    text: str


class JobAnalyzeResponse(BaseModel):
    job_title: Optional[str] = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    all_skills: list[str] = Field(default_factory=list)
    min_experience_years: Optional[float] = None
    has_multiple_jobs: bool = False
    multiple_jobs_warning: Optional[str] = None


class FileErrorItem(BaseModel):
    filename: str
    error: str


class ScreenResponse(BaseModel):
    job: JobAnalysis
    rankings: list[CandidateRanking]
    recommendation: Recommendation
    charts: dict[str, Any]
    total_candidates: int
    file_errors: list[FileErrorItem] = Field(default_factory=list)
    effective_weights: dict[str, float] = Field(default_factory=dict)
    non_applicable_components: list[str] = Field(default_factory=list)
    weight_redistribution_note: Optional[str] = None


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
def root_health_check() -> dict[str, Any]:
    """Root endpoint for cloud hosting health checks (Render, Vercel, Railway)."""
    return {
        "status": "ok",
        "service": "ai-resume-screening",
        "version": "1.0.0",
        "health": "/api/health",
        "docs": "/docs",
        "gemini_available": is_gemini_available(),
    }


@app.get("/api/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Returns backend API operational health status.

    This endpoint is intentionally lightweight: no ML inference, no I/O.
    It must remain fast even while /api/screen is running in a thread-pool.
    """
    return HealthResponse(
        status="ok",
        version="1.0.0",
        service="ai-resume-screening",
        max_resumes_per_batch=MAX_RESUMES_PER_BATCH,
        gemini_available=is_gemini_available(),
    )


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    """Returns runtime configuration limits and feature flags."""
    return {
        "max_resumes_per_batch": MAX_RESUMES_PER_BATCH,
        "max_file_size_bytes": MAX_FILE_SIZE_BYTES,
        "max_batch_size_bytes": MAX_BATCH_SIZE_BYTES,
        "gemini_available": is_gemini_available(),
    }


@app.post("/api/resumes/validate", response_model=GeminiValidationResult)
def validate_resume_endpoint(payload: ValidateResumeRequest) -> GeminiValidationResult:
    """Evaluates candidate depth, authenticity, and generates tailored interview questions via Gemini."""
    if not payload.job_text or not payload.job_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job text cannot be empty for AI validation.",
        )
    return validate_candidate_with_gemini(
        job_description=payload.job_text,
        candidate_name=payload.candidate_name,
        candidate_text=payload.candidate_text or "",
        matched_skills=payload.matched_skills,
        missing_skills=payload.missing_skills,
    )


@app.get("/api/samples", response_model=SamplesResponse)
def get_samples() -> SamplesResponse:
    """Lists available sample job descriptions and synthetic test resumes."""
    jobs: list[SampleJobItem] = []
    jd_dir = DATA_DIR / "job_descriptions"
    if jd_dir.exists():
        for f in sorted(jd_dir.glob("*.txt")):
            text = f.read_text(encoding="utf-8")
            title = f.stem.replace("_", " ").title()
            for line in text.splitlines():
                if line.lower().startswith("job title:"):
                    title = line.split(":", 1)[1].strip()
                    break
            jobs.append(
                SampleJobItem(
                    id=f.stem,
                    title=title,
                    filename=f.name,
                    text=text,
                )
            )

    resumes: list[SampleResumeItem] = []
    res_dir = DATA_DIR / "resumes"
    if res_dir.exists():
        for f in sorted(res_dir.glob("resume_*.*")):
            resumes.append(
                SampleResumeItem(
                    id=f.stem,
                    filename=f.name,
                    size=f.stat().st_size,
                )
            )

    return SamplesResponse(jobs=jobs, resumes=resumes)


@app.get("/api/samples/resume/{filename:path}")
def get_sample_resume_file(filename: str):
    """Downloads a sample resume binary file with strict path traversal security checks."""
    if not filename or not filename.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename parameter cannot be empty.",
        )

    # 1. Decode URL-encoded variations
    decoded = urllib.parse.unquote(filename)

    # 2. Reject path separators, parent directory traversal, and encoded variants
    if any(sep in filename or sep in decoded for sep in ("/", "\\")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path traversal characters not allowed.",
        )
    if ".." in filename or ".." in decoded:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parent directory navigation ('..') not allowed.",
        )
    if Path(filename).is_absolute() or Path(decoded).is_absolute():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Absolute paths not allowed.",
        )

    # 3. Resolve path and confirm it strictly resides within samples directory
    samples_dir = (DATA_DIR / "resumes").resolve()
    target_path = (samples_dir / decoded).resolve()

    try:
        target_path.relative_to(samples_dir)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Access outside samples directory denied.",
        )

    if not target_path.exists() or not target_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sample resume '{decoded}' not found.",
        )

    media_type = "application/pdf" if decoded.lower().endswith(".pdf") else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return Response(
        content=target_path.read_bytes(),
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{decoded}"'},
    )


@app.post("/api/jobs/analyze", response_model=JobAnalyzeResponse)
def analyze_job_endpoint(payload: JobAnalyzeRequest) -> JobAnalyzeResponse:
    """Analyzes job description text and extracts required & preferred skills plus minimum experience."""
    if not payload.text or not payload.text.strip():
        return JobAnalyzeResponse()

    analysis = analyze_job(payload.text)
    job_title = analysis.job_title
    if not job_title:
        for line in analysis.raw_text.splitlines():
            line_clean = line.strip()
            if line_clean.lower().startswith("job title:"):
                job_title = line_clean.split(":", 1)[1].strip()
                break
            elif line_clean and not job_title and len(line_clean) < 60:
                job_title = line_clean

    return JobAnalyzeResponse(
        job_title=job_title,
        required_skills=analysis.required_skills,
        preferred_skills=analysis.preferred_skills,
        all_skills=analysis.all_skills,
        min_experience_years=analysis.min_experience_years,
        has_multiple_jobs=analysis.has_multiple_jobs,
        multiple_jobs_warning=analysis.multiple_jobs_warning,
    )


@app.post("/api/screen", response_model=ScreenResponse)
async def screen_resumes_endpoint(
    job_text: str = Form(...),
    files: list[UploadFile] = File(default=[]),
    use_sample_resumes: bool = Form(default=False),
    sample_resume_ids: Optional[str] = Form(default=None),
    required_skill_weight: float = Form(default=0.50),
    preferred_skill_weight: float = Form(default=0.20),
    semantic_weight: float = Form(default=0.20),
    experience_weight: float = Form(default=0.10),
    experience_penalty: float = Form(default=0.60),
    renormalize_weights: bool = Form(default=True),
    anonymize: bool = Form(default=False),
) -> ScreenResponse:
    """Main screening pipeline with file type/size/count limits, error sanitization, and score ranking.

    ## Event-loop safety

    All CPU-bound work (PDF/DOCX parsing, SentenceTransformer.encode, TF-IDF,
    scoring) is offloaded to a dedicated ThreadPoolExecutor so the asyncio event
    loop remains free to serve /api/health and other lightweight requests while
    screening is in progress. This is what prevents 502/503 on Render's single-
    worker deployment.
    """
    t_start = time.time()

    # 1. Validate Job Text
    if not job_text or not job_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job description text is required.",
        )

    # 2. Validate File Count Limit
    if len(files) > MAX_FILES_COUNT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum of {MAX_FILES_COUNT} files allowed per batch.",
        )

    # 3. Validate Weight Sums
    total_weights = required_skill_weight + preferred_skill_weight + semantic_weight + experience_weight
    if abs(total_weights - 1.0) > 0.005:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Scoring weights must sum to 1.00 (currently {total_weights:.2f}).",
        )

    # 4. Read & validate uploads in the event loop (async I/O, non-blocking)
    files_to_parse: list[Any] = []
    total_batch_bytes = 0

    for uf in files:
        if not uf.filename:
            continue

        ext = Path(uf.filename).suffix.lower()
        if ext not in ALLOWED_FILE_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type for '{uf.filename}'. Only PDF and DOCX files are allowed.",
            )

        content = await uf.read()
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File '{uf.filename}' exceeds 5 MB limit ({len(content)} bytes).",
            )

        total_batch_bytes += len(content)
        if total_batch_bytes > MAX_BATCH_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Total batch size exceeds {MAX_BATCH_SIZE_BYTES // (1024 * 1024)} MB limit.",
            )

        stream = io.BytesIO(content)
        stream.name = uf.filename
        files_to_parse.append(stream)

    # 5. Add Sample Resumes if Requested
    if use_sample_resumes or sample_resume_ids:
        res_dir = DATA_DIR / "resumes"
        if res_dir.exists():
            samples = sorted(f for f in res_dir.glob("resume_*.*") if f.is_file() and f.suffix.lower() in ALLOWED_FILE_EXTENSIONS)
            if sample_resume_ids:
                by_id = {f.stem: f for f in samples}
                selected = []
                for sample_id in dict.fromkeys(x.strip() for x in sample_resume_ids.split(",") if x.strip()):
                    sample = by_id.get(sample_id) or by_id.get(f"resume_{sample_id}")
                    if sample is None:
                        raise HTTPException(status_code=400, detail="Unknown sample resume ID.")
                    selected.append(sample)
            else:
                selected = samples
            files_to_parse.extend(str(sample) for sample in selected)

    if len(files_to_parse) > MAX_FILES_COUNT:
        raise HTTPException(status_code=400, detail=f"Maximum batch size is {MAX_FILES_COUNT} resumes.")

    if not files_to_parse:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid resumes were provided for screening.",
        )

    weights = WeightConfig(
        required_skill_weight=required_skill_weight,
        preferred_skill_weight=preferred_skill_weight,
        semantic_weight=semantic_weight,
        experience_weight=experience_weight,
        experience_penalty=experience_penalty,
        renormalize_weights=renormalize_weights,
    )

    logger.info(
        "Starting screening: %d file(s), %.1f KB total",
        len(files_to_parse),
        total_batch_bytes / 1024,
    )

    # 6. Offload ALL CPU-bound screening work to the dedicated thread-pool
    #    so the event loop remains free to serve /api/health during this time.
    loop = asyncio.get_event_loop()
    try:
        (
            job_analysis,
            parsed_resumes,
            raw_file_errors,
            rankings,
            recommendation,
            charts,
            non_app_comp,
            eff_w,
            note,
        ) = await loop.run_in_executor(
            _SCREENING_EXECUTOR,
            _run_screening_sync,
            files_to_parse,
            job_text,
            weights,
            anonymize,
        )
    except ValueError as exc:
        # Raised by _run_screening_sync when ALL resumes fail parsing
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("Unexpected screening error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during resume screening. Please try again.",
        )

    file_errors = [FileErrorItem(**e) for e in raw_file_errors]

    logger.info(
        "Screening complete: %d ranked, %d errors, total %.2fs",
        len(rankings),
        len(file_errors),
        time.time() - t_start,
    )

    return ScreenResponse(
        job=job_analysis,
        rankings=rankings,
        recommendation=recommendation,
        charts=charts,
        total_candidates=len(rankings),
        file_errors=file_errors,
        effective_weights=eff_w,
        non_applicable_components=non_app_comp,
        weight_redistribution_note=note,
    )


class ExportRequest(BaseModel):
    rankings: list[dict[str, Any]]
    job_title: Optional[str] = "Screening Results"


@app.post("/api/export")
def export_csv_endpoint(payload: ExportRequest):
    """Generates a downloadable CSV containing evaluation rankings with formula injection sanitization."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Rank",
        "Candidate",
        "Composite Score (%)",
        "Below Min Experience",
        "Required Skill Score",
        "Preferred Skill Score",
        "Semantic Score",
        "Experience Score",
        "TF-IDF Baseline Score",
        "Matched Required Skills",
        "Missing Required Skills",
        "Related Skills Matched",
    ])

    for r in payload.rankings:
        cs = r.get("component_scores", {})
        raw_row = [
            r.get("rank_display") or r.get("rank", ""),
            r.get("candidate", ""),
            r.get("match_score", ""),
            "Yes" if r.get("below_min_experience") else "No",
            cs.get("required_skill_score", ""),
            cs.get("preferred_skill_score", ""),
            cs.get("semantic_score", ""),
            cs.get("experience_score", ""),
            cs.get("tfidf_baseline_score", ""),
            "; ".join(r.get("matched_required_skills", [])),
            "; ".join(r.get("missing_required_skills", [])),
            "; ".join(r.get("related_skills_matched", [])),
        ]
        # Sanitize each cell to prevent CSV formula injection (=, +, -, @)
        writer.writerow([sanitize_csv_cell(cell) for cell in raw_row])

    output.seek(0)
    safe_title = re.sub(r'[^a-zA-Z0-9_\-]', '_', payload.job_title or "Screening")
    filename = f"{safe_title.lower()}_results.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
