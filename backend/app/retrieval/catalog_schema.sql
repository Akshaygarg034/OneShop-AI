-- Product catalog in Postgres (Supabase). Run ONCE in the Supabase SQL editor.
--
-- This is the app's slug-keyed catalog (ids like "phone_pixel8"), matching
-- contracts/models.py::Product exactly - deliberately separate from the richer
-- normalized `products`/`plans`/`accessories` tables so the working app, RAG,
-- and eval suite don't have to change. Prices/stock live here (the deterministic
-- source of truth); the semantic text (description/features) is what gets
-- embedded into Qdrant for retrieval.
--
-- Seed it with:  cd backend && python -m app.retrieval.seed_catalog

create table if not exists public.catalog_products (
    id                text primary key,
    type              text not null,
    name              text not null,
    brand             text not null default '',
    description       text not null default '',
    price_monthly     numeric not null default 0,
    price_onetime     numeric not null default 0,
    category          text not null default '',
    features          jsonb not null default '[]'::jsonb,
    compatible_plans  jsonb not null default '[]'::jsonb,
    stock             integer not null default 0,
    in_stock          boolean not null default true,
    image_url         text not null default '',
    updated_at        timestamptz not null default now()
);

-- Safe to re-run: if the table already exists from before image_url was added,
-- this adds the column without touching existing rows/data.
alter table public.catalog_products add column if not exists image_url text not null default '';

-- POC: service key, no per-user auth -> RLS off (same note as the other schemas).
alter table public.catalog_products disable row level security;
