-- supabase/migrations/0001_init.sql

-- Profiles: one row per student, auto-created on signup.
create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  full_name text,
  major_name text,
  acad_plan_code text,
  catalog_year text,
  academic_year text check (academic_year in ('freshman','sophomore','junior','senior','graduate')),
  interests text[] not null default '{}',
  goals text,
  clubs text[] not null default '{}',
  projects text,
  onboarded boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Major map: flat course rows per student (terms 1..8).
create table public.major_map_courses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  term_number int not null,
  course_code text,
  title text not null,
  credits numeric,
  requirement_note text,
  status text not null default 'remaining' check (status in ('taken','in_progress','remaining')),
  sort_order int not null default 0,
  created_at timestamptz not null default now()
);
create index major_map_courses_user_idx on public.major_map_courses (user_id);

-- Auto-create a profile row on signup.
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, email) values (new.id, new.email);
  return new;
end;
$$;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- updated_at maintenance.
create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;
create trigger profiles_touch before update on public.profiles
  for each row execute function public.touch_updated_at();

-- RLS: backend uses service role (bypasses RLS); these policies are defense-in-depth
-- and allow future direct frontend reads.
alter table public.profiles enable row level security;
alter table public.major_map_courses enable row level security;

create policy "own profile" on public.profiles
  for all using (auth.uid() = id) with check (auth.uid() = id);
create policy "own courses" on public.major_map_courses
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
