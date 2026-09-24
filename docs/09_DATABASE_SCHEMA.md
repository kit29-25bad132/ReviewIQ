# ReviewIQ — Database Schema

Canonical source: [`supabase_schema.sql`](../supabase_schema.sql).

## Table: `reviews`

| Column | Type | Nullable | Purpose |
|---|---|---|---|
| id | UUID | No | Primary key (`gen_random_uuid()`) |
| review_text | TEXT | No | Original review for traceability |
| sentiment | TEXT | No | `positive` / `negative` / `neutral` / `mixed` (CHECK) |
| rating | INTEGER | Yes | Validated rating 1–5, or null |
| rating_source | TEXT | Yes* | `explicit` / `inferred` / `not_found` (nullable for legacy rows) |
| pros | JSONB | No | `[{ "point", "evidence" }]` (default `[]`) |
| cons | JSONB | No | `[{ "point", "evidence" }]` (default `[]`) |
| aspects | JSONB | No | `[{ "aspect", "sentiment", "evidence" }]` (default `[]`) |
| summary | TEXT | No | Validated summary |
| created_at | TIMESTAMP | No | Creation time (UTC) |

\* New rows always write `rating_source`; the column stays nullable so pre-migration rows remain valid.

## Constraints & indexes

- `rating` is null or between 1 and 5.
- `sentiment` and `rating_source` use CHECK enums above.
- Index on `created_at desc` for history ordering.

## RLS

Row Level Security is enabled with public anon/authenticated policies for **select**, **insert**, and **delete** (demo posture — anyone holding the frontend publishable/anon key can read and modify rows). See `supabase_schema.sql`.

## Persistence path

Frontend only (`frontend/src/services/historyStorage.ts` → Supabase). The backend does not talk to Supabase and exposes no history API.
