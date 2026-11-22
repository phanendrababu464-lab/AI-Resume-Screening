# HireLens AI

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Architecture](https://img.shields.io/badge/architecture-4--tier%20decoupled-teal.svg)](#architecture-overview)
[![Pydantic v2](https://img.shields.io/badge/contracts-pydantic%20v2-green.svg)](https://docs.pydantic.dev/)
[![Hardware](https://img.shields.io/badge/hardware-CPU%20only%20%28no%20GPU%29-orange.svg)](#prerequisites)

An enterprise-grade, NLP-driven resume screening and ranking platform tailored for technical hiring. The system parses multi-format candidate resumes (`.pdf` and `.docx`), extracts structured sections and technical skills using a curated IT taxonomy and `spaCy` phrase matching, redacts PII for demographic evaluation invariance, and ranks candidates against job descriptions using a 4-component composite scoring engine powered by `sentence-transformers/all-MiniLM-L6-v2`.

Designed with a **strict 4-tier decoupled architecture**, the system can be operated either via a modern interactive **React + Vite web interface (backed by FastAPI)** or headless via a **typed Python service layer API** suitable for microservices, background job workers, and automated hiring pipelines.

---

## Table of Contents

- [Key Capabilities](#key-capabilities)
- [Architecture Overview](#architecture-overview)
  - [The 4-Tier Model](#the-4-tier-model)
  - [Data Flow Diagram](#data-flow-diagram)
  - [Pydantic v2 Contract Reference](#pydantic-v2-contract-reference)
- [Repository Structure](#repository-structure)
- [Installation & Setup](#installation--setup)
  - [Prerequisites](#prerequisites)
  - [1. Clone and Navigate](#1-clone-and-navigate)
  - [2. Virtual Environment Setup](#2-virtual-environment-setup)
  - [3. Install Dependencies](#3-install-dependencies)
- [Usage Guidelines](#usage-guidelines)
  - [A. Full-Stack Web Application (React + FastAPI)](#a-full-stack-web-application-react--fastapi)
  - [B. Running via Launcher Scripts](#b-running-via-launcher-scripts)
  - [C. Headless Service Layer API](#c-headless-service-layer-api)
  - [D. Configuration & Weight Tuning](#d-configuration--weight-tuning)
- [Synthetic Data Assets](#synthetic-data-assets)
- [Testing & Verification](#testing--verification)
  - [Running the Test Suite](#running-the-test-suite)
  - [Test Suite Breakdown](#test-suite-breakdown)
  - [Quality & Integrity Guarantees](#quality--integrity-guarantees)
- [Repository Cleanliness](#repository-cleanliness)

---

## Key Capabilities

- **Multi-Format Ingestion**: Extracts text, tables, and document blocks from `.pdf` (`pdfplumber`) and `.docx` (`python-docx`) files or in-memory binary streams (`BytesIO`).
- **Intelligent Section Splitting**: Parses resumes into structured sections (`skills`, `experience`, `education`, `projects`, `other`) using robust regex boundary matching, backed by a fuzzy heuristic fallback classifier for resumes with missing or non-standard headers.
- **Cue-Phrase Job Description Parsing**: Dissects job descriptions into **Required** (must-have) versus **Preferred** (nice-to-have) technical competencies using in-line cue phrases and section headers, and extracts minimum required experience years.
- **Precision Technical Skill Extraction**: Powered by `spaCy` `PhraseMatcher` and a curated IT taxonomy (`data/skills/technical_skills.json`). Handles complex tokenization edge cases:
  - Sub-span disambiguation (`C#` / `C++` vs. `C`) using `filter_spans`.
  - Punctuation-sensitive tokens (`.NET`, `Node.js`).
  - Single-letter guard for `R` (matches standalone language, rejects false positives like `R&D` or `Toys R Us`).
  - Disambiguates `Java` from `JavaScript`.
  - Canonical alias normalization (`JS` &rarr; `JavaScript`, `K8s` &rarr; `Kubernetes`, `NodeJS` &rarr; `Node.js`).
  - Plural/singular normalization (`Dockers` &rarr; `Docker`, `Microservice` &rarr; `Microservices`).
- **Demographic Evaluation Invariance & Anonymization**: Redacts names (with honorifics/suffixes), emails, phone numbers, and gendered pronouns (`[NAME]`, `[EMAIL]`, `[PHONE]`, `[PRONOUN]`) while safeguarding technical skill tokens (`Ruby`, `Rust`, `Swift`, `Julia`, `Go`, `Bash`). Ensures candidate scores remain mathematically invariant regardless of demographic identity.
- **4-Component Weighted Scoring Engine**:
  - **Required Skill Match (50% default)**: Strict coverage percentage against must-have technical competencies.
  - **Preferred Skill Match (20% default)**: Coverage bonus for nice-to-have competencies.
  - **Semantic Contextual Match (20% default)**: Dense embedding cosine similarity computed via `sentence-transformers/all-MiniLM-L6-v2`.
  - **Experience Match (10% default)**: Candidate years of experience evaluated against job requirements.
  - **TF-IDF Cosine Baseline**: Independent bag-of-words baseline computed alongside embeddings for transparency and benchmarking.
- **Strict Pydantic v2 Contracts**: Strongly-typed schemas for job analyses, parsed resumes, candidate rankings, scoring breakdowns, and configuration models.
- **Laptop-Friendly & CPU Optimized**: Runs with sub-second inference times per resume entirely on CPU, with singleton-cached NLP models and zero GPU requirements.

---

## Architecture Overview

The system is organized into a **4-tier decoupled architecture**, strictly isolating presentation from application orchestration, core domain logic, and persistent assets.

```
┌────────────────────────────────────────────────────────────────────────┐
│                   Tier 1: Presentation Layer                           │
│  frontend/ (React + Vite Web UI)    │  src/api.py (FastAPI REST API)   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (Calls Service Layer APIs only)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   Tier 2: Service & Contract Layer                     │
│  src/services/screening_service.py  │  src/schemas.py (Pydantic v2)    │
│  - analyze_job(text)                │  - JobAnalysis                   │
│  - parse_resumes(files)             │  - ParsedResume, ResumeSections  │
│  - rank(job, resumes, weights)      │  - WeightConfig, CandidateRanking│
│  - screen(job, files, weights)      │  - ComponentScores               │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (Orchestrates Domain Engines)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   Tier 3: Core Domain Engines                          │
│  src/parser.py           src/job_parser.py       src/skill_extractor.py│
│  (PDF/DOCX Extraction    (Cue-Phrase Required    (spaCy PhraseMatcher  │
│   & Section Splitting)    vs Preferred Split)     & Edge Cases)        │
│                                                                        │
│  src/anonymizer.py       src/ranker.py           src/preprocessor.py   │
│  (PII Redaction & Score  (Embedding Cosine Sim   (Text Normalization   │
│   Evaluation Invariance)  & TF-IDF Baseline)      & Hyphen Safeguards) │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (Resolves Configurations & Assets)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   Tier 4: Data & Infrastructure Assets                 │
│  src/config.py                 │  data/skills/technical_skills.json    │
│  data/resumes/ (*.pdf, *.docx) │  data/job_descriptions/ (*.txt)       │
│  HuggingFace Local Cache (~/.cache/huggingface/all-MiniLM-L6-v2)       │
└────────────────────────────────────────────────────────────────────────┘
```

### The 4-Tier Model

1. **Tier 1: Presentation Layer (`frontend/` & `src/api.py`)**:
2. **Tier 2: Service & Contract Layer (`src/services/` & `src/schemas.py`)**:
   - `src/services/screening_service.py`: Headless orchestration boundary. Manages job parsing, file ingestion, anonymization, and scoring pipelines. Employs singleton pattern caching for CPU inference models.
   - `src/schemas.py`: Explicit, validated Pydantic v2 domain schemas defining inputs, intermediate artifacts, and output rankings.
3. **Tier 3: Core Domain Engines (`src/`)**:
   - Specialized stateless engines: text extraction, section splitting with fallback classification, cue-phrase parsing, edge-case skill extraction, demographic anonymization, and composite ranking calculation.
4. **Tier 4: Data & Infrastructure Assets (`data/` & `src/config.py`)**:
   - `src/config.py`: Dynamic base directory path resolution and default weight constants.
   - `data/skills/technical_skills.json`: Curated software engineering and IT skill taxonomy.
   - `data/resumes/` & `data/job_descriptions/`: Synthetic evaluation fixtures.

### Data Flow Diagram

```
[Raw Job Description Text]
          │
          ▼
   analyze_job() ────────► [JobAnalysis Schema]
                                (Required, Preferred, Min Experience)
                                      │
[PDF / DOCX Resumes]                  │
          │                           │
          ▼                           │
   parse_resumes()                    │
   ├── extract_text()                 │
   ├── split_resume_sections()        │
   ├── anonymize_text() [PII Redacted]│
   └── extract_skills()               │
          │                           │
          ▼                           │
  [ParsedResume Schemas]              │
          │                           │
          └─────────────┬─────────────┘
                        │
                        ▼
                 rank(job, resumes, weights)
                 ├── SentenceTransformer Embedding Cosine Similarity
                 ├── Required & Preferred Skill Coverage Calculation
                 ├── Experience Match vs Min Years Required
                 └── scikit-learn TF-IDF Cosine Baseline
                        │
                        ▼
             [CandidateRanking Schemas]
             (Sorted Descending by match_score)
```

### Pydantic v2 Contract Reference

All data exchanged between the Presentation, Service, and Domain tiers conforms strictly to Pydantic v2 models:

```python
class JobAnalysis(BaseModel):
    raw_text: str
    cleaned_text: str = ""
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    all_skills: list[str] = Field(default_factory=list)
    min_experience_years: Optional[float] = None

class ResumeSections(BaseModel):
    skills: str = ""
    experience: str = ""
    education: str = ""
    projects: str = ""
    other: str = ""

class ParsedResume(BaseModel):
    filename: str
    raw_text: str
    cleaned_text: str = ""
    sections: ResumeSections = Field(default_factory=ResumeSections)
    skills: list[str] = Field(default_factory=list)
    experience_years: Optional[float] = None
    anonymized_text: Optional[str] = None

class WeightConfig(BaseModel):
    required_skill_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    preferred_skill_weight: float = Field(default=0.2, ge=0.0, le=1.0)
    semantic_weight: float = Field(default=0.2, ge=0.0, le=1.0)
    experience_weight: float = Field(default=0.1, ge=0.0, le=1.0)

class ComponentScores(BaseModel):
    required_skill_score: float = 0.0
    preferred_skill_score: float = 0.0
    semantic_score: float = 0.0
    experience_score: float = 0.0
    tfidf_baseline_score: Optional[float] = None

class CandidateRanking(BaseModel):
    rank: int
    candidate: str
    match_score: float
    component_scores: ComponentScores
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    matched_required_skills: list[str] = Field(default_factory=list)
    matched_preferred_skills: list[str] = Field(default_factory=list)
    missing_required_skills: list[str] = Field(default_factory=list)

class ScreeningResult(BaseModel):
    job: JobAnalysis
    rankings: list[CandidateRanking] = Field(default_factory=list)
    total_resumes: int = 0
```

---

## Repository Structure

```text
resume-screening-system/
├── data/
│   ├── skills/
│   │   ├── technical_skills.json # Curated IT / Software Engineering skill taxonomy
│   │   └── related_skills.json   # Semantic partial-credit similarity graph
│   ├── resumes/                 # 10 synthetic resumes (5 .pdf, 5 .docx)
│   └── job_descriptions/        # 3 synthetic technical job descriptions (.txt)
├── docs/
│   └── teamwork/                # Internal team coordination & audit records
├── frontend/                    # Modern React + Vite + TypeScript web interface
│   ├── src/
│   │   ├── components/          # TopBar, SetupSection, ScoringSettings, Results/
│   │   ├── context/             # ThemeContext (dark/light theme persistence)
│   │   ├── services/            # Typed API client with Vite proxy
│   │   ├── types/               # TypeScript interfaces matching backend models
│   │   └── utils/               # Normalizing, formatting & validation helpers
│   ├── package.json
│   ├── tailwind.config.js       # Design tokens (indigo accent, neutral surfaces)
│   └── vite.config.ts           # Proxy to FastAPI on :8000
├── src/
│   ├── __init__.py
│   ├── api.py                   # FastAPI REST backend (/api/screen, /api/jobs/analyze, etc.)
│   ├── config.py                # Centralized paths, model configurations, default weights
│   ├── schemas.py               # Strongly-typed Pydantic v2 schemas
│   ├── preprocessor.py          # Text normalization, bullet & hyphen preservation
│   ├── parser.py                # PDF & DOCX text extraction, section splitting & fallback
│   ├── job_parser.py            # Cue-phrase required/preferred parsing & experience parser
│   ├── skill_extractor.py       # spaCy PhraseMatcher with edge-case resolution
│   ├── anonymizer.py            # PII redaction & demographic evaluation invariance engine
│   ├── ranker.py                # Semantic similarity, TF-IDF baseline, candidate ranker
│   └── services/
│       ├── __init__.py
│       └── screening_service.py # UI-free headless service layer
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Pytest fixtures and mock candidate builders
│   ├── test_parser.py           # Baseline document parser tests (7 tests)
│   ├── test_preprocessor.py     # Baseline preprocessor & token cleaning tests (5 tests)
│   ├── test_ranker.py           # Baseline ranker & DataFrame shape tests (4 tests)
│   ├── test_skill_extractor.py  # Baseline skill extractor tests (10 tests)
│   ├── test_section_splitting.py# Resume section splitting & fallback tests (12 tests)
│   ├── test_job_parser.py       # Cue-phrase required vs. preferred tests (12 tests)
│   ├── test_edge_cases.py       # Skill extraction edge case tests (21 tests)
│   ├── test_anonymizer.py       # PII redaction & score invariance tests (43 tests)
│   ├── test_screening_service.py# Headless service layer & schema tests (16 tests)
│   ├── test_ui_decoupling.py    # Architecture decoupling & retirement audit tests (6 tests)
│   ├── test_experience_gate.py  # Below-minimum experience gate tests (5 tests)
│   ├── test_related_skills.py   # Semantic partial credit tests (5 tests)
│   ├── test_synthetic_data.py   # Synthetic data validation tests
│   └── test_e2e_screening.py    # 4-Tier end-to-end evaluation suite (124 tests)
├── .gitignore
├── run_web.sh                   # One-click launcher for FastAPI (:8000) + React (:5173)
├── requirements.txt             # Locked project dependencies
└── README.md                    # Comprehensive system documentation
```

---

## Installation & Setup

### Prerequisites

- **Python**: Use Python 3.12.8 to match Render.
- **Architecture**: Standard x86_64 or Apple Silicon ARM64 terminal.
- **Hardware**: Standard laptop / workstation CPU (no CUDA/GPU required; memory footprint < 1.5 GB).

### 1. Clone and Navigate

```bash
git clone <repository-url>
cd resume-screening-system
```

### 2. Virtual Environment Setup

Create and activate a clean virtual environment:

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

# Windows (Command Prompt)
python -m venv .venv
.venv\Scripts\activate.bat

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

Install all locked dependencies via `pip`:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> **Note on NLP Models:**
> - **spaCy**: The skill extraction engine uses `spacy.blank("en")` with token-based phrase matching. There is **no need** to download external language models like `en_core_web_sm`.
> - **SentenceTransformers**: The `all-MiniLM-L6-v2` embedding model (~90 MB) is downloaded automatically upon first execution and cached locally in `~/.cache/huggingface/`. Subsequent runs operate completely offline.

---

## Deployment and environment

Render runs the FastAPI service using Python 3.12.8. Its start command binds Uvicorn to the port assigned by Render. Use `/api/health` to check the service.

Set `VITE_API_BASE_URL=https://ai-resume-screening-3-1r1d.onrender.com` in the Vercel production environment and rebuild the Vite frontend. Set Render's `CORS_ORIGINS` to `https://ai-resume-screening-three-kohl.vercel.app`.

For local development, create `.env` in the repository root with these backend settings.

```dotenv
PORT=8000
HOST=0.0.0.0
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
MAX_RESUMES_PER_BATCH=100
MAX_FILE_SIZE_BYTES=5242880
```

Create `frontend/.env.development` with `VITE_API_BASE_URL=http://127.0.0.1:8000`. To enable Gemini, set `GEMINI_API_KEY` in the local backend environment or the Render environment. Keep the key server-side.

## Usage Guidelines

### A. Full-Stack Web Application (React + FastAPI)

The project includes an enterprise-grade web application built with **React 18 + Vite + TypeScript + Tailwind CSS**, communicating with a **FastAPI** backend via typed JSON endpoints.

#### 1. One-Command Startup
To start both the FastAPI backend (`http://127.0.0.1:8000`) and the React frontend (`http://localhost:5173`) with automated cleanup:

```bash
./run_web.sh
```

#### 2. Manual Dev Server Startup
If running services individually:

```bash
# Terminal 1: Backend API (port 8000)
source .venv/bin/activate
uvicorn src.api:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: Frontend (port 5173 with Vite proxy)
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in any browser.

#### Key Frontend Capabilities:
- **Design System & Themes**: Clean, professional recruiting tool aesthetic built on an 8px grid with neutral surfaces, a single Indigo accent (`#6366f1`), Inter typography, rounded cards, and full **Dark / Light mode** toggle (stored in `localStorage` and respecting system preferences). All chart labels and text maintain high contrast across themes.
- **Top Bar**: Live API health monitoring dot (green/red from `/api/health`), theme toggle, and an interactive **"How Scoring Works"** modal detailing the 4-component formula, experience penalty gate, and related-skill partial credit.
- **Side-by-Side Setup**:
  - *Target Job Description*: Monospace textarea, "Use sample job" dropdown (`/api/samples`), and a debounced live preview (`/api/jobs/analyze`) displaying extracted required and preferred skill chips and minimum experience gate.
  - *Candidate Resumes*: Drag-and-drop zone and file picker with client-side validation (PDF/DOCX, 5 MB limit, max 100 resumes), removable file chips with size badges, and a "Use sample resumes" button.
- **Scoring Parameters (Collapsible Panel)**: 4 weight sliders with real-time sum indicator, **"Normalize to 100%"** button, configurable below-minimum-experience penalty slider, Anonymize toggle, and "Reset to Defaults". The **"Screen & Rank Resumes"** button is disabled with a visible explanation until inputs are valid and weights equal exactly 100%.
- **Evaluation & Candidate Ranking Results**:
  1. **Best Match Hero Card**: Large SVG match score ring, runner-up comparison with margin points, deterministic recommendation text, and three structured cards (Key Strengths, Gaps & Unmatched Skills, Advisory Warnings).
  2. **Candidate Leaderboard**: Descending horizontal ranked bars, top candidate highlighted in emerald, below-minimum-experience warning badges, and clickable rows that open the Candidate Detail Drawer.
  3. **Score Composition Breakdown**: Recharts stacked horizontal bars showing exact percentage contributions of Required, Preferred, Semantic, and Experience components, plus footnotes where experience penalties were applied.
  4. **Skill Match Matrix**: Grouped columns (**REQUIRED SKILLS** first, then **PREFERRED SKILLS** with a vertical divider), sticky candidate column, uniform cells with colors and symbols (`✓` exact, `≈` related with matched skill tooltip, `✗` missing), and a summary column (`e.g. 7/7 required`).
  5. **Candidate Detail Drawer**: Slide-over drawer with 5 component score progress bars and full skill taxonomy breakdown chips.
  6. **Export Action**: One-click CSV export button (`/api/export`).

---

### B. Running via Launcher Scripts

The unified runner script launches both the FastAPI backend and the React + Vite web application together:

```bash
./run_web.sh
```


Once started:
- **Web Frontend**: `http://localhost:5173`
- **FastAPI API**: `http://127.0.0.1:8000`
- **Interactive Swagger Docs**: `http://127.0.0.1:8000/docs`


---

### C. Headless Service Layer API

For automated pipelines, microservice endpoints, or batch evaluations, use the headless service layer in `src.services.screening_service`. It requires no UI and operates purely via Python functions and Pydantic schemas.

#### Complete Programmatic Example:

```python
from pathlib import Path
from src.services.screening_service import analyze_job, parse_resumes, rank, screen
from src.schemas import WeightConfig

# 1. Parse and analyze a Job Description
job_text = """
Senior Python Backend Engineer
Requirements:
- Must have 4+ years of hands-on experience with Python and FastAPI
- Production experience with PostgreSQL and Redis
Preferred:
- Experience with Docker, Kubernetes, and AWS
"""

job_analysis = analyze_job(job_text)
print("Required Skills detected:", job_analysis.required_skills)
# Output: ['FastAPI', 'PostgreSQL', 'Python', 'Redis']
print("Preferred Skills detected:", job_analysis.preferred_skills)
# Output: ['AWS', 'Docker', 'Kubernetes']
print("Minimum Experience Required:", job_analysis.min_experience_years)
# Output: 4.0

# 2. Ingest candidate resumes from file paths (or in-memory BytesIO streams)
resume_paths = [
    Path("data/resumes/resume_01.pdf"),
    Path("data/resumes/resume_06.docx"),
]
# Alternatively, pass raw text dicts:
# parsed_candidates = [
#     {"name": "Alice Smith", "text": "5 years experience in Python, FastAPI, and PostgreSQL."},
#     {"name": "Bob Jones", "text": "2 years in React, JavaScript, and HTML."}
# ]
parsed_candidates = parse_resumes(resume_paths)

# 3. Configure custom scoring weights (Optional, defaults to 0.5/0.2/0.2/0.1)
weights = WeightConfig(
    required_skill_weight=0.50,
    preferred_skill_weight=0.20,
    semantic_weight=0.20,
    experience_weight=0.10,
)

# 4. Compute candidate rankings
rankings = rank(job=job_analysis, resumes=parsed_candidates, weights=weights)

# 5. Inspect ranked results
for candidate in rankings:
    print(f"Rank {candidate.rank}: {candidate.candidate}")
    print(f"  Match Score: {candidate.match_score:.2f}%")
    print(f"  Required Skills Matched: {candidate.matched_required_skills}")
    print(f"  Required Skills Missing: {candidate.missing_required_skills}")
    print(f"  Component Scores: {candidate.component_scores.model_dump()}")

# 6. Or use the all-in-one convenience function:
# result = screen(job=job_text, files=resume_paths, weights=weights)
# print(f"Screened {result.total_resumes} resumes. Top candidate: {result.rankings[0].candidate}")
```

#### Demographic Anonymization Example:

```python
from src.anonymizer import anonymize_text

raw_resume = """
Johnathan Doe
Email: john.doe@engineer-corp.com | Phone: (555) 234-5678
He is a Lead Software Engineer with 6 years experience in Python, Rust, and AWS.
"""

anonymized_resume = anonymize_text(raw_resume, candidate_name="Johnathan Doe")
print(anonymized_resume)
# Output preserves technical skills while deterministically redacting PII:
# [NAME]
# Email: [EMAIL] | Phone: [PHONE]
# [PRONOUN] is a Lead Software Engineer with 6 years experience in Python, Rust, and AWS.
```

---

### D. Configuration & Weight Tuning

The system provides two levels of configuration:

1. **System Defaults (`src/config.py`)**:
   Global defaults and paths are centrally declared in `src/config.py`:
   - `DEFAULT_REQUIRED_SKILL_WEIGHT = 0.5`
   - `DEFAULT_PREFERRED_SKILL_WEIGHT = 0.2`
   - `DEFAULT_SEMANTIC_SIMILARITY_WEIGHT = 0.2`
   - `DEFAULT_EXPERIENCE_WEIGHT = 0.1`
   - `EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"`
   - `DEFAULT_DEVICE = "cpu"`
2. **Runtime Overrides (`WeightConfig`)**:
   Any programmatic call to `rank()` or `screen()` can pass a custom `WeightConfig` instance or dictionary to override weights on a per-job basis without altering code files.
3. **Skill Taxonomy Customization (`data/skills/technical_skills.json`)**:
   Add new domain-specific technologies, frameworks, or tools to the `"skills"` array in `data/skills/technical_skills.json`. The `TechnicalSkillExtractor` automatically loads and indexes the updated taxonomy upon startup.

---

## Synthetic Data Assets

To support out-of-the-box evaluation and hermetic automated testing, the repository includes representative synthetic test fixtures in `data/`:

- **`data/resumes/`** (10 Synthetic Candidate Resumes):
  - 5 `.pdf` resumes (`resume_01.pdf` through `resume_05.pdf`) and 5 `.docx` resumes (`resume_06.docx` through `resume_10.docx`).
  - Spans diverse technical roles: Senior Backend Python Engineer, Frontend React/TypeScript Developer, DevOps/Cloud AWS Architect, Machine Learning / Data Scientist, Fullstack Mobile Engineer.
  - Formatted with realistic resume sections (`Skills`, `Experience`, `Education`, `Projects`) and explicit years of experience.
- **`data/job_descriptions/`** (3 Synthetic Technical Job Descriptions):
  - `job_01_backend_python.txt`: Senior Backend Engineer (Required: Python, FastAPI, PostgreSQL; Preferred: Docker, Kubernetes, AWS; 5+ years).
  - `job_02_frontend_react.txt`: Lead Frontend Developer (Required: React, TypeScript, JavaScript, HTML5, CSS3, Next.js, Git; Preferred: Cypress, Docker, GraphQL, Sass, WebSockets; 4+ years).
  - `job_03_devops_cloud.txt`: Senior DevOps & Cloud Infrastructure Engineer (Required: AWS, Bash, CI/CD, Docker, Kubernetes, Linux, Terraform; Preferred: Ansible, GitHub Actions, Grafana, Prometheus, Python; 5+ years).

---

## Testing & Verification

Run the backend suite from the repository root and the frontend checks from the frontend directory.

```bash
python -m pytest -q
(cd frontend && npm test && npm run build)
```

The integration tests exercise PDF and DOCX screening, anonymized results, recommendations and CSV export. Gemini success and failure paths use simulated provider responses.

### Quality & Integrity Guarantees

- **Demographic Evaluation Invariance**: Verified by automated test `test_evaluation_invariance_multi_demographic_variants` — candidate scores remain identical to within `1e-6` floating-point precision when names and demographic attributes are altered across ethnic and gender variants.
- **Baseline Backward Compatibility**: All 26 original baseline tests continue to pass without modification or regression.
- **Zero Mock Policy**: Tests evaluate real NLP parsing, phrase matching, and embedding vector operations without mocking core logic.

---

## Repository Cleanliness

In accordance with strict production repository standards:
- **Zero Stray Files**: No temporary scripts, notes, scratch files, or planning artifacts are permitted in the repository root.
- **Dedicated Docs Directory**: Any internal planning, milestone tracking, or auditing records are isolated under `docs/teamwork/`.
