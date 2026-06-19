-- 0003_people.sql — M3 networking (people) surface
-- Shared people index + per-user recommendations. Mirrors 0002_events.sql.

create table if not exists people (
  id uuid primary key default gen_random_uuid(),
  source text not null default 'asu_isearch',
  source_person_key text not null,
  name text not null,
  email text,
  title text,
  departments text[] not null default '{}',
  expertise_areas text[] not null default '{}',
  research_interests text,
  short_bio text,
  profile_url text not null,
  photo_url text,
  fetched_at timestamptz not null default now(),
  unique (source, source_person_key)
);

create table if not exists person_recommendations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade,
  person_id uuid not null references people(id) on delete cascade,
  why_note text not null,
  rank int not null,
  created_at timestamptz not null default now(),
  unique (user_id, person_id)
);

create index if not exists person_recommendations_user_rank_idx
  on person_recommendations (user_id, rank);

alter table people enable row level security;
alter table person_recommendations enable row level security;

create policy "read people" on people
  for select using (auth.role() = 'authenticated');

create policy "own person recs" on person_recommendations
  for all using (auth.uid() = user_id);
