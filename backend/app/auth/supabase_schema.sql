-- Supabase / Postgres schema for P4 auth (user accounts).
-- Run this ONCE in the Supabase dashboard -> SQL Editor, alongside
-- app/session/supabase_schema.sql.
--
-- This matches the live `users` table. The app speaks in `user_id`/`name`, but
-- the physical columns are `id` (uuid pk) and `full_name`; the translation lives
-- entirely in SupabaseUserBackend (app/auth/users_store.py). `id` also becomes
-- the session_id once a guest registers/logs in (see
-- SessionStore.merge_guest_into_user), so a user's cart/history/profile end up
-- keyed by that same id in the `sessions` table too.

create table if not exists public.users (
    id            uuid primary key default gen_random_uuid(),
    full_name     text not null default '',
    email         text unique not null,
    password_hash text not null,
    country       text not null default '',
    created_at    timestamptz not null default now()
);

create unique index if not exists users_email_idx on public.users (email);

-- POC only: service_role/secret key, no per-user auth -> disable RLS (see the
-- session schema file for the same note).
alter table public.users disable row level security;
