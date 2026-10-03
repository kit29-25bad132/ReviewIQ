-- =========================================================
-- REVIEWIQ — CANONICAL DATA ARCHITECTURE SCHEMA
-- Database: Supabase PostgreSQL (with pgvector)
-- =========================================================

-- 1. Enable required extensions
create extension if not exists "uuid-ossp";
create extension if not exists vector with schema extensions;

-- =========================================================
-- 2. CANONICAL PRODUCTS TABLE
-- =========================================================
create table if not exists public.products (
    id uuid primary key default gen_random_uuid(),
    source_product_id text not null unique,
    name text not null,
    brand text not null,
    category text not null,
    metadata jsonb not null default '{}'::jsonb,
    source_dataset text not null default 'product_reviews_dataset.csv',
    source_reference text not null,
    created_at timestamptz not null default timezone('utc'::text, now()),
    updated_at timestamptz not null default timezone('utc'::text, now())
);

comment on table public.products is 'Authoritative canonical product registry for ReviewIQ.';

-- Indexes for product lookups
create index if not exists idx_products_source_product_id on public.products (source_product_id);
create index if not exists idx_products_category on public.products (category);
create index if not exists idx_products_brand on public.products (brand);
create index if not exists idx_products_name on public.products (name);

-- =========================================================
-- 3. CANONICAL REVIEWS TABLE
-- =========================================================
create table if not exists public.reviews (
    id uuid primary key default gen_random_uuid(),
    product_id uuid not null references public.products(id) on delete cascade,
    source_product_id text not null,
    source_review_id text not null unique,
    rating integer not null check (rating >= 1 and rating <= 5),
    review_title text,
    review_text text not null,
    review_date text,
    verified_purchase boolean not null default true,
    source_dataset text not null default 'product_reviews_dataset.csv',
    source_reference text not null,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default timezone('utc'::text, now())
);

comment on table public.reviews is 'Authoritative canonical customer reviews for ReviewIQ.';

-- Indexes for reviews
create index if not exists idx_reviews_product_id on public.reviews (product_id);
create index if not exists idx_reviews_source_product_id on public.reviews (source_product_id);
create index if not exists idx_reviews_source_review_id on public.reviews (source_review_id);
create index if not exists idx_reviews_rating on public.reviews (rating);
create index if not exists idx_reviews_product_rating on public.reviews (product_id, rating);

-- =========================================================
-- 4. REVIEW EMBEDDINGS (pgvector)
-- =========================================================
create table if not exists public.review_embeddings (
    id bigint generated always as identity primary key,
    review_id text not null,
    product_id text,
    fingerprint text not null unique,
    original_text text not null,
    normalized_text text not null,
    rating integer check (rating is null or (rating >= 1 and rating <= 5)),
    source text default 'product_reviews_dataset.csv',
    source_dataset text default 'product_reviews_dataset.csv',
    source_reference text,
    review_date timestamptz,
    embedding_model text not null default 'gemini-embedding-001',
    embedding_dimension integer not null default 768 check (embedding_dimension = 768),
    embedding vector(768) not null,
    created_at timestamptz not null default timezone('utc'::text, now()),
    updated_at timestamptz not null default timezone('utc'::text, now())
);

comment on table public.review_embeddings is 'Gemini 768-dimension vector embeddings for semantic review retrieval.';

create index if not exists idx_review_embeddings_product_id on public.review_embeddings (product_id);
create index if not exists idx_review_embeddings_rating on public.review_embeddings (rating);
create index if not exists idx_review_embeddings_embedding_hnsw on public.review_embeddings using hnsw (embedding vector_cosine_ops);

-- =========================================================
-- 5. INGESTION AND QUALITY METADATA TABLES
-- =========================================================
create table if not exists public.data_ingestion_runs (
    id uuid primary key default gen_random_uuid(),
    dataset_name text not null,
    dataset_version text not null,
    source_path text not null,
    started_at timestamptz not null default timezone('utc'::text, now()),
    completed_at timestamptz,
    processed_rows integer not null default 0,
    accepted_rows integer not null default 0,
    rejected_rows integer not null default 0,
    validation_status text not null check (validation_status in ('PENDING', 'VALIDATED', 'FAILED')),
    quality_status text not null check (quality_status in ('PENDING', 'PASSED', 'FAILED')),
    error_details jsonb default '[]'::jsonb,
    metrics jsonb default '{}'::jsonb
);

create table if not exists public.data_quality_reports (
    id uuid primary key default gen_random_uuid(),
    dataset_version text not null,
    ingestion_run_id uuid references public.data_ingestion_runs(id) on delete set null,
    status text not null check (status in ('PASS', 'FAIL')),
    total_rows integer not null,
    total_products integer not null,
    total_reviews integer not null,
    exact_duplicate_count integer not null default 0,
    normalized_duplicate_count integer not null default 0,
    near_duplicate_count integer not null default 0,
    template_repetition_count integer not null default 0,
    missing_values_count integer not null default 0,
    invalid_ratings_count integer not null default 0,
    orphan_reviews_count integer not null default 0,
    provenance_coverage_pct double precision not null default 100.0,
    metrics jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default timezone('utc'::text, now())
);

create table if not exists public.dataset_versions (
    id uuid primary key default gen_random_uuid(),
    version_tag text not null unique,
    dataset_name text not null,
    row_count integer not null,
    product_count integer not null,
    sha256_hash text not null,
    is_active boolean not null default true,
    created_at timestamptz not null default timezone('utc'::text, now())
);

create index if not exists idx_dataset_versions_tag on public.dataset_versions (version_tag);
create index if not exists idx_data_quality_reports_ver on public.data_quality_reports (dataset_version);
