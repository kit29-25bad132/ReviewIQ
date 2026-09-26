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

---

## V2-P2 Table: `review_embeddings` (pgvector)

Canonical source: the additive "V2-P2" section of [`supabase_schema.sql`](../supabase_schema.sql).

Backend-only table for semantic retrieval. Requires the `vector` (pgvector) extension. The frontend `public.reviews` table is unchanged.

| Column | Type | Nullable | Purpose |
|---|---|---|---|
| id | BIGINT IDENTITY | No | Primary key |
| review_id | TEXT | No | Source review identifier (or fingerprint) |
| product_id | TEXT | Yes | Product context (filter) |
| fingerprint | TEXT | No | Deterministic dedup key (`sha256(product_id + canonical text)`), unique |
| original_text | TEXT | No | Original review text (evidence grounding) |
| normalized_text | TEXT | No | Preprocessed text that was embedded |
| rating | INTEGER | Yes | 1–5 when available (CHECK) |
| source | TEXT | Yes | Provenance (e.g. `dataset`, `catalog`) |
| review_date | TIMESTAMPTZ | Yes | Review date when available |
| embedding_model | TEXT | No | e.g. `gemini-embedding-001` |
| embedding_dimension | INTEGER | No | 768 (CHECK matches the column) |
| embedding | VECTOR(768) | No | Embedding vector |
| created_at | TIMESTAMPTZ | No | Insert time (UTC) |
| updated_at | TIMESTAMPTZ | No | Upsert time (UTC) |

### Indexes & metric

- Unique index on `fingerprint` (idempotent upsert target).
- Metadata indexes on `product_id`, `rating`, and `(embedding_model, embedding_dimension)`.
- HNSW index `using hnsw (embedding vector_cosine_ops)` for cosine similarity search.
- **Similarity convention: cosine.** pgvector `<=>` returns cosine distance; retrieval reports `similarity = 1 - distance`.

### RLS

RLS is enabled with **no** anon/authenticated policies: only the backend's service/direct Postgres connection accesses embeddings. The frontend public key cannot read or write them.

### Prerequisites / status

- The `vector` extension must be enabled on the Supabase project.
- The connection string is supplied to the backend via `DATABASE_URL` (or `SUPABASE_DB_URL`) and must never reach the frontend.
- **The migration is additive and has NOT been verified against a live Supabase project.**
