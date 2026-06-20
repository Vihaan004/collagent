-- 0004_foundation.sql — v2 "Daily Brief" foundation
-- Adds the agent-memory store (wired up in this plan) plus schema-ahead tables
-- for news, the ASU academic calendar, and per-user dashboard snapshots
-- (used by later v2 plans). Mirrors 0002_events.sql / 0003_people.sql.

-- Agent memory: durable, user-owned facts the chat agent curates.
create table if not exists user_memories (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade,
  content text not null,
  kind text not null default 'fact',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists user_memories_user_created_idx
  on user_memories (user_id, created_at);

-- Global open-web news cache (Tavily). No per-user table; per-user tuning lives
-- in dashboard_snapshots.news. (Populated in the News plan.)
create table if not exists news_items (
  id uuid primary key default gen_random_uuid(),
  source text not null default 'tavily',
  source_key text not null,
  title text not null,
  url text not null,
  summary text,
  published_at timestamptz,
  fetched_at timestamptz not null default now(),
  raw jsonb,
  unique (source, source_key)
);

-- ASU academic calendar, current term only. Deterministic ingestion, read-only
-- to the agent. (Populated in the Calendar plan.)
create table if not exists calendar_items (
  id uuid primary key default gen_random_uuid(),
  term text not null,
  session text not null default 'whole',
  title text not null,
  date_start date,
  date_end date,
  category text,
  fetched_at timestamptz not null default now(),
  unique (term, session, title)
);

-- Per-user dashboard snapshot: the agent-written Brief + the lightly-tuned news
-- subset chosen for this student. (Populated in the Orchestrator plan.)
create table if not exists dashboard_snapshots (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade unique,
  brief_md text not null default '',
  news jsonb not null default '[]',
  generated_at timestamptz not null default now()
);

alter table user_memories enable row level security;
alter table news_items enable row level security;
alter table calendar_items enable row level security;
alter table dashboard_snapshots enable row level security;

create policy "own memories" on user_memories
  for all using (auth.uid() = user_id);

create policy "read news" on news_items
  for select using (auth.role() = 'authenticated');

create policy "read calendar" on calendar_items
  for select using (auth.role() = 'authenticated');

create policy "own snapshot" on dashboard_snapshots
  for all using (auth.uid() = user_id);
