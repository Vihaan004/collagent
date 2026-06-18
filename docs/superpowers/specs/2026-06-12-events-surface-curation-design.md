# Collagent PoC Milestone 2: Events Surface + Curation Pipeline — Design

**Date:** 2026-06-12
**Status:** Approved design, ready for implementation planning.
**Companion specs:** `2026-06-09-collagent-vision-design.md` (why), `2026-06-09-collagent-technical-feature-spec.md` (how — §1 curation feeds chat, §4 curation pipeline, §5 Events feature, §5.5 stack).
**Builds on:** `2026-06-10-poc-m1-app-shell-onboarding.md` (M1: app shell, Supabase, auth, onboarding, agent-built major map — complete).

## Goal

Build the first **curated surface** end to end: a background-style workflow that ingests public ASU event data, ranks it against the student's profile with a personalized why-note, and stores the result — then exposes that store through **two doors**: a surface UI page (cards + "Discuss in chat") and an agent tool (the chat agent can read the same recommendations). This proves the spec's "curation feeds chat" pattern (§1) as a **reusable template** that networking/opportunities will later instantiate by swapping the item type.

## Scope decisions (settled during brainstorming)

- **Surface:** Events first (lowest-risk slice; Tier-1 public data; simple matching).
- **Trigger:** **Manual refresh only.** No scheduler/APScheduler in this milestone — the tester explicitly controls when the workflow runs. One button runs the full pipeline (ingest → curate). APScheduler is deferred to a later milestone when there are real users.
- **Matching:** **Single structured-output LLM rank-and-explain.** Ingest the upcoming-events window (~40 rows), pass profile + candidates to one LLM call that returns the top 5–10 with a why-note each. No embeddings / no pgvector at PoC scale (the candidate pool fits in one prompt). The spec defers semantic matching until volume demands it.
- **Transfer-to-chat:** **Prefilled visible message.** "Discuss in chat" navigates to `/chat?ask=<prompt>` and auto-sends a visible message naming the event; the agent uses its `get_event_recommendations` tool to ground the answer. No new SSE/chat protocol — reuses the existing `extra_tools` mechanism.
- **Storage:** **Two tables** — a shared `events` index (ingested once, reusable across students) and per-user `event_recommendations` (the why-notes). Preserves the spec's "build data access once, two callers" two-stage structure rather than collapsing and re-splitting later.

## The reusable pattern

```
 Refresh button ──▶ POST /api/events/refresh
                         │
              ┌──────────┴───────────┐
              │  1. INGEST (shared)   │  httpx fetch listing + detail pages,
              │     → events table    │  parse gcal-link params. No LLM, no Playwright.
              └──────────┬───────────┘
              ┌──────────┴───────────┐
              │  2. CURATE (per-user) │  one structured-output LLM call:
              │  → event_recs table   │  profile + candidate events → top 5–10 + why-note
              └──────────┬───────────┘
                         ▼
        ┌────────────────────────────────────┐
        │  event_recommendations  (the store) │
        └───────┬──────────────────────┬──────┘
         door A │                       │ door B
   GET /api/events                get_event_recommendations  (agent tool)
         │                              │
   Events page (cards +          Chat agent pulls the list itself,
   "Discuss in chat" button)     or answers about one event
```

Networking/opportunities later reuse this exact shape: a Tier-1 ingestion module → shared index table → per-student `curate_*` pipeline → per-user recommendation table → a `GET /api/<surface>` route + a `get_<surface>_recommendations` chat tool + a surface page. Only the item type and the ingestion source change.

## Reconnaissance findings (verified 2026-06-12)

- `https://asuevents.asu.edu/?page=N` — **server-rendered HTML, HTTP 200** with a browser `User-Agent`. Paginated. No Playwright needed.
- Event detail links on the listing: `/event/<slug>?eventDate=YYYY-MM-DD&id=N`.
- Each event **detail page** carries a **Google Calendar render link** whose query params encode the structured event data:
  - `dates=START/END` (e.g. `20260612T090000/20260612T120000`) → start/end datetime
  - `ctz=America/Phoenix` → timezone
  - `text=` → title
  - `details=` → URL-encoded HTML description (unescape + strip tags → plain text)
  - `location=` → location (when present)
- **No per-event `.ics` link** was found, but the gcal render link is an equivalent structured carrier and is parseable purely from query params — so **ingestion needs no LLM**.
- All Tier-1: plain `httpx` + `User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)`, same posture as `asu/programs.py`.

## Database schema

New migration `supabase/migrations/0002_events.sql`, following `0001_init.sql` conventions (RLS defense-in-depth, FK cascade, service-role backend writes).

```sql
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

-- Per-student curated recommendations (the "store" both doors read).
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
```

Notes:
- **Dedupe** on `(source, source_event_key)` — re-ingesting upserts instead of duplicating. The `source` column lets the same table generalize to additional event feeds.
- **Curate = replace**: refreshing a user's recs deletes their rows and re-inserts (mirrors `replace_major_map_courses`).
- **Candidate pool for the LLM**: upcoming events (`starts_at >= now()`), date-ordered, capped (default ~40 / next ~30 days) so the set fits in one prompt.
- `categories` stays `default '{}'` since ASU's per-event category exposure is inconsistent; `description` carries the matching signal.

## Backend modules

### Ingestion — `src/collagent/asu/events.py`
Sibling to `programs.py`/`majormap.py`. Pure Tier-1, no LLM.

```
fetch_upcoming_events(max_events=40) -> list[dict]
  ├─ GET asuevents.asu.edu/?page=0..N            (browser UA, httpx)
  ├─ parse_event_links(html) -> [{slug, url, event_date}]   (regex on /event/<slug>?eventDate=…)
  └─ for each detail page:
       parse_gcal_link(html) -> {title, starts_at, ends_at, description, location}
         (read the Google Calendar render link query params; details=HTML→text)
```

Each row → `{source:'asu_events', source_event_key, title, description, starts_at, ends_at, location, url}`.
`parse_event_links` and `parse_gcal_link` are **pure functions** → unit-testable against an HTML fixture, no network (same approach as `parse_major_links`). A capture script saves a real fixture for tests (mirrors `capture_roadmap_fixture.py`).

### Curation — `src/collagent/curation/events.py`
New `curation/` package (leaves room for networking/opportunities). A pure function with one structured LLM call.

```python
class RankedEvent(BaseModel):
    event_id: str
    why_note: str = Field(description="1–2 sentences on why THIS event fits the student")

class EventRanking(BaseModel):
    picks: list[RankedEvent]  # top 5–10, best first

def curate_events(user_id: str) -> list[EventRecommendation]:
    profile = db.get_profile(user_id)
    courses = db.get_major_map_courses(user_id)        # reuse the major-map signal
    events  = db.get_upcoming_events(limit=40)
    ranking = get_model().with_structured_output(EventRanking).invoke(
        [("system", _RANK_PROMPT),
         ("user", <profile summary + numbered candidate events>)])
    # keep only picks whose event_id is in the candidate set (drop hallucinations)
    rows = [{"event_id": p.event_id, "why_note": p.why_note, "rank": i}
            for i, p in enumerate(validated_picks)]
    return db.replace_event_recommendations(user_id, rows)
```

The prompt reuses `build_system_prompt`-style profile rendering for consistency and instructs: pick 5–10, rank by fit, ground each why-note in the student's actual interests / major / goals.

### `db.py` additions
Same service-role client.
- `upsert_events(rows)` — insert with `on_conflict=(source,source_event_key)`.
- `get_upcoming_events(limit, since=now)` — `starts_at >= since`, ordered, limited.
- `replace_event_recommendations(user_id, rows)` — delete-then-insert (mirrors `replace_major_map_courses`).
- `get_event_recommendations(user_id)` — join recs → events, ordered by `rank`, returns a combined view model.

### Model — `src/collagent/models.py`
Add `EventRecommendation` (event fields + `why_note` + `rank`) so the API route and the chat tool return the same typed shape.

## API routes

`src/collagent/api/routes/events.py`, registered in `api/main.py` alongside the others.

```python
@router.get("", response_model=list[EventRecommendation])      # door A: surface read
def read_events(user_id = Depends(get_current_user_id)):
    return db.get_event_recommendations(user_id)

# Plain def: ingestion does sync httpx fan-out + an LLM call; FastAPI threadpools it.
@router.post("/refresh", response_model=list[EventRecommendation])
def refresh_events(user_id = Depends(get_current_user_id)):
    upsert_events(fetch_upcoming_events())   # 1. ingest shared index
    return curate_events(user_id)            # 2. curate for this user → returns new recs
```

One endpoint runs the full pipeline (~30–60s, like major-map generation); the page shows a loading state. The two-table split still allows separating "re-index" from "re-curate" later if wanted, but one button is the simplest tester action now.

## Chat tool (door B)

New per-user factory `make_event_tools(user_id)` returning one tool:

```python
@tool("get_event_recommendations")
def get_event_recommendations() -> str:
    """Return this student's current curated event recommendations
    (title, date, location, and why each was recommended)."""
    recs = db.get_event_recommendations(user_id)
    return <compact text rendering>  # or "No recommendations yet; suggest the Events page."
```

Wired into the existing chat route by extending `extra_tools`:

```python
extra_tools=tuple(make_profile_tools(user_id)) + tuple(make_event_tools(user_id))
```

When "Discuss in chat" sends *"Tell me about the event: <title>"*, the agent calls this tool, finds the matching rec, and answers grounded in the why-note + details. It can also pull the whole list unprompted ("what events are good for me this week?"). No SSE protocol change.

## Frontend

### New page — `app/events/page.tsx`
Client component, follows `chat`/`profile` conventions.
- On mount: `api.get("/api/events")` → render recommendation cards. Empty state: "No recommendations yet — hit Refresh."
- Card: title, date/time, location, short description snippet, and the **why-note** (visually distinct — the personalized bit). Actions: event `url` (opens ASU page) + **"Discuss in chat."**
- **Refresh** button → `api.post("/api/events/refresh", {})` with a loading state (~30–60s), then re-render with returned recs.

### Transfer-to-chat mechanic
"Discuss in chat" navigates to `/chat?ask=<encoded prompt>`. Small refactor to `chat/page.tsx`:
- Extract the body of `send` into `sendMessage(text: string)` (current `send` becomes a thin form wrapper).
- On mount, read `?ask=` via `useSearchParams`; if present, auto-call `sendMessage(decoded)` once and strip the param. Message shows in the transcript like any user message (transparent behavior).

### Plumbing
- `components/Nav.tsx`: add `{ href: "/events", label: "Events" }` to `LINKS`.
- `lib/types.ts`: add an `EventRecommendation` interface matching the backend model.
- `lib/api.ts`: unchanged (already generic).

> **Next.js note:** `frontend/AGENTS.md` warns this Next.js version has breaking changes from training data. The implementation plan must require reading the relevant `node_modules/next/dist/docs/` guide (esp. `useSearchParams`/Suspense behavior) before writing the page.

## Testing approach

Follows the M1 plan's split:
- **Backend (TDD):** `parse_event_links` and `parse_gcal_link` unit-tested against a captured HTML fixture (no network). `curate_events` tested with a mocked LLM + mocked `db` (verify candidate-set validation drops hallucinated `event_id`s, ranks are assigned, replace semantics). `db` functions tested with the mocked supabase client pattern from `test_db.py`. API routes tested with `TestClient` + dependency override (mock ingest/curate). Chat tool tested like `test_profile_tools.py`.
- **Integration (gated on `OPENAI_API_KEY`):** end-to-end `curate_events` against the real fixture, asserting 5–10 picks with non-empty why-notes and valid event ids.
- **Frontend:** `npm run build` (typecheck + compile) + manual smoke check — the PoC-speed bar from M1.
- **Live smoke:** apply migration to Supabase via MCP, run refresh against the live DB for the test user, confirm recs persist and render, and that "Discuss in chat" round-trips through the agent tool.

## Out of scope (this milestone)

- APScheduler / any scheduled or automatic refresh.
- Embeddings / pgvector / semantic retrieval.
- Networking and Research Opportunities surfaces (this milestone builds the template they will reuse).
- Per-event category taxonomy beyond whatever is cheaply parseable.
- Persisting chat threads (still in-process `MemorySaver`, unchanged from M1).
