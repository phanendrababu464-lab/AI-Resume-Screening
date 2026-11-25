# HireLens AI architecture

## Repository audit

The local checkout matched GitHub `main` at `707af50` when work started. Commit `042e103` deleted the old working tree, and `bd546bd` restored the application using the existing remote. Historical commit `a207680` introduced the model worker and Vercel/Render split. The current baseline already contained stronger parsing, alias matching, anonymization, synthetic fixtures and regression coverage, so the rebuild retained those components.

The audit found a single-page dashboard, an API that blocked startup while warming the model, unrestricted Vercel subdomain CORS, open-ended inference queueing, and a loose Python deployment specification. The tracked history check for local environment files and Google-style API keys produced no matches.

## Runtime

- The Vite frontend serves a landing page and a routed React workspace. Candidate data and the active shortlist live in memory in the current tab. Completed session summaries power dashboard activity during that tab's lifetime. Only theme and layout preferences are persisted in browser storage.
- FastAPI owns multipart validation, scoring contracts, and export. A single-worker executor imports and warms the model libraries and handles PDF or DOCX extraction, job analysis and CPU inference. Model encoding uses one document per batch on Render and four elsewhere to cap peak memory. Render uses half-precision model weights by default and converts embeddings to Float32 for cosine scoring. Set `EMBEDDING_DTYPE=float32` to override this on a larger instance. Request admission caps concurrent uploads and keeps at most one running and one queued ML task. A timed-out HTTP request keeps its worker slot until the computation finishes.
- The service loads the pinned MiniLM revision and the spaCy `en_core_web_sm` tokenizer for taxonomy phrase matching. Role overrides accept canonical or aliased technical skills from the taxonomy. Known protected-attribute fields and explicit age statements are removed from modern relevance inputs.
- Gemini is a separate optional request through the Interactions API, with interaction storage disabled. Render uses the documented REST transport to avoid retaining the SDK in its small instance. Other environments use the Google GenAI SDK. On Render, temporary provider failures get one retry. When the primary is Gemini 3.5 Flash-Lite, the retry defaults to Gemini 3.1 Flash-Lite, configurable via GEMINI_FALLBACK_MODEL. Provider work has two concurrent slots, a per-process quota, and bounded timeouts and retries. Gemini output never feeds the ranking formula.

## Score methodology

The overall match is the weighted sum of semantic similarity, TF-IDF keyword relevance, skill match and experience relevance. Default weights are **40%, 20%, 30%, and 10%** respectively. Components use a 0–1 scale, displayed as percentages. The score contribution in points is 100 times component score times configured weight, rounded to reconcile with the visible overall score.

- Semantic relevance uses cosine similarity on batched MiniLM embeddings from the job description and redacted candidate text. Negative similarity is clipped at zero.
- Keyword relevance uses TF-IDF cosine similarity across the submitted batch. The configured n-gram range defaults to unigrams and bigrams. Relative scores may change with batch composition.
- Skill match gives required and preferred skills 80% and 20% of the skill component when both exist. One available skill group counts for the entire component. Alias matches count as exact and the curated related-skill map can award partial credit.
- Experience relevance credits explicit years-of-experience statements relative to the requested minimum. Unstated experience remains unknown. Unknown or unspecified criteria contribute zero points without a multiplier. Reported years are candidate claims and may not be role-specific.
- Overall scores sort descending. Equal scores share a rank and preserve input order. Scores are heuristic indicators of role relevance.

Legacy Python callers and multipart clients that supply the original required-skill weight can continue using the historical scoring contract.

## Limits

PDF processing is capped at 30 pages and 100,000 extracted characters. Scanned or encrypted documents may be unreadable. Resume excerpts are capped at 4,000 characters and hidden by default. The keyword score is batch-relative and MiniLM truncates inputs at its tokenizer limit. Skill taxonomy coverage, redaction, and experience extraction are heuristic. There is no cross-user sharing or persistent candidate storage.
