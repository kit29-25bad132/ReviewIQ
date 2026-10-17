# ReviewIQ — AI-Powered Product Review Analyzer

> **Project status (updated: 16 October 2026):** The frontend is deployed on Vercel and the FastAPI backend is deployed on Render. The backend health endpoint responds successfully, but the deployed application is **not yet fully verified end to end**: database-backed product search is failing in the deployed environment and needs to be fixed and retested.

ReviewIQ turns unstructured product reviews into structured product intelligence, helping users understand customer sentiment, ratings, recurring pros and cons, and review themes.

## Table of contents

- [Overview](#overview)
- [Current deployment status](#current-deployment-status)
- [Architecture](#architecture)
- [Technology stack](#technology-stack)
- [Implemented capabilities](#implemented-capabilities)
- [Request flow](#request-flow)
- [Repository and deployment configuration](#repository-and-deployment-configuration)
- [Environment configuration](#environment-configuration)
- [Run locally](#run-locally)
- [Testing and verification](#testing-and-verification)
- [Known issues and next steps](#known-issues-and-next-steps)
- [Project scope](#project-scope)

## Overview

ReviewIQ is an AI-powered product review analysis application. It combines a web interface, a Python API, an LLM-based analysis workflow, and a database-backed product/review layer.

The intended user experience is to select or search for a product, analyze review text, and view concise, structured results instead of manually reading large volumes of reviews.

## Current deployment status

| Component | Current status | Details |
|---|---|---|
| Frontend | Deployed | Vercel project: `reviewiq-final` |
| Frontend URL | Available | https://reviewiq-final.vercel.app |
| Backend API | Deployed | Render service: `ReviewIQ-Backend` |
| Backend URL | Available | https://reviewiq-backend-qox7.onrender.com |
| Backend health check | Responding | `/health` returns an `ok` status and reports Gemini as the AI provider |
| Database-backed product search | **Needs investigation** | Render logs show a failure while opening a PostgreSQL connection through `psycopg.connect(dsn)` |
| Full production end-to-end flow | **Not yet verified** | The frontend reports that it cannot connect to the backend / product search fails, despite the health endpoint responding |

**Important:** A successful `/health` response confirms that the API process is reachable; it does not by itself prove that database queries, product search, AI analysis, and all frontend flows work correctly.

## Architecture

```text
User
  |
  v
React + TypeScript + Vite frontend (Vercel)
  |
  | HTTPS API requests
  v
FastAPI backend (Render)
  |
  +--> Product catalog and review data
  |
  +--> Supabase PostgreSQL / pgvector
  |      +--> Product and review persistence
  |      +--> Embeddings and semantic retrieval (where configured)
  |
  +--> AI analysis and orchestration
         +--> Gemini model/provider integration
         +--> Structured response validation
         +--> Evidence-grounding and retrieval workflow (as implemented)
  |
  v
Structured analysis returned to the frontend
```

The deployed frontend and backend are separate services. The frontend must use the correct public backend base URL, and the backend must have valid production database credentials, CORS configuration, and AI-provider configuration.

## Technology stack

| Layer | Technologies |
|---|---|
| Frontend | React, TypeScript, Vite |
| Backend API | Python, FastAPI, Uvicorn, Pydantic |
| AI | Google Gemini API; AI provider/gateway and fallback orchestration in the codebase |
| Orchestration | LangGraph-based workflow components |
| Data processing | Pandas |
| Database | Supabase-hosted PostgreSQL |
| Vector retrieval | pgvector, configured for 768-dimensional embeddings in the V2 design |
| Database driver | Psycopg |
| Frontend hosting | Vercel |
| Backend hosting | Render |
| Testing | Pytest and frontend build checks |

The table describes technologies present in the project architecture/codebase; it does not mean every feature or production integration has passed end-to-end verification.

## Implemented capabilities

The project codebase includes the following capabilities:

- **Review analysis:** structured sentiment, rating, pros, cons, and summary output.
- **Sentiment labels:** positive, negative, neutral, and mixed.
- **Rating provenance:** supports distinguishing an explicit rating from an inferred rating.
- **Structured contracts:** Pydantic-based request/response validation.
- **Evidence grounding:** review-analysis contract and grounding work are present in the V2 development history; verify the current deployed commit before treating production behavior as confirmed.
- **AI provider integration:** Gemini integration and model/provider orchestration components.
- **Product/review data layer:** Supabase/PostgreSQL integration and product catalog/search routes.
- **Retrieval foundation:** embedding and vector-retrieval work using Gemini embeddings and pgvector.
- **Analytics and data exploration:** dataset and product/review analytics work in the codebase.

Some capabilities depend on production environment variables, database schema/migrations, provider quotas, and the exact commit deployed. Production readiness should be judged by the end-to-end checks below, not by code presence alone.

## Request flow

1. A user opens the Vercel-hosted frontend.
2. The frontend sends an HTTPS request to the FastAPI backend using `VITE_API_BASE_URL`.
3. FastAPI validates the request and routes it to the relevant product or analysis service.
4. Product and review routes access the configured Supabase PostgreSQL database. Retrieval-enabled flows can use embeddings/vector search where configured.
5. The AI workflow calls the configured Gemini integration and validates the structured result.
6. The API returns the result to the frontend for display.

## Repository and deployment configuration

- **Git repository:** https://github.com/kit29-25bad132/ReviewIQ
- **Reported deployment branch:** `main-final`
- **Vercel frontend project:** `reviewiq-final`
- **Render backend service:** `ReviewIQ-Backend`

### Frontend (Vercel)

The frontend project is configured with:

- Root directory: `frontend`
- Build command: `npm run build`
- Output directory: `dist`
- Environment variable: `VITE_API_BASE_URL`

Set `VITE_API_BASE_URL` to the public Render backend URL, without accidentally adding an endpoint path if the frontend code expects a base URL. After changing a Vite environment variable, trigger a new frontend deployment because Vite values are embedded at build time.

### Backend (Render)

The backend is deployed as a separate FastAPI service. Confirm its start command, Python dependency installation, environment variables, and database network connectivity in the Render dashboard. Do not put private keys or database passwords in this README or in frontend environment variables.

## Environment configuration

Use the actual variable names referenced by the current code and deployment configuration. Common configuration needed by this architecture includes:

| Variable / setting | Used by | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | Vercel frontend | Public base URL for the backend API |
| `GEMINI_API_KEY` | Render backend | Authentication for Gemini API calls |
| `DATABASE_URL` (first) / `SUPABASE_DB_URL` (fallback) | Render backend | Direct Postgres (Supabase) connection string |
| `ALLOWED_ORIGINS` | Render backend | Allowed CORS origins — see [CORS and production origins](#cors-and-production-origins) below |

**Variable names verified against the current code:** the backend reads `DATABASE_URL` first and falls back to `SUPABASE_DB_URL`, and CORS reads `ALLOWED_ORIGINS`. The complete list of backend variables with defaults is documented under [CORS and production origins](#cors-and-production-origins) below. Use the appropriate Supabase connection string and SSL settings for the chosen connection mode. Keep all secrets in Vercel/Render environment settings, never in committed files.

### CORS and production origins

The backend allows cross-origin browser requests based on the `ALLOWED_ORIGINS` environment variable (`backend/main.py`):

- **Default (development):** loopback origins only — `http://localhost:5173`, `http://127.0.0.1:5173`, `http://localhost:5174`, `http://127.0.0.1:5174`, `http://localhost:3000`, `http://127.0.0.1:3000` — plus a host regex that matches only loopback hosts with any port: `^http://(localhost|127\.0\.0\.1)(:\d+)?$`.
- **Production:** the deployed frontend origin does not match those loopback defaults, so it must be set explicitly to the actual frontend URL (Render environment setting). Example:

```text
ALLOWED_ORIGINS=https://reviewiq-final.vercel.app
```

- The value is a comma-separated list of full origins (scheme + host, no path, no trailing slash). The loopback regex always applies regardless of the list.
- Preflight (`OPTIONS`) requests are answered by FastAPI's CORS middleware, and its headers also wrap normal and error responses. The frontend sends JSON requests, so every cross-origin call requires a successful preflight.

#### Required backend (Render) environment variables

None of these are required for the process to boot or for `GET /health` to return 200 — each powers a specific feature, so a missing variable degrades or disables that feature instead of blocking startup.

| Variable | Requirement | Purpose / default |
|---|---|---|
| `ALLOWED_ORIGINS` | Required in production | Comma-separated allowed CORS origins (default: loopback development origins only) |
| `DATABASE_URL` | Required for DB-backed features | Direct Postgres connection string (checked first) |
| `SUPABASE_DB_URL` | Optional | Fallback connection string used only when `DATABASE_URL` is unset |
| `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY` | At least one required for any AI feature | Provider keys in fallback order (Gemini → Groq → OpenRouter); unconfigured providers are skipped |
| `GEMINI_MODEL` | Optional | Primary Gemini model override (default: `gemini-3.8-flash`) |
| `ROUTING_STRATEGY` | Optional | `gemini_first` (default) or `cost_aware` |
| `AI_REQUEST_TIMEOUT_SECONDS` | Optional | Per-request AI timeout in seconds (default: `30`) |
| `RETRY_MAX_ATTEMPTS`, `RETRY_BASE_DELAY_SECONDS`, `RETRY_MAX_DELAY_SECONDS`, `RETRY_JITTER` | Optional | Bounded retry tuning (defaults: `2`, `0.5`, `8`, `true`) |
| `EMBEDDING_MODEL`, `EMBEDDING_DIMENSION`, `EMBEDDING_BATCH_SIZE` | Optional (embeddings) | Defaults: `gemini-embedding-001`, `768`, `100`; dimension must match the pgvector column |
| `RAG_ENABLED` plus RAG context settings | Optional (analysis RAG) | Disabled by default; see `backend/.env.example` |
| `RAG_INTELLIGENCE_ENABLED` | Optional | Phase 5 pros/cons grounding RAG (default: enabled) |
| `LLM_CACHE_ENABLED`, `EMBEDDING_CACHE_ENABLED` plus cache TTLs | Optional | Postgres-backed result caches, disabled by default |
| `PRODUCT_ANALYSIS_CACHE_TTL_SECONDS`, `PRODUCT_ANALYSIS_CACHE_MAX_ENTRIES` | Optional | In-memory product-analysis cache (defaults: `3600` seconds, `500` entries) |
| `HOST`, `PORT` | Optional | Bind address (defaults: `127.0.0.1`, `8000`) |

The full commented template with defaults lives in `backend/.env.example`. Frontend-side variables (`VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` / `VITE_SUPABASE_PUBLISHABLE_KEY`) are set in Vercel, never here.

#### What `/health` checks — and what it does not

| `/health` checks (200 OK means...) | `/health` does NOT check |
|---|---|
| The API process is reachable | Postgres/DSN validity — a database-backed request can still fail |
| The reported app `version` | Schema, migrations, extensions, required tables |
| `ai_provider`: which provider **keys are configured** (environment presence only) | Whether provider credentials are valid, quota remains, or a model responds |
| `ai_configured`: at least one provider key is present | Embeddings, pgvector, and the retrieval index |
| — | The evaluation cache and dataset files |
| — | Frontend Supabase browser configuration |

**Warning:** a `200` from `/health` proves only that the process is up and configuration is present — it does **not** prove that database-backed product search, RAG, AI analysis, or any other feature works. Verify the actual database-backed routes end-to-end (see [Testing and verification](#testing-and-verification)).

## Run locally

These are typical development steps. Check the repository's current directory names and dependency files before running them.

### Backend

```bash
# From the repository root
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# Install the backend's declared dependencies using the repository's
# current requirements file or project configuration.
pip install -r backend/requirements.txt

# Start the API (adjust the import path if the repository differs)
uvicorn backend.main:app --reload
```

If the repository's dependency file is elsewhere, use that file instead. Configure the required environment variables before starting the API.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

For a production-build check:

```bash
npm run build
```

## Testing and verification

Run tests using the test configuration and commands present in the current checkout. For the backend, the project's established test command is:

```bash
python -m pytest backend/tests -q
```

Before announcing a production-ready release, verify all of the following against the currently deployed commit:

- [ ] Frontend production build succeeds.
- [ ] Backend `/health` returns HTTP 200.
- [ ] Browser requests reach the correct backend URL.
- [ ] CORS permits the exact deployed frontend origin.
- [ ] Product search returns valid results from the production database.
- [ ] Database-backed product routes work without connection errors.
- [ ] Review analysis returns schema-valid output.
- [ ] Evidence shown as supporting a claim actually comes from the relevant review text/retrieval context.
- [ ] Embedding and retrieval routes work if enabled in production.
- [ ] Loading, empty-result, API-error, and timeout states render correctly in the frontend.

## Known issues and next steps

### 1. Fix the production database connection

The latest reported Render traceback reaches the product search path and fails when Psycopg attempts to connect using the configured DSN. Verify:

1. The exact database environment variable name read by the current code.
2. That the Render environment contains that variable and its value is not empty or malformed.
3. That the Supabase connection string, host, port, database name, username, and password are correct.
4. That the selected Supabase connection mode is compatible with the Render runtime/network; use the connection option recommended by Supabase for the deployment environment.
5. That SSL parameters and URL-encoding of special characters in credentials are correct where required.
6. That the deployed database schema and required extensions/tables exist.
7. That the backend logs show the underlying exception without exposing credentials.

Do not treat the API as fully healthy just because `/health` works; test the actual database-backed routes.

### 2. Confirm frontend URL and CORS

- Confirm the production Vercel environment has the correct `VITE_API_BASE_URL`.
- Confirm the backend's CORS allowlist includes `https://reviewiq-final.vercel.app` (or the actual production domain in use).
- Inspect the browser Network tab to distinguish a CORS rejection from an API `500`, timeout, or incorrect URL.
- Redeploy the frontend after changing Vite environment variables.

### 3. Complete end-to-end production verification

After fixing the database connection, test product search and review analysis from the deployed UI. Record the tested commit, test date, API responses, and any remaining limitations.

## Project scope

ReviewIQ is being developed as a practical AI product-review intelligence system, with emphasis on structured outputs, grounded claims, retrieval, reliability, and cost-conscious model use.

The intended deployment keeps model execution in hosted APIs rather than requiring users to run local LLMs. Features such as multi-agent execution, chain-of-thought exposure, quantization, and local-model runtime are outside the current scope.

## Status summary

- **Frontend deployment:** available.
- **Backend deployment:** available; health endpoint responds.
- **AI configuration:** backend health has reported Gemini configured.
- **Database-backed product search:** currently needs a production configuration/connectivity fix.
- **Full end-to-end production readiness:** pending successful database, search, and analysis verification.

---

*This README reflects the latest status shared for the project on 16 October 2026. Update it after the database fix and end-to-end deployment checks are completed.*
