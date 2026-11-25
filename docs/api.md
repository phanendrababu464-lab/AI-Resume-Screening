# HireLens API

The FastAPI service serves its request schemas at `/openapi.json` and interactive documentation at `/docs`.

| Method and path | Contract |
| --- | --- |
| `GET /` | Service identifier and discovery links |
| `GET /api/health` | Lightweight liveness and configured feature flags |
| `GET /api/ready` | HTTP 200 when local models are ready, HTTP 503 while initializing or after startup failure |
| `GET /api/config` | Upload limits and Gemini configuration flag |
| `GET /api/model-info` | Model names, revision and n-gram settings |
| `GET /api/samples` | Bundled synthetic fixtures |
| `POST /api/jobs/analyze` | JSON `text` to extracted title, skills and minimum experience |
| `POST /api/jobs/document` | Multipart `file` to job-description `text` |
| `POST /api/screen` | Multipart job criteria and resume files to ranked results with evidence and contributions |
| `POST /api/compare` | JSON with two to six supplied ranking records to comparable metrics |
| `POST /api/insights` | JSON job text, candidate reference, optional excerpt and skill evidence to validated Gemini analysis or an availability status |
| `POST /api/export` | JSON rankings and optional job title to CSV |

For screening, send `job_text`, repeated `files`, and optional `job_title`, comma-separated `required_skills` and `preferred_skills`, `min_experience_years`, and `anonymize`. Fractional `semantic_weight`, `keyword_weight`, `skill_weight`, and `experience_weight` must total 1.0. `use_sample_resumes=true` selects the synthetic fixtures. File-level errors are returned with successful results if at least one file is readable.

For insights, send `job_text`, `candidate_name` as an opaque reference, optional `candidate_text`, `matched_skills`, and `missing_skills`. The response returns `success`, `unconfigured`, `model_unavailable`, `quota`, `timeout` or `error`. Quoted evidence is checked against the submitted excerpt.

Invalid input receives 400 or 422, oversized requests receive 413, provider admission limits receive 429, and temporarily unavailable inference receives 503 with `Retry-After`. A local processing deadline returns 504. Retry screening only after a human initiates a new request. The service keeps no saved candidate IDs or sessions.
