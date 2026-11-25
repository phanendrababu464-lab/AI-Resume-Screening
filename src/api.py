from __future__ import annotations

import asyncio
import concurrent.futures
from contextlib import asynccontextmanager
import csv
import io
import logging
import math
import os
from pathlib import Path
import re
import time
from typing import Any, Optional
import urllib.parse

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field
from starlette.formparsers import MultiPartException
from src.services.document_service import check_document, read_job_text
from src.services.insights import InsightsResponse, generate_insights

from src.config import (
    EMBEDDING_MODEL_NAME,
    EMBEDDING_REVISION,
    TFIDF_MAX_NGRAM,
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
    get_skill_extractor,
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
    application.state.models = "initializing"
    task = asyncio.create_task(_warm_up_model())
    try:
        yield
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        del application.state.models


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


# ---------------------------------------------------------------------------
# Warm up ML model on startup (avoid first-request cold-start penalty)
# ---------------------------------------------------------------------------
async def _warm_up_model() -> None:
    def load() -> None:
        get_sentence_model().encode(["warmup"], show_progress_bar=False, convert_to_numpy=True)
        get_skill_extractor()

    try:
        await asyncio.get_running_loop().run_in_executor(_SCREENING_EXECUTOR, load)
    except Exception as exc:
        app.state.models = "failed"
        logger.error("Model initialization failed (%s)", type(exc).__name__)
    else:
        app.state.models = "ready"
        logger.info("Screening models ready")


_pending_ml = 0


async def run_ml(function, *args):
    """Keep a slot until the thread finishes, even if the HTTP request ends."""
    global _pending_ml
    state = getattr(app.state, "models", "ready")
    if state != "ready":
        raise HTTPException(503, detail="Screening models are " + state + ".", headers={"Retry-After": "10"})
    if _pending_ml >= 2:
        raise HTTPException(503, detail="Screening is busy. Try again shortly.", headers={"Retry-After": "10"})
    _pending_ml += 1

    def finished(future):
        global _pending_ml
        _pending_ml -= 1
        if not future.cancelled():
            future.exception()

    future = asyncio.get_running_loop().run_in_executor(_SCREENING_EXECUTOR, function, *args)
    future.add_done_callback(finished)
    try:
        return await asyncio.wait_for(asyncio.shield(future), timeout=105)
    except TimeoutError as exc:
        raise HTTPException(504, detail="Processing timed out. Try a smaller batch.") from exc


class RequestLimits:
    def __init__(self, app):
        self.app = app
        self.uploads = 0

    async def __call__(self, scope, receive, send):
        path = scope.get("path")
        if scope["type"] != "http" or scope.get("method") != "POST":
            return await self.app(scope, receive, send)
        upload = path in {"/api/screen", "/api/jobs/document"}
        limit = MAX_BATCH_SIZE_BYTES + 1024 * 1024 if path == "/api/screen" else MAX_FILE_SIZE_BYTES + 1024 * 1024 if upload else 512 * 1024
        length = dict(scope["headers"]).get(b"content-length", b"0")
        if not length.isdigit() or int(length) > limit:
            return await JSONResponse({"detail": "Request exceeds the upload limit."}, 413)(scope, receive, send)
        if upload and self.uploads >= 2:
            return await JSONResponse({"detail": "Uploads are busy. Try again shortly."}, 503, headers={"Retry-After": "10"})(scope, receive, send)
        self.uploads += int(upload)
        received = 0

        async def bounded_receive():
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > limit:
                if upload:
                    raise MultiPartException("Request exceeds the upload limit.")
                raise HTTPException(413, detail="Request exceeds the upload limit.")
            return message

        async def send_private(message):
            if message["type"] == "http.response.start":
                message["headers"] = [*message.get("headers", []), (b"cache-control", b"no-store")]
            await send(message)

        try:
            await self.app(scope, bounded_receive, send_private)
        finally:
            self.uploads -= int(upload)


async def read_document(upload: UploadFile) -> io.BytesIO:
    filename = upload.filename or ""
    name = re.split(r"[/\\]", filename)[-1]
    ext = Path(name).suffix.lower()
    name = name[:200 - len(ext)] + name[-len(ext):] if ext and len(name) > 200 else name
    mime = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    if ext not in mime:
        raise HTTPException(400, detail="Unsupported file type. Use PDF or DOCX.")
    if upload.content_type not in {None, "", "application/octet-stream", mime[ext]}:
        raise HTTPException(400, detail="The document MIME type does not match its extension.")
    content = await upload.read(MAX_FILE_SIZE_BYTES + 1)
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(400, detail=f"File exceeds {MAX_FILE_SIZE_BYTES / (1024 * 1024):g} MB limit.")
    stream = io.BytesIO(content)
    stream.name = name
    return stream


app.add_middleware(RequestLimits)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    if val_str and (val_str[0] in "\t\r\n" or val_str.lstrip().lstrip("\ufeff").startswith(("=", "+", "-", "@"))):
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
    overrides: dict | None = None,
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
    if overrides:
        extractor = get_skill_extractor()
        for field, value in overrides.items():
            if field.endswith("_skills"):
                configured = [word.strip() for word in value.split(",") if word.strip()]
                skills = [extractor.lookup.get(word.casefold()) for word in configured]
                if any(skill is None for skill in skills):
                    raise ValueError("Use technical skills from the supported taxonomy in the criteria fields.")
                value = list(dict.fromkeys(skills))
            setattr(job_analysis, field, value)
        required = {skill.casefold() for skill in job_analysis.required_skills}
        job_analysis.preferred_skills = [skill for skill in job_analysis.preferred_skills if skill.casefold() not in required]
        job_analysis.all_skills = job_analysis.required_skills + job_analysis.preferred_skills
    app_comp, non_app_comp, eff_w, note = get_applicable_components(job_analysis, weights)

    # Parse all resumes, collecting per-file errors without aborting batch
    parsed_resumes: list[Any] = []
    for index, item in enumerate(files_to_parse, start=1):
        fname = getattr(item, "name", str(item))
        base_name = f"Candidate {index}" if anonymize else Path(fname).name
        try:
            if isinstance(item, io.BytesIO):
                check_document(item)
            prs = parse_resumes([item])
            if not prs or not prs[0].raw_text.strip():
                raise ValueError("Document contains no readable text.")
            if anonymize:
                prs[0].filename = base_name
            elif weights.skill_weight is not None:
                prs[0].source_filename = base_name
                existing = {resume.filename for resume in parsed_resumes}
                while prs[0].filename in existing:
                    prs[0].filename += f" ({index})"
            if prs:
                parsed_resumes.extend(prs)
        except Exception as exc:
            safe_msg = "Could not read the document. Use a text-based PDF or valid DOCX."
            logger.info("Resume rejected (%s)", type(exc).__name__)
            file_errors.append({"filename": base_name, "error": safe_msg})

    if not parsed_resumes:
        raise ValueError("All provided resumes failed text extraction.")

    # Rank candidates (this calls SentenceTransformer.encode internally)
    t0 = time.time()
    rankings = rank(job=job_analysis, resumes=parsed_resumes, weights=weights)
    logger.info(
        "Ranked %d candidates in %.2fs", len(rankings), time.time() - t0
    )

    if weights.skill_weight is not None and not anonymize:
        for candidate in rankings:
            resume = parsed_resumes[int(candidate.candidate_id) - 1]
            candidate.resume_filename = resume.source_filename or resume.filename
            named = re.search(r"(?im)^\s*(?:candidate name|name)\s*:\s*([^\r\n]{2,100})$", resume.raw_text[:1000])
            if named:
                candidate.candidate_name = named.group(1).strip()

    if anonymize:
        for candidate in rankings:
            candidate.resume_snippet = ""
            candidate.text_hash = None

    recommendation = build_recommendation(rankings, job_analysis)

    # Chart datasets
    overall_chart = get_overall_ranking_chart_data(rankings)
    composition_chart = get_score_composition_chart_data(rankings, weights, job_analysis if weights.skill_weight is not None else None)
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
    job_text: str = Field(max_length=24000)
    candidate_name: str = Field(max_length=250)
    candidate_text: Optional[str] = Field(default="", max_length=10000)
    matched_skills: list[str] = Field(default_factory=list, max_length=100)
    missing_skills: list[str] = Field(default_factory=list, max_length=100)


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
    text: str = Field(max_length=24000)


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


@app.get("/api/ready")
async def get_readiness(request: Request):
    state = getattr(request.app.state, "models", "initializing")
    return JSONResponse({"status": state}, 200 if state == "ready" else 503)


@app.get("/api/model-info")
async def get_model_info():
    return {
        "embedding": EMBEDDING_MODEL_NAME,
        "skills": "spaCy en_core_web_sm / technical taxonomy",
        "keyword": f"TF-IDF (1–{TFIDF_MAX_NGRAM} grams)",
        "embedding_revision": EMBEDDING_REVISION,
        "gemini": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    }


@app.post("/api/jobs/document")
async def extract_job_document(file: UploadFile = File(...)):
    stream = await read_document(file)

    try:
        result = await run_ml(read_job_text, stream)
    except ValueError as exc:
        raise HTTPException(422, detail="Could not read the job description document.") from exc
    if not result.strip() or len(result) > 24000:
        raise HTTPException(422, detail="The job document must contain between 1 and 24,000 characters.")
    return {"text": result}


_provider_slots = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="gemini")
_provider_jobs = 0
_provider_window: list[float] = []


@app.post("/api/insights", response_model=InsightsResponse)
async def insights(payload: ValidateResumeRequest):
    global _provider_jobs
    if not payload.job_text.strip():
        raise HTTPException(400, detail="A job description is required.")
    if not is_gemini_available():
        return InsightsResponse(status="unconfigured", message="Gemini insights are unavailable on this server.")

    now = time.monotonic()
    _provider_window[:] = [start for start in _provider_window if now - start < 60]
    if _provider_jobs >= 2 or len(_provider_window) >= 12:
        raise HTTPException(429, detail="AI insights are busy. Try again shortly.", headers={"Retry-After": "30"})
    _provider_jobs += 1
    _provider_window.append(now)

    def finished(future):
        global _provider_jobs
        _provider_jobs -= 1
        if not future.cancelled():
            future.exception()

    future = asyncio.get_running_loop().run_in_executor(
        _provider_slots, generate_insights, payload.job_text, payload.candidate_text or "",
        payload.matched_skills[:60], payload.missing_skills[:60],
    )
    future.add_done_callback(finished)
    try:
        return await asyncio.wait_for(asyncio.shield(future), 24)
    except TimeoutError:
        return InsightsResponse(status="timeout", message="Gemini timed out. Try again shortly.")


@app.post("/api/resumes/validate", response_model=GeminiValidationResult)
async def validate_resume_endpoint(payload: ValidateResumeRequest) -> GeminiValidationResult:
    """Evaluates candidate depth, authenticity, and generates tailored interview questions via Gemini."""
    if not payload.job_text or not payload.job_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job text cannot be empty for AI validation.",
        )
    result = await insights(payload)
    analysis = result.analysis
    return GeminiValidationResult(
        status="success" if analysis else ("unconfigured" if result.status == "unconfigured" else "error"),
        executive_summary=analysis.summary if analysis else (
            "Set GEMINI_API_KEY to enable AI insights." if result.status == "unconfigured" else result.message or ""
        ),
        strengths=analysis.strengths if analysis else [],
        risks_or_concerns=analysis.areas_to_verify if analysis else [],
        interview_questions=analysis.interview_questions if analysis else [],
        model_used=result.model,
        error_message=result.message,
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
async def analyze_job_endpoint(payload: JobAnalyzeRequest) -> JobAnalyzeResponse:
    """Analyzes job description text and extracts required & preferred skills plus minimum experience."""
    if not payload.text or not payload.text.strip():
        return JobAnalyzeResponse()

    analysis = await run_ml(analyze_job, payload.text)
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
    required_skill_weight: float | None = Form(default=None, ge=0, le=1),
    preferred_skill_weight: float = Form(default=0.20, ge=0, le=1),
    semantic_weight: float | None = Form(default=None, ge=0, le=1),
    experience_weight: float = Form(default=0.10, ge=0, le=1),
    keyword_weight: float = Form(default=0.20, ge=0, le=1),
    skill_weight: float | None = Form(default=None, ge=0, le=1),
    job_title: str | None = Form(default=None, max_length=120),
    required_skills: str | None = Form(default=None, max_length=1200),
    preferred_skills: str | None = Form(default=None, max_length=1200),
    min_experience_years: float | None = Form(default=None, ge=0, le=60),
    experience_penalty: float = Form(default=0.60, ge=0, le=1),
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
    if not job_text.strip() or len(job_text) > 24000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job description text is required and must be at most 24,000 characters.",
        )

    # 2. Validate File Count Limit
    if len(files) > MAX_FILES_COUNT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum of {MAX_FILES_COUNT} files allowed per batch.",
        )

    # 3. Validate Weight Sums
    modern = skill_weight is not None or required_skill_weight is None
    if modern and skill_weight is None:
        skill_weight = 0.30
    if semantic_weight is None:
        semantic_weight = 0.40 if modern else 0.20
    required_skill_weight = 0.50 if required_skill_weight is None else required_skill_weight
    skills_total = skill_weight + keyword_weight if modern else required_skill_weight + preferred_skill_weight
    total_weights = skills_total + semantic_weight + experience_weight
    if not math.isclose(total_weights, 1.0, abs_tol=1e-8):
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

        stream = await read_document(uf)
        total_batch_bytes += stream.getbuffer().nbytes
        if total_batch_bytes > MAX_BATCH_SIZE_BYTES:
            raise HTTPException(status_code=413, detail="Total batch exceeds the upload limit.")
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
        skill_weight=skill_weight,
        keyword_weight=keyword_weight,
    )

    logger.info(
        "Starting screening: %d file(s), %.1f KB total",
        len(files_to_parse),
        total_batch_bytes / 1024,
    )

    # 6. Offload ALL CPU-bound screening work to the dedicated thread-pool
    #    so the event loop remains free to serve /api/health during this time.
    overrides = {key: value for key, value in {
        "job_title": job_title, "required_skills": required_skills,
        "preferred_skills": preferred_skills, "min_experience_years": min_experience_years,
    }.items() if value is not None}
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
        ) = await run_ml(
            _run_screening_sync,
            files_to_parse,
            job_text,
            weights,
            anonymize,
            overrides,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        # Raised by _run_screening_sync when ALL resumes fail parsing
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("Unexpected screening error (%s)", type(exc).__name__)
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


class ComparisonRequest(BaseModel):
    candidates: list[CandidateRanking] = Field(min_length=2, max_length=6)


@app.post("/api/compare")
async def compare(payload: ComparisonRequest):
    return {"candidates": [{
        "id": candidate.candidate_id,
        "label": candidate.candidate,
        "overall": candidate.match_score,
        "scores": candidate.component_scores,
        "matched": candidate.matched_skills,
        "missing": candidate.missing_required_skills,
        "experience_years": candidate.experience_years,
    } for candidate in payload.candidates]}


class ExportRequest(BaseModel):
    rankings: list[dict[str, Any]] = Field(max_length=100)
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
        "Keyword Relevance (TF-IDF)",
        "Skill Match",
        "Experience Evidence (Years)",
        "Shortlisted",
        "Extracted Name",
        "Resume Filename",
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
            cs.get("skill_score", ""),
            r.get("experience_years"),
            "Yes" if r.get("shortlisted") else "No",
            r.get("candidate_name"),
            r.get("resume_filename"),
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
