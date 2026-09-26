-- =========================================================
-- PRODUCT REVIEW ANALYZER — SUPABASE DATABASE SCHEMA
-- Run this SQL in your Supabase SQL Editor:
-- https://supabase.com/dashboard/project/_/sql
-- =========================================================

-- 1. Create the 'reviews' table
create table if not exists public.reviews (
    id uuid primary key default gen_random_uuid(),
    review_text text not null,
    sentiment text not null check (sentiment in ('positive', 'negative', 'neutral', 'mixed')),
    rating integer check (rating is null or (rating >= 1 and rating <= 5)),
    rating_source text check (rating_source is null or rating_source in ('explicit', 'inferred', 'not_found')),
    pros jsonb not null default '[]'::jsonb,
    cons jsonb not null default '[]'::jsonb,
    aspects jsonb not null default '[]'::jsonb,
    summary text not null,
    created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- 1b. Additive columns for existing deployments (no-op when already present)
alter table public.reviews
    add column if not exists rating_source text
    check (rating_source is null or rating_source in ('explicit', 'inferred', 'not_found'));

alter table public.reviews
    add column if not exists aspects jsonb not null default '[]'::jsonb;

-- 2. Create index on created_at for fast descending queries
create index if not exists idx_reviews_created_at on public.reviews (created_at desc);

-- 3. Enable Row Level Security (RLS)
alter table public.reviews enable row level security;

-- 4. Set RLS Policies for Anon / Public access
drop policy if exists "Allow public read access" on public.reviews;
create policy "Allow public read access"
on public.reviews
for select
to anon, authenticated
using (true);

drop policy if exists "Allow public insert access" on public.reviews;
create policy "Allow public insert access"
on public.reviews
for insert
to anon, authenticated
with check (true);

drop policy if exists "Allow public delete access" on public.reviews;
create policy "Allow public delete access"
on public.reviews
for delete
to anon, authenticated
using (true);


-- =========================================================
-- V2-P2 — SEMANTIC RETRIEVAL FOUNDATION (pgvector)
-- =========================================================
-- STATUS: NOT VERIFIED against a live Supabase project. Apply and validate
-- manually before relying on it in production.
--
-- PREREQUISITES:
--   1. The pgvector extension must be available on the Supabase project
--      (Database -> Extensions -> "vector"). Supabase installs extensions into
--      the `extensions` schema, which is on the default search_path.
--   2. The backend connects with a role that can read/write this table
--      (the service/direct Postgres connection, never the frontend anon key).
--
-- This section is ADDITIVE: it does not alter or delete existing V1 tables or
-- data. The frontend's `public.reviews` table is untouched.
--
-- Embedding model: gemini-embedding-001. Dimension: 768 (cosine).
-- Changing the embedding model dimension requires a new migration that
-- rewrites this column and its index.
-- =========================================================

create extension if not exists vector with schema extensions;

create table if not exists public.review_embeddings (
    id bigint generated always as identity primary key,
    review_id text not null,
    product_id text,
    -- Deterministic sha256(product_id + canonicalized review text). Unique so
    -- upserts are idempotent and duplicates never create a second vector row.
    fingerprint text not null,
    -- Original review text is retained for later evidence grounding.
    original_text text not null,
    normalized_text text not null,
    rating integer,
    source text,
    review_date timestamptz,
    embedding_model text not null,
    embedding_dimension integer not null,
    -- Cosine distance is the project-wide similarity convention (operator <=>).
    embedding vector(768) not null,
    created_at timestamptz not null default timezone('utc'::text, now()),
    updated_at timestamptz not null default timezone('utc'::text, now()),
    constraint review_embeddings_rating_check
        check (rating is null or (rating >= 1 and rating <= 5)),
    -- The stored column is vector(768); keep the declared dimension in sync so
    -- a model/dimension change is always an explicit migration.
    constraint review_embeddings_dimension_check
        check (embedding_dimension = 768)
);

comment on table public.review_embeddings is
    'V2-P2 review embeddings. Similarity uses cosine distance (pgvector <=>); similarity = 1 - distance.';

-- Idempotent upsert target.
create unique index if not exists uq_review_embeddings_fingerprint
    on public.review_embeddings (fingerprint);

-- Metadata filtering support.
create index if not exists idx_review_embeddings_product_id
    on public.review_embeddings (product_id);
create index if not exists idx_review_embeddings_rating
    on public.review_embeddings (rating);
create index if not exists idx_review_embeddings_model_dimension
    on public.review_embeddings (embedding_model, embedding_dimension);

-- Approximate nearest-neighbour index for cosine similarity search.
-- Requires pgvector >= 0.5 (HNSW). Query ORDER BY uses embedding <=> query.
create index if not exists idx_review_embeddings_embedding_hnsw
    on public.review_embeddings using hnsw (embedding vector_cosine_ops);

-- RLS: enabled with NO anon/authenticated policies. Only the backend's
-- service/direct connection (which bypasses RLS) reads or writes embeddings;
-- the frontend public key cannot access this table.
alter table public.review_embeddings enable row level security;
