-- Supabase / Postgres schema for P4 auth (user accounts).
-- Run this ONCE in the Supabase dashboard -> SQL Editor, alongside
-- app/session/supabase_schema.sql.
--
-- user_id is generated in Python (uuid4 hex) rather than a Postgres default, so
-- it's identical whether the app is running against Supabase or the in-memory
-- fallback. It also becomes the session_id once a guest registers/logs in
-- (see SessionStore.merge_guest_into_user), so a user's cart/history/profile end
-- up keyed by the same durable id in the `sessions` table too.

create table if not exists public.users (
    user_id       text primary key,
    email         text unique not null,
    password_hash text not null,
    name          text not null default '',
    phone         text not null default '',
    created_at    timestamptz not null default now()
);

create unique index if not exists users_email_idx on public.users (email);

-- POC only: service_role key, no per-user auth -> disable RLS (see session's schema
-- file for the same note).
alter table public.users disable row level security;
