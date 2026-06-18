-- supabase/migrations/0002_events.sql

-- Shared event index: ingested from asuevents.asu.edu, reusable across all students.
create table public.events (
  id uuid primary key default gen_random_uuid(),
  source text not null default 'asu_events',
  source_event_key text not null,          -- dedupe: slug + event date
  title text not null,
  description text,
  starts_at timestamptz,
  ends_at timestamptz,
  location text,
  categories text[] not null default '{}',
  url text not null,
  fetched_at timestamptz not null default now(),
  unique (source, source_event_key)
);
create index events_starts_at_idx on public.events (starts_at);

-- Per-student curated recommendations (the store both doors read).
create table public.event_recommendations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  event_id uuid not null references public.events(id) on delete cascade,
  why_note text not null,
  rank int not null,
  created_at timestamptz not null default now(),
  unique (user_id, event_id)
);
create index event_recs_user_idx on public.event_recommendations (user_id, rank);

alter table public.events enable row level security;
alter table public.event_recommendations enable row level security;

-- Events are shared, non-sensitive: any authenticated user may read.
create policy "read events" on public.events for select using (auth.role() = 'authenticated');
-- Recommendations are per-student.
create policy "own recs" on public.event_recommendations
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
