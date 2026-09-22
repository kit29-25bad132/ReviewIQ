# ReviewIQ — Deployment

## Environments
- Local development
- Optional staging
- Production

## Deployment Flow
Local development → tests/build → GitHub PR → review/merge → frontend deployment on Vercel → backend deployment on Render → Supabase PostgreSQL connectivity → production smoke tests.

## Required Configuration
Document environment variables separately for frontend and backend. Only public, non-sensitive configuration may reach the frontend.

## Production Verification
- Frontend loads.
- Backend health endpoint responds.
- CORS works for approved origin.
- Gemini connectivity works.
- Database connectivity works.
- Analyze flow succeeds.
- History and insights work.
- Safe errors are returned.
- No secrets appear in source, logs, or client bundles.
