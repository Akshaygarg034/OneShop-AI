-- Supabase / Postgres schema for P4 session persistence.
-- Run this ONCE in the Supabase dashboard -> SQL Editor.
--
-- One row per shopping session. history/profile/cart are stored as JSONB so the
-- shape stays in sync with contracts/models.py without migrations. The primary key
-- makes the upsert in SupabaseBackend.save() idempotent (retried cart writes can't
-- duplicate).
--
-- NOTE: `history` stores the conversations map (conv_id -> message list), not a
-- flat message array. Session.from_dict() still accepts the old flat-list format.

create table if not exists public.sessions (
    session_id  text primary key,
    history     jsonb       not null default '[]'::jsonb,
    profile     jsonb       not null default '{}'::jsonb,
    cart        jsonb       not null default '{}'::jsonb,
    updated_at  timestamptz not null default now()
);

-- Keep updated_at fresh on every upsert.
create or replace function public.touch_sessions_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

drop trigger if exists trg_touch_sessions on public.sessions;
create trigger trg_touch_sessions
    before update on public.sessions
    for each row execute function public.touch_sessions_updated_at();

-- POC only: we connect with the service_role key and don't use per-user auth,
-- so disable Row Level Security on this table. (In production you'd scope rows to
-- an authenticated customer instead.)
alter table public.sessions disable row level security;
