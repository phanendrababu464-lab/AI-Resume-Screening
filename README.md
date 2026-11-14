# AI-Based Resume Screening System

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Architecture](https://img.shields.io/badge/architecture-4--tier%20decoupled-teal.svg)](#architecture-overview)
[![Pydantic v2](https://img.shields.io/badge/contracts-pydantic%20v2-green.svg)](https://docs.pydantic.dev/)
[![Hardware](https://img.shields.io/badge/hardware-CPU%20only%20%28no%20GPU%29-orange.svg)](#prerequisites)
[![Tests Passing](https://img.shields.io/badge/tests-321%20passed-brightgreen.svg)](#testing--verification)

An enterprise-grade, NLP-driven resume screening and ranking platform tailored for technical hiring. The system parses multi-format candidate resumes (`.pdf` and `.docx`), extracts structured sections and technical skills using a curated IT taxonomy and `spaCy` phrase matching, redacts PII for demographic evaluation invariance, and ranks candidates against job descriptions using a 4-component composite scoring engine powered by `sentence-transformers/all-MiniLM-L6-v2`.

Designed with a **strict 4-tier decoupled architecture**, the system can be operated either via a modern interactive **Streamlit web dashboard** or headless via a **typed Python service layer API** suitable for microservices, background job workers, and automated hiring pipelines.

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
  - [A. Interactive Streamlit Dashboard](#a-interactive-streamlit-dashboard)
  - [B. Headless Service Layer API](#b-headless-service-layer-api)
  - [C. Configuration & Weight Tuning](#c-configuration--weight-tuning)
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
│  app/streamlit_app.py (Modern UI)   │  src/app.py (Legacy Wrapper)     │
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

1. **Tier 1: Presentation Layer (`app/` & `src/app.py`)**:
   - `app/streamlit_app.py`: High-performance Streamlit UI containing zero business or domain logic. Renders interactive parameter sliders, job description previews, file uploaders, and ranked candidate cards.
   - `src/app.py`: Backward compatibility entry point delegating execution directly to `app/streamlit_app.py`.
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
├── app/
│   ├── __init__.py
│   └── streamlit_app.py         # Relocated Streamlit UI (strictly decoupled)
├── data/
│   ├── skills/
│   │   └── technical_skills.json # Curated IT / Software Engineering skill taxonomy
│   ├── resumes/                 # 10 synthetic resumes (5 .pdf, 5 .docx)
│   └── job_descriptions/        # 3 synthetic technical job descriptions (.txt)
├── docs/
│   └── teamwork/                # Internal team coordination & audit records
├── src/
│   ├── __init__.py
│   ├── config.py                # Centralized paths, model configurations, default weights
│   ├── schemas.py               # Strongly-typed Pydantic v2 schemas
│   ├── preprocessor.py          # Text normalization, bullet & hyphen preservation
│   ├── parser.py                # PDF & DOCX text extraction, section splitting & fallback
│   ├── job_parser.py            # Cue-phrase required/preferred parsing & experience parser
│   ├── skill_extractor.py       # spaCy PhraseMatcher with edge-case resolution
│   ├── anonymizer.py            # PII redaction & demographic evaluation invariance engine
│   ├── ranker.py                # Semantic similarity, TF-IDF baseline, candidate ranker
│   ├── app.py                   # Backward compatibility wrapper for Streamlit UI
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
│   ├── test_ui_decoupling.py    # UI decoupling & wrapper delegation tests (4 tests)
│   ├── test_synthetic_data.py   # Synthetic data validation tests
│   └── test_e2e_screening.py    # 4-Tier end-to-end evaluation suite (124 tests)
├── .gitignore
├── requirements.txt             # Locked project dependencies
└── README.md                    # Comprehensive system documentation
```

---

## Installation & Setup

### Prerequisites

- **Python**: Version 3.10 or higher (tested on Python 3.10, 3.11, 3.12, 3.13).
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

## Usage Guidelines

### A. Interactive Streamlit Dashboard

To launch the modern interactive web application, execute:

```bash
streamlit run app/streamlit_app.py
```

*(Alternatively, the backward-compatible entry point `streamlit run src/app.py` is fully supported).*

Once started, open your web browser at `http://localhost:8501`.

#### Using the Dashboard:
1. **Configure Weights (Sidebar)**:
   - Fine-tune sliders for **Required Skills Weight** (default: `0.50`), **Preferred Skills Weight** (default: `0.20`), **Semantic Similarity Weight** (default: `0.20`), and **Experience Match Weight** (default: `0.10`).
   - The sidebar provides real-time validation ensuring total weight equals `1.00`.
2. **Input Job Description (Left Column)**:
   - Paste any technical job description. The live analyzer will immediately extract and display detected **Required Skills**, **Preferred Skills**, and **Minimum Experience Required**.
3. **Upload Resumes (Right Column)**:
   - Drag and drop one or more `.pdf` or `.docx` candidate resumes.
4. **Screen and Rank**:
   - Click **"🚀 Screen and Rank Resumes"**.
   - The application automatically anonymizes candidate PII, extracts sections and skills, computes embedding similarities, and renders:
     - An **interactive leaderboard table** sorted by composite match score.
     - **Detailed candidate breakdown cards** with component metrics (`Required Skills %`, `Preferred Skills %`, `Semantic Match %`, `Experience Match %`, `TF-IDF Baseline %`), as well as visual badges for **Matched Required Skills**, **Matched Preferred Skills**, and **Missing Required Skills**.

---

### B. Headless Service Layer API

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

### C. Configuration & Weight Tuning

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

The system maintains a comprehensive, hermetic automated test suite with **350 passing tests** executed via `pytest`. All tests execute locally on CPU with zero network calls and zero mock-bypassing.

### Running the Test Suite

Execute the entire test suite with verbose output:

```bash
pytest tests/ -v
```

Execute a specific test module:

```bash
# Test UI-free service layer and Pydantic schemas
pytest tests/test_screening_service.py -v

# Test skill extraction edge cases (C#, C++, .NET, Node.js, R, aliases, plurals)
pytest tests/test_edge_cases.py -v

# Test candidate anonymization and evaluation invariance
pytest tests/test_anonymizer.py -v

# Test resume section splitting and fallback classifier
pytest tests/test_section_splitting.py -v

# Test cue-phrase job parsing
pytest tests/test_job_parser.py -v

# Test UI decoupling and backward compatibility wrappers
pytest tests/test_ui_decoupling.py -v

# Test synthetic data assets and repository hygiene
pytest tests/test_synthetic_data.py -v

# Test 4-tier requirement-driven end-to-end evaluation suite
pytest tests/test_e2e_screening.py -v
```

### Test Suite Breakdown

| Module | Test Count | Focus & Acceptance Coverage |
| :--- | :---: | :--- |
| `tests/test_parser.py` | 7 | Baseline PDF/DOCX ingestion and text extraction |
| `tests/test_preprocessor.py` | 5 | Text cleaning, bullet stripping, and hyphen protection (`Scikit-Learn`) |
| `tests/test_ranker.py` | 4 | Baseline ranking and legacy 7-column DataFrame compatibility |
| `tests/test_skill_extractor.py` | 10 | Baseline skill taxonomy loading and phrase matching |
| `tests/test_section_splitting.py` | 12 | Heading regex parsing and heuristic fallback for unstructured resumes |
| `tests/test_job_parser.py` | 12 | Cue-phrase required vs preferred splitting and min experience extraction |
| `tests/test_edge_cases.py` | 21 | C#, C++, .NET, Node.js, standalone R guard, Java vs JS, aliases, plurals |
| `tests/test_anonymizer.py` | 43 | PII redaction (names, emails, phones, pronouns) & evaluation invariance |
| `tests/test_screening_service.py` | 16 | Headless service layer functions, Pydantic contracts, stream ingestion |
| `tests/test_ui_decoupling.py` | 4 | UI decoupling verification (zero business logic in Streamlit UI) |
| `tests/test_synthetic_data.py` | 92 | Validation of 10 synthetic resumes and 3 synthetic job descriptions |
| `tests/test_e2e_screening.py` | 124 | 4-Tier end-to-end requirement, boundary, and stress evaluation suite |
| **Total** | **350** | **100% Passing on CPU without mocks or skips** |

### Quality & Integrity Guarantees

- **Demographic Evaluation Invariance**: Verified by automated test `test_evaluation_invariance_multi_demographic_variants` — candidate scores remain identical to within `1e-6` floating-point precision when names and demographic attributes are altered across ethnic and gender variants.
- **Baseline Backward Compatibility**: All 26 original baseline tests continue to pass without modification or regression.
- **Zero Mock Policy**: Tests evaluate real NLP parsing, phrase matching, and embedding vector operations without mocking core logic.
- **Strict UI Decoupling**: Verified by automated AST inspection in `test_ui_has_zero_domain_business_logic_imports` — `app/streamlit_app.py` has zero direct imports from domain engines (`parser`, `ranker`, `skill_extractor`, `anonymizer`), importing exclusively from `src.services.screening_service` and `src.schemas`.

---

## Repository Cleanliness

In accordance with strict production repository standards:
- **Zero Stray Files**: No temporary scripts, notes, scratch files, or planning artifacts are permitted in the repository root.
- **Dedicated Docs Directory**: Any internal planning, milestone tracking, or auditing records are isolated under `docs/teamwork/`.
