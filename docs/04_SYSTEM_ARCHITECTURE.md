# ReviewIQ — System Architecture

## Components
- **Frontend:** Next.js, React, TypeScript, Tailwind CSS, shadcn/ui, Recharts.
- **Backend:** FastAPI, Pydantic, Uvicorn.
- **AI layer:** Google Gemini API through Google GenAI SDK.
- **Data layer:** Supabase-hosted PostgreSQL.
- **Deployment:** Vercel frontend, Render backend, Supabase database.

## Request Lifecycle
Browser → Next.js UI → HTTP/JSON → FastAPI route → request schema → review service → AI analyzer → Gemini → structured result → Pydantic validation → application validation → database persistence → response schema → frontend.

## Responsibility Boundaries
- LLM: language interpretation and extraction.
- Application code: validation, persistence, analytics, filtering, pagination, retries, error mapping, and security.
- Database: durable storage and relational integrity.
- Frontend: user interaction, state, rendering, and user-facing errors.

## Principle
Use AI for language understanding and deterministic code for deterministic computation.
