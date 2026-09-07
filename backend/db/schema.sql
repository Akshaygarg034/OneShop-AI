-- Smart Shopping Assistant — Supabase (Postgres) schema. Fully idempotent and
-- non-destructive: tables are created only if missing, and columns added only
-- if missing — existing data is never dropped or modified. The backend runs
-- this on every startup when SUPABASE_DB_URL is set; otherwise run it manually
-- in the Supabase SQL editor.
--
-- Security note: this service accesses these tables exclusively with the
-- service-role key from the backend. Row Level Security is enabled with no
-- policies, which blocks the anon/authenticated keys entirely — never expose
-- these tables to client-side Supabase access.

create table if not exists public.users (
    id             uuid primary key,
    email          text not null unique,
    password_hash  text not null,
    full_name      text not null default '',
    created_at     timestamptz not null default now()
);
alter table public.users add column if not exists phone text not null default '';
-- Google account id ("sub"). Null for password-only accounts; unique when set so
-- one Google identity can never map to two local accounts.
alter table public.users add column if not exists google_sub text;
create unique index if not exists idx_users_google_sub on public.users (google_sub)
    where google_sub is not null;

create table if not exists public.catalog_products (
    id               text primary key,
    type             text not null,
    name             text not null,
    brand            text not null default '',
    description      text not null default '',
    category         text not null default '',
    subcategory      text not null default '',
    price_onetime    numeric not null default 0,
    price_monthly    numeric not null default 0,
    original_price   numeric not null default 0,
    discount_pct     integer not null default 0,
    rating           numeric not null default 0,
    review_count     integer not null default 0,
    colors           jsonb not null default '[]',
    model_year       integer not null default 0,
    warranty_months  integer not null default 0,
    features         jsonb not null default '[]',
    compatible_plans jsonb not null default '[]',
    stock            integer not null default 0,
    in_stock         boolean not null default true,
    image_url        text not null default '',
    popularity       numeric not null default 0.5,
    attributes       jsonb not null default '{}',
    updated_at       timestamptz not null default now()
);
-- Upgrade a pre-existing catalog table in place (columns added by later versions).
alter table public.catalog_products add column if not exists subcategory text not null default '';
alter table public.catalog_products add column if not exists original_price numeric not null default 0;
alter table public.catalog_products add column if not exists discount_pct integer not null default 0;
alter table public.catalog_products add column if not exists rating numeric not null default 0;
alter table public.catalog_products add column if not exists review_count integer not null default 0;
alter table public.catalog_products add column if not exists colors jsonb not null default '[]';
alter table public.catalog_products add column if not exists model_year integer not null default 0;
alter table public.catalog_products add column if not exists warranty_months integer not null default 0;
alter table public.catalog_products add column if not exists popularity numeric not null default 0.5;
alter table public.catalog_products add column if not exists attributes jsonb not null default '{}';

create index if not exists idx_catalog_category on public.catalog_products (category);
create index if not exists idx_catalog_brand on public.catalog_products (brand);
create index if not exists idx_catalog_price on public.catalog_products (price_onetime, price_monthly);
create index if not exists idx_catalog_stock on public.catalog_products (in_stock);

-- One row per session (guest id or user id). Cart lives here; `version`
-- backs optimistic-concurrency writes.
create table if not exists public.sessions (
    session_id  text primary key,
    cart        jsonb not null default '{}',
    version     integer not null default 1,
    updated_at  timestamptz not null default now()
);
-- Upgrade a pre-existing sessions table in place.
alter table public.sessions add column if not exists cart jsonb not null default '{}';
alter table public.sessions add column if not exists version integer not null default 1;

create table if not exists public.user_preferences (
    session_id  text primary key,
    prefs       jsonb not null default '{}',
    updated_at  timestamptz not null default now()
);

create table if not exists public.conversations (
    id                text primary key,
    session_id        text not null,
    title             text not null default '',
    summary           text not null default '',
    summary_upto_seq  integer not null default 0,
    message_count     integer not null default 0,
    created_at        timestamptz not null default now(),
    updated_at        timestamptz not null default now()
);
create index if not exists idx_conversations_session on public.conversations (session_id, updated_at);

create table if not exists public.messages (
    id               bigint generated always as identity primary key,
    conversation_id  text not null references public.conversations (id) on delete cascade,
    session_id       text not null,
    seq              integer not null,
    role             text not null,
    content          text not null,
    recommendations  jsonb not null default '[]',
    created_at       timestamptz not null default now(),
    unique (conversation_id, seq)
);
create index if not exists idx_messages_conversation on public.messages (conversation_id, seq);
create index if not exists idx_messages_session on public.messages (session_id);

create table if not exists public.orders (
    order_id       text primary key,
    session_id     text not null,
    items          jsonb not null default '[]',
    onetime_total  numeric not null default 0,
    monthly_total  numeric not null default 0,
    free_shipping  boolean not null default false,
    status         text not null default 'confirmed',
    created_at     timestamptz not null default now()
);
create index if not exists idx_orders_session on public.orders (session_id);

-- updated_at maintenance
create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin
    new.updated_at = now();
    return new;
end $$;

create or replace trigger touch_sessions before update on public.sessions
    for each row execute function public.touch_updated_at();
create or replace trigger touch_preferences before update on public.user_preferences
    for each row execute function public.touch_updated_at();

-- RLS: enabled, no policies -> service-role key only.
alter table public.catalog_products enable row level security;
alter table public.users enable row level security;
alter table public.sessions enable row level security;
alter table public.user_preferences enable row level security;
alter table public.conversations enable row level security;
alter table public.messages enable row level security;
alter table public.orders enable row level security;
