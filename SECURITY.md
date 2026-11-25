# Security and privacy

HireLens processes resumes supplied by the active user. Results, shortlists, and session activity remain in tab memory. Reloading or leaving the workspace clears them. The API has no candidate listing or retrieval endpoint. Its public document retrieval route serves only bundled synthetic samples.

The API bounds request size and concurrent uploads, checks file MIME and signature, limits expanded DOCX content, and parses documents without running uploaded content. FastAPI closes temporary multipart files at the end of the request. The backend keeps no database of uploaded resumes and avoids logging candidate filenames, contents, or provider response bodies. CSV exports neutralize values that could begin spreadsheet formulas and omit resume excerpts.

Gemini is optional. Requesting insights sends job information and the available redacted candidate excerpt or extracted skills to Google's service. Avoid using personal details in the job description or criteria. The request uses a separate system instruction, schema validation, verified excerpt quotes, bounded retries, and per-process request limits. AI interpretations may still be inaccurate and require recruiter review. Protected characteristics must not form part of role criteria or hiring decisions. Redaction is heuristic.

Public deployments are stateless. Introduce authentication, authorization and session isolation before adding candidate storage or sharing. Confirm hosting logs and the organization's Google data-handling settings before processing real applicant data.

Report suspected vulnerabilities privately to the repository owner. Include affected versions and observed behavior without attaching real candidate documents, API keys, or personal data.
