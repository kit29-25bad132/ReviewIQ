# ReviewIQ — Security

## Secrets
Never commit:
- `.env`
- `GEMINI_API_KEY`
- Database passwords
- `SUPABASE_SERVICE_ROLE_KEY`
- Private credentials
- Production secrets

Use `.env.example` with placeholders.

## Controls
- Keep Gemini keys and privileged database credentials server-side.
- Validate and limit user input.
- Configure CORS narrowly for approved frontend origins.
- Avoid logging raw secrets or unnecessary sensitive content.
- Return safe public errors and retain detailed diagnostics only in protected logs.
- Apply least privilege to database access.
- Review dependencies and deployment settings.

## Secret Exposure Response
1. Revoke or rotate immediately.
2. Remove exposure from relevant history where appropriate.
3. Audit usage.
4. Replace the secret in secure configuration.
5. Do not assume a later deletion makes an exposed secret safe.
