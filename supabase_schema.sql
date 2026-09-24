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
    pros jsonb not null default '[]'::jsonb,
    cons jsonb not null default '[]'::jsonb,
    summary text not null,
    created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

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
