# HireLens AI

HireLens AI screens batches of technical resumes against a job description. It exposes the evidence and contributions behind each ranking, supports shortlisting and comparison, and offers optional Gemini interview preparation. Use the results as decision support and review candidate evidence before making hiring decisions.

## Run locally

The dependency lock targets Python 3.12.8 on macOS ARM64 and Linux x86_64. Use Node.js 22.12 or newer and uv 0.13.9.

```bash
uv sync --frozen
uv run --frozen python -m src.warm_cache
npm ci --prefix frontend
```

Start the API and frontend in separate terminals from the repository root.

```bash
./run_backend.sh
npm run dev --prefix frontend
```

Open the [local frontend](http://127.0.0.1:5173). FastAPI serves [OpenAPI documentation](http://127.0.0.1:8000/docs), [liveness](http://127.0.0.1:8000/api/health), and [readiness](http://127.0.0.1:8000/api/ready). Vite proxies local API requests. The workspace includes a synthetic job and sample resumes for trying the full workflow.

Copy [.env.example](.env.example) to `.env` to override server defaults. Set `GEMINI_API_KEY` there for optional AI insights and `GEMINI_MODEL` to override `gemini-2.5-flash`. `VITE_API_BASE_URL` is public configuration for the frontend build. Use [frontend/.env.example](frontend/.env.example) if you need to specify the API origin explicitly for development.

## Quality checks

```bash
OMP_NUM_THREADS=1 HF_HUB_OFFLINE=1 uv run --frozen pytest -q
npm run typecheck --prefix frontend
npm run lint --prefix frontend
npm test --prefix frontend
npm run build --prefix frontend
npm audit --prefix frontend --audit-level=high
(cd frontend && npx playwright install chromium && npm run test:e2e)
uvx pip-audit --path .venv/lib/python3.12/site-packages --progress-spinner off
```

Playwright starts both services and uses bundled synthetic PDF and DOCX resumes with Gemini disabled. Set `PLAYWRIGHT_CHANNEL=chrome` to use an installed Chrome channel. Mocked backend tests cover Gemini response validation, timeouts and unavailable states.

## Deploy on the existing services

| Service | Existing production URL | Configuration |
| --- | --- | --- |
| GitHub | [AI-Resume-Screening](https://github.com/phanendrababu464-lab/AI-Resume-Screening) | Branch `main` |
| Vercel | [HireLens AI](https://ai-resume-screening-three-kohl.vercel.app) | Repository root, `npm ci --prefix frontend`, `npm run build --prefix frontend`, output `frontend/dist` |
| Render | [FastAPI service](https://ai-resume-screening-3-1r1d.onrender.com) | Repository root, build and start commands in [render.yaml](render.yaml), health check `/api/health` |

On Vercel, set `VITE_API_BASE_URL` to the Render URL. On Render, use `PYTHON_VERSION=3.12.8`, `HF_HUB_OFFLINE=1`, `MAX_RESUMES_PER_BATCH=25`, and the Vercel origin in `CORS_ORIGINS`. Add the Gemini API key through the Render secret settings if AI insights are needed. Apply these settings to the **existing** projects and deploy the same Git commit on both. Configure the existing Render service directly if it was created outside a Blueprint.

The model is cached at build time and warmed in the background after Uvicorn starts. Confirm that the existing Render instance can load the CPU model within its memory allowance and check the startup logs if readiness stays at 503. Review instance resources and costs in the [Render plan documentation](https://render.com/pricing) before changing the plan.

Verify `/api/health` and `/api/ready` independently, then screen representative synthetic PDF and DOCX files from the Vercel UI. Check candidate details, comparison, exports, and responsive navigation. Generate insights with synthetic data to verify configured Gemini access.

See the [architecture](docs/architecture.md), [API guide](docs/api.md), and [security and privacy notes](SECURITY.md).
