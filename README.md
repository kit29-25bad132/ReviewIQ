# ReviewIQ

### AI-Powered Product Review Intelligence

ReviewIQ transforms unstructured product reviews into structured,
actionable product intelligence. It helps users understand customer
sentiment, ratings, recurring strengths and weaknesses, and key review
themes without manually reading large volumes of feedback.

[![Frontend](https://img.shields.io/badge/Frontend-React%20%7C%20TypeScript-3178C6)](https://react.dev/)
[![Backend](https://img.shields.io/badge/Backend-FastAPI-009688)](https://fastapi.tiangolo.com/)
[![Database](https://img.shields.io/badge/Database-Supabase%20PostgreSQL-3FCF8E)](https://supabase.com/)
[![AI](https://img.shields.io/badge/AI-Google%20Gemini-4285F4)](https://ai.google.dev/)

> **Deployment status --- 24 November 2026:** The frontend and backend
> are deployed. The backend health endpoint responds, but full
> production functionality has not yet been verified. Database-backed
> product search was previously failing during the PostgreSQL connection
> step; this remains an item to retest before claiming end-to-end
> production readiness.

------------------------------------------------------------------------

## Contents

-   [Overview](#overview)
-   [Live deployment](#live-deployment)
-   [System architecture](#system-architecture)
-   [Technology stack](#technology-stack)
-   [Key capabilities](#key-capabilities)
-   [Application workflow](#application-workflow)
-   [Repository and deployment setup](#repository-and-deployment-setup)
-   [Environment configuration](#environment-configuration)
-   [Run locally](#run-locally)
-   [Testing and release
    verification](#testing-and-release-verification)
-   [Known issue and next steps](#known-issue-and-next-steps)
-   [Project scope](#project-scope)

## Overview

Product reviews contain valuable customer feedback, but extracting
useful insights from large collections of unstructured text can be
time-consuming. ReviewIQ addresses this problem by combining a web
application, API services, AI-powered review analysis, and a
database-backed product and review layer.

The application is designed to let users find or select a product,
analyze review content, and explore concise results such as:

-   Overall sentiment and rating
-   Commonly mentioned product advantages
-   Recurring complaints and disadvantages
-   A concise summary of customer feedback
-   Structured insights that can be presented consistently in the user
    interface

## Live deployment

  ----------------------------------------------------------------------------------------------------------------
  Component               Deployment                                                       Current status
  ----------------------- ---------------------------------------------------------------- -----------------------
  Frontend                [reviewiq-final.vercel.app](https://reviewiq-final.vercel.app)   Deployed

  Backend API             [Render service](https://reviewiq-backend-qox7.onrender.com)     Deployed

  Health endpoint         [/health](https://reviewiq-backend-qox7.onrender.com/health)     Responding

  Database-backed product Supabase PostgreSQL                                              Requires production
  search                                                                                   retesting

  Full end-to-end         Frontend → API → database → AI                                   Not yet verified
  workflow                                                                                 
  ----------------------------------------------------------------------------------------------------------------

A successful `/health` response confirms that the API process is
reachable. It does **not** establish that database connectivity, product
search, retrieval, or AI analysis is functioning correctly in
production.

## System architecture

``` text
                         ┌──────────────────────────┐
                         │           User           │
                         └────────────┬─────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────┐
                    │ React + TypeScript + Vite       │
                    │ Frontend — Vercel               │
                    └────────────────┬────────────────┘
                                     │ HTTPS API requests
                                     ▼
                    ┌─────────────────────────────────┐
                    │ FastAPI Backend — Render        │
                    │ Request handling and validation │
                    └─────────┬───────────────┬───────┘
                              │               │
                 ┌────────────▼──────┐  ┌─────▼────────────────┐
                 │ Supabase          │  │ AI analysis workflow │
                 │ PostgreSQL        │  │ Gemini integration   │
                 │                   │  │ Provider orchestration│
                 │ Products/reviews  │  │ Structured validation│
                 │ pgvector retrieval│  │ Grounding / RAG*      │
                 └───────────────────┘  └─────────┬────────────┘
                                                  │
                                                  ▼
                                  ┌────────────────────────────┐
                                  │ Structured analysis result │
                                  │ returned to the frontend   │
                                  └────────────────────────────┘
```

\* Retrieval-augmented and evidence-grounding behavior depends on the
enabled configuration and the deployed code version.

The frontend and backend are deployed as separate services. The frontend
communicates with the public backend URL over HTTPS. The backend uses
its configured database connection and AI-provider credentials to
process requests.

## Technology stack

  Layer                 Technologies
  --------------------- -----------------------------------------------------
  Frontend              React, TypeScript, Vite
  Backend               Python, FastAPI, Uvicorn, Pydantic
  AI integration        Google Gemini API and provider/gateway components
  Orchestration         LangGraph workflow components
  Data processing       Pandas
  Database              Supabase-hosted PostgreSQL
  Vector search         pgvector; V2 design uses 768-dimensional embeddings
  Database driver       Psycopg
  Frontend deployment   Vercel
  Backend deployment    Render
  Testing               Pytest and frontend production-build checks

This table describes technologies represented in the project codebase
and architecture. It should not be interpreted as proof that every
integration is currently enabled or verified in the deployed
environment.

## Key capabilities

The project codebase includes the following functionality and
development foundations:

-   **Structured review analysis:** produces sentiment, rating, pros,
    cons, and a concise summary.
-   **Sentiment classification:** supports positive, negative, neutral,
    and mixed labels.
-   **Rating provenance:** distinguishes explicitly supplied ratings
    from inferred ratings.
-   **Validated data contracts:** uses Pydantic-based request and
    response validation.
-   **Evidence-grounding foundation:** includes review-analysis contract
    and grounding work in the V2 development history. Confirm the
    deployed commit and runtime behavior before describing production
    grounding as verified.
-   **AI provider integration:** includes Gemini integration and
    model/provider orchestration components.
-   **Product and review data layer:** includes Supabase/PostgreSQL
    integration and product catalog/search routes.
-   **Semantic retrieval foundation:** includes embedding and
    vector-retrieval work using Gemini embeddings and pgvector.
-   **Analytics and data exploration:** includes dataset processing and
    product/review analytics work.

Actual feature availability depends on the deployed commit, environment
configuration, database schema, provider credentials, and external API
quotas.

## Application workflow

1.  The user opens the ReviewIQ frontend.
2.  The frontend sends an HTTPS request to the FastAPI backend using
    `VITE_API_BASE_URL`.
3.  FastAPI validates the incoming request and routes it to the relevant
    product or analysis service.
4.  Product and review services access Supabase PostgreSQL.
    Retrieval-enabled workflows can use embeddings and vector search
    when configured.
5.  The AI workflow invokes the configured Gemini integration and
    validates the structured response.
6.  The API returns the result to the frontend for presentation.

## Repository and deployment setup

-   **GitHub repository:**
    [kit29-25bad132/ReviewIQ](https://github.com/kit29-25bad132/ReviewIQ)
-   **Reported deployment branch:** `main-final`
-   **Vercel project:** `reviewiq-final`
-   **Render service:** `ReviewIQ-Backend`

### Frontend --- Vercel

The reported Vercel configuration is:

  Setting                Value
  ---------------------- ---------------------
  Root directory         `frontend`
  Build command          `npm run build`
  Output directory       `dist`
  Backend URL variable   `VITE_API_BASE_URL`

Set `VITE_API_BASE_URL` to the public Render backend base URL expected
by the frontend code. Avoid adding an endpoint path unless the
application explicitly expects one.

Vite environment variables are embedded during the build. Redeploy the
frontend after changing them.

### Backend --- Render

The FastAPI backend is deployed as a separate Render service. Verify the
service's start command, Python dependency installation, environment
variables, and database network connectivity in the Render dashboard.

Never commit API keys, database passwords, or other credentials to the
repository. Store secrets in the deployment platform's
environment-variable settings.

## Environment configuration

Use the exact variable names consumed by the current code and deployment
configuration. The following settings are documented for the current
architecture.

### Frontend variables

  -----------------------------------------------------------------------
  Variable                            Purpose
  ----------------------------------- -----------------------------------
  `VITE_API_BASE_URL`                 Public base URL of the backend API

  `VITE_SUPABASE_URL`                 Supabase project URL, if used by
                                      the frontend

  `VITE_SUPABASE_ANON_KEY` /          Public Supabase client key, if used
  `VITE_SUPABASE_PUBLISHABLE_KEY`     by the frontend
  -----------------------------------------------------------------------

Frontend variables belong in the Vercel project settings. Do not expose
server-side secrets through `VITE_` variables.

### Backend variables

  ---------------------------------------------------------------------------------------
  Variable                               Requirement / default    Purpose
  -------------------------------------- ------------------------ -----------------------
  `ALLOWED_ORIGINS`                      Set explicitly in        Comma-separated list of
                                         production               permitted browser
                                                                  origins

  `DATABASE_URL`                         Required for             Primary PostgreSQL
                                         database-backed features connection string

  `SUPABASE_DB_URL`                      Fallback if              Alternative PostgreSQL
                                         `DATABASE_URL` is unset  connection string

  `GEMINI_API_KEY`                       At least one AI provider Gemini API
                                         key is needed for AI     authentication
                                         features                 

  `GROQ_API_KEY`                         Optional                 Groq provider
                                                                  authentication

  `OPENROUTER_API_KEY`                   Optional                 OpenRouter provider
                                                                  authentication

  `GEMINI_MODEL`                         Optional; documented     Primary Gemini model
                                         default:                 override
                                         `gemini-3.8-flash`       

  `ROUTING_STRATEGY`                     Optional; default:       AI provider/model
                                         `gemini_first`           routing strategy;
                                                                  documented alternative:
                                                                  `cost_aware`

  `AI_REQUEST_TIMEOUT_SECONDS`           Optional; default: `30`  AI request timeout

  `RETRY_MAX_ATTEMPTS`                   Optional; default: `2`   Maximum retry attempts

  `RETRY_BASE_DELAY_SECONDS`             Optional; default: `0.5` Initial retry delay

  `RETRY_MAX_DELAY_SECONDS`              Optional; default: `8`   Maximum retry delay

  `RETRY_JITTER`                         Optional; default:       Enables retry jitter
                                         `true`                   

  `EMBEDDING_MODEL`                      Optional; default:       Embedding model
                                         `gemini-embedding-001`   

  `EMBEDDING_DIMENSION`                  Optional; default: `768` Embedding vector size;
                                                                  must match the database
                                                                  column

  `EMBEDDING_BATCH_SIZE`                 Optional; default: `100` Embedding batch size

  `RAG_ENABLED`                          Optional; disabled by    Enables the configured
                                         default                  analysis RAG workflow

  `RAG_INTELLIGENCE_ENABLED`             Optional; default:       Controls the documented
                                         `true`                   pros/cons grounding RAG
                                                                  phase

  `LLM_CACHE_ENABLED`                    Optional; disabled by    Controls the
                                         default                  Postgres-backed LLM
                                                                  result cache

  `EMBEDDING_CACHE_ENABLED`              Optional; disabled by    Controls the embedding
                                         default                  cache

  `PRODUCT_ANALYSIS_CACHE_TTL_SECONDS`   Optional; default:       Product-analysis cache
                                         `3600`                   lifetime

  `PRODUCT_ANALYSIS_CACHE_MAX_ENTRIES`   Optional; default: `500` Maximum in-memory
                                                                  product-analysis cache
                                                                  entries

  `HOST`                                 Optional; default:       API bind host
                                         `127.0.0.1`              

  `PORT`                                 Optional; default:       API bind port
                                         `8000`                   
  ---------------------------------------------------------------------------------------

The repository's `backend/.env.example` is the detailed configuration
template. Check it and the current source code before deploying, as
variable names and defaults can change.

### CORS configuration

The backend reads allowed browser origins from `ALLOWED_ORIGINS` in
`backend/main.py`.

The documented development defaults allow loopback origins such as
`localhost` and `127.0.0.1`. The deployed Vercel domain must be added
explicitly in the Render environment settings.

Example:

``` env
ALLOWED_ORIGINS=https://reviewiq-final.vercel.app
```

Use a comma-separated list of full origins (scheme and host), without
URL paths or trailing slashes. Include any additional production
frontend domains that should be permitted.

### Understanding the health endpoint

`GET /health` is a process/configuration health check, not a complete
integration test.

  -----------------------------------------------------------------------
  It reports/checks                   It does not verify
  ----------------------------------- -----------------------------------
  API process is reachable            PostgreSQL connection succeeds

  Application version                 Database schema, migrations,
                                      extensions, or required tables

  Configured AI provider information  Provider credentials are valid or
                                      API quota is available

  Whether an AI provider key is       A model can successfully complete a
  present                             request

  Basic configuration state           Embeddings, pgvector, retrieval
                                      index, or cache behavior

  ---                                 Frontend Supabase browser
                                      configuration
  -----------------------------------------------------------------------

A `200 OK` response must therefore be followed by tests against real
database-backed and AI-backed application routes.

## Run locally

The following commands reflect the documented project layout. Confirm
the dependency file and import path in the current checkout before
running them.

### 1. Backend

From the repository root:

``` bash
python -m venv .venv
```

Activate the virtual environment.

**Windows PowerShell**

``` powershell
.venv\Scripts\Activate.ps1
```

**macOS / Linux**

``` bash
source .venv/bin/activate
```

Install backend dependencies:

``` bash
pip install -r backend/requirements.txt
```

Configure the required environment variables, then start the API:

``` bash
uvicorn backend.main:app --reload
```

If the repository's dependency file or application import path differs,
use the paths defined by the current checkout.

### 2. Frontend

In a separate terminal:

``` bash
cd frontend
npm install
npm run dev
```

Run a production build check with:

``` bash
npm run build
```

## Testing and release verification

Run the backend test suite using the established project command:

``` bash
python -m pytest backend/tests -q
```

Before declaring a release production-ready, verify the deployed version
against this checklist:

-   [ ] Frontend production build completes successfully.
-   [ ] Backend `/health` endpoint returns HTTP 200.
-   [ ] Frontend requests reach the intended backend URL.
-   [ ] CORS permits the exact deployed frontend origin.
-   [ ] Product search returns valid results from the production
    database.
-   [ ] Database-backed product routes complete without connection
    errors.
-   [ ] Review analysis returns a response that satisfies the expected
    schema.
-   [ ] Evidence presented for analysis claims is supported by the
    relevant review text or retrieval context.
-   [ ] Embedding and vector-retrieval routes work when enabled.
-   [ ] Frontend loading, empty-result, API-error, and timeout states
    behave correctly.
-   [ ] The tested commit hash and verification date are recorded.

## Known issue and next steps

### Production database connectivity

The latest reported deployment investigation identified a failure in the
product-search path when Psycopg attempted to open a PostgreSQL
connection using the configured DSN.

The following checks should be completed:

1.  Confirm which database environment variable the deployed code reads.
2.  Verify that Render has the variable configured and that its value is
    present and correctly formatted.
3.  Check the Supabase host, port, database name, username, and
    password.
4.  Confirm that the selected Supabase connection mode is compatible
    with the Render runtime and network.
5.  Verify SSL parameters and URL-encoding of special characters in
    credentials where required.
6.  Confirm that the production database has the required schema,
    extensions, tables, and migrations.
7.  Inspect the underlying server exception without logging or exposing
    credentials.

### Frontend-to-backend connectivity

-   Confirm that Vercel has the correct `VITE_API_BASE_URL` for the
    active deployment.
-   Confirm that Render's `ALLOWED_ORIGINS` includes the active frontend
    origin.
-   Use the browser Network tab to distinguish CORS failures from API
    errors, timeouts, and incorrect URLs.
-   Redeploy the frontend after changing Vite environment variables.

### End-to-end production verification

After the database connection is corrected, test product search and
review analysis through the deployed UI. Record the deployed commit,
test date, observed API responses, and any remaining limitations.

## Project scope

ReviewIQ is intended to be a practical AI-powered product-review
intelligence system, with emphasis on:

-   Structured and validated AI outputs
-   Evidence-grounded review insights
-   Retrieval-supported analysis
-   Reliable provider/model orchestration
-   Cost-conscious AI usage
-   A hosted deployment that does not require users to run local
    language models

Multi-agent execution, exposed chain-of-thought, quantization, and
local-model runtime are outside the current project scope.

## Current status summary

  -----------------------------------------------------------------------
  Area                                Status
  ----------------------------------- -----------------------------------
  Frontend deployment                 Available

  Backend deployment                  Available; health endpoint responds

  AI configuration                    Gemini was reported as configured
                                      by the backend health endpoint

  Database-backed product search      Production connectivity requires
                                      investigation and retesting

  Full production end-to-end          Pending successful database,
  readiness                           search, and analysis verification
  -----------------------------------------------------------------------

------------------------------------------------------------------------

**Maintenance note:** This README reflects the project and deployment
information supplied for the 24 November 2026 update. Revise the
deployment status after the database issue is resolved and the complete
production workflow has been tested.
