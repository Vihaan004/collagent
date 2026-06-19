# M3: Networking (People) Surface + Live Directory Lookup — Design

**Status:** Approved (brainstorming complete)
**Date:** 2026-06-18
**Milestone:** M3 (follows M2 events surface + curation pipeline)

## 1. Goal

Add a **People / Networking** curated surface that recommends ASU faculty and research
mentors a student should reach out to — each with a brief, a generated why-note, and a
contact path (email + iSearch profile link) — plus a **"Discuss in chat"** transfer.
The chat agent can both read the curated list (door B) **and** perform live directory
lookups on demand. This milestone also retrofits a live-search chat tool onto the
existing Events feature, generalizing the curation template.

This is the spec's flagship Networking surface, built as a near-verbatim reuse of the
M2 events template. See `2026-06-12-events-surface-curation-design.md` for the shared
architecture and `2026-06-17-poc-m2-events-surface.md` for the reference implementation.

## 2. What's reused vs. new

**Reused verbatim in shape (the M2 "curation-feeds-chat" template):**
Tier-1 ingestion module → shared index table → per-student `curate_*` pipeline →
per-user recommendation table → `GET /api/<surface>` + `POST /api/<surface>/refresh`
→ a curated chat tool (door B) → a surface page with manual Refresh and
"Discuss in chat" transfer via `/chat?ask=...`.

**New in M3:**
1. A new ingestion source: the iSearch faculty/staff JSON API (§3).
2. A **live-search chat tool** capability added to the template — `search_people(query)`
   and a retrofitted `search_events(query)` — so the agent can answer cold/ad-hoc
   questions, not only read curated recommendations.

**Updated template shape (carried forward to future surfaces):**
ingestion → shared index → curate → per-user recs → `GET` + `POST /refresh`
→ **curated read tool + live-search tool** + surface page.

## 3. Data source (verified live, 2026-06-18)

**Endpoint:**
`GET https://search.asu.edu/api/v1/webdir-profiles/faculty-staff?sort-by=&query=<term>&page=<n>&size=<n>&client=asuis`

- Reachable server-to-server (HTTP 200, no auth, no VPN). Confirmed from the backend
  environment. The legacy `asudir-solr.asu.edu` Solr host named in the M2 spec is dead
  (HTTP 000) and is **not** used.
- Response shape:
  ```json
  {
    "meta": { "page": { "current": 1, "total_pages": 43, "total_results": 129, "size": 3 } },
    "results": [
      {
        "asurite_id": { "raw": "ashaik11" },
        "eid": { "raw": "2958771" },
        "display_name": { "raw": "Aashiq Shaikh" },
        "email_address": { "raw": "Aashiq.Shaikh@asu.edu" },
        "primary_title": { "raw": ["VR Programmer"] },
        "departments": { "raw": ["EdPlus at ASU", "Dreamscape Learn"] },
        "expertise_areas": { "raw": ["Computer Engineering", "Computer Science"] },
        "research_interests": { "raw": null },
        "short_bio": { "raw": null },
        "photo_url": { "raw": "https://webapp4.asu.edu/photo-ws/directory_photo/2958771" },
        "simplified_empl_classes": { "raw": ["University Staff"] }
      }
    ]
  }
  ```
- Every field is wrapped in a `{"raw": <value>}` envelope; the parser unwraps it.
- **Profile URL** is derived from `eid`: `https://search.asu.edu/profile/<eid>`.
- **`expertise_areas` is the primary matching signal.** `research_interests` and
  `short_bio` are richer but frequently `null`; `primary_title` + `departments` are
  near-always present.

**Data-quality note:** a free-text `query` matches against job titles too, so results mix
faculty with staff and student-workers, and the rich fields are populated mainly for
actual faculty. Ingestion therefore filters to likely faculty/mentors (§5).

## 4. Schema

`supabase/migrations/0003_people.sql`, applied live via Supabase MCP (project
`collagent`, ref `qepwzwitwjhklxscrugr`). Mirrors the events tables exactly.

**`people`** (shared Tier-1 index, global across students):

| column | type | notes |
|---|---|---|
| `id` | uuid pk | `default gen_random_uuid()` |
| `source` | text | `default 'asu_isearch'` |
| `source_person_key` | text | the `asurite_id` |
| `name` | text not null | `display_name` |
| `email` | text | `email_address` |
| `title` | text | first of `primary_title` |
| `departments` | text[] | `default '{}'` |
| `expertise_areas` | text[] | `default '{}'` |
| `research_interests` | text | nullable |
| `short_bio` | text | nullable |
| `profile_url` | text not null | `https://search.asu.edu/profile/<eid>` |
| `photo_url` | text | nullable |
| `fetched_at` | timestamptz | `default now()` |

`unique(source, source_person_key)`. RLS enabled; policy `"read people"` —
`select using (auth.role() = 'authenticated')`.

**`person_recommendations`** (per-user):

| column | type | notes |
|---|---|---|
| `id` | uuid pk | `default gen_random_uuid()` |
| `user_id` | uuid | fk → `profiles(id)` on delete cascade |
| `person_id` | uuid | fk → `people(id)` on delete cascade |
| `why_note` | text not null | generated |
| `rank` | int not null | |
| `created_at` | timestamptz | `default now()` |

`unique(user_id, person_id)`; index on `(user_id, rank)`. RLS enabled; policy
`"own person recs"` — `all using (auth.uid() = user_id)`.

## 5. Ingestion — `src/collagent/asu/people.py` (Strategy A: profile-seeded)

- `parse_people(payload: dict) -> list[dict]` — **pure function.** Unwraps the `{"raw": …}`
  envelope, maps fields to the `people` column shape, builds `profile_url` from `eid`,
  coerces `departments`/`expertise_areas` to lists (drop `None`/blank entries), and
  **filters to likely faculty/mentors**: keep a row if any of —
  `simplified_empl_classes` contains an entry matching `faculty` (case-insensitive), OR
  `title` contains `professor`/`lecturer`/`faculty` (case-insensitive), OR
  `expertise_areas` is non-empty. Drops rows with no `asurite_id` or no `name`.
  Unit-tested against a captured JSON fixture (no network), like `parse_event_links`.
- `_query_terms(profile, courses) -> list[str]` — derive a small set of query terms from
  the student's interests + major (e.g. interests verbatim plus the major name).
  De-duplicated, capped (e.g. ≤ 6 terms) to bound cost.
- `fetch_faculty(query_terms, per_term=10) -> list[dict]` — for each term, GET the API
  (timeout 15s, browser UA, `Accept: application/json`), `parse_people` the results,
  accumulate. Resilient: wrap each request in `try/except httpx.HTTPError` → skip that
  term; dedupe by `source_person_key` across terms. No LLM, no browser.
- `search_faculty(query, size=8) -> list[dict]` — thin single-query variant used by the
  live chat tool (§7). Same fetch + `parse_people`, returns the parsed rows directly.
- A capture script `scripts/capture_people_fixture.py` saves a real fixture for tests
  (mirrors `capture_events_fixture.py`).

## 6. Curation — `src/collagent/curation/people.py`

Mirrors `curation/events.py`. A pure function with one structured LLM call.

- `RankedPerson(person_id: str, why_note: str)` and `PersonRanking(picks: list[RankedPerson])`.
- `curate_people(user_id)`:
  1. Load the student's profile + courses and the candidate pool via `db.get_people(...)`.
  2. If no candidates → `db.replace_person_recommendations(user_id, [])` and return.
  3. Build a candidate block (id, name, title, departments, expertise_areas, truncated
     bio/research_interests with `(untitled)`/`TBD` fallbacks) and a student summary.
  4. One `get_model().with_structured_output(PersonRanking)` call: "choose the 5–10
     people this student should most consider reaching out to, with a one-sentence,
     specific why-note grounded in their expertise."
  5. Validate: drop picks whose `person_id` is not in the candidate set; assign `rank`
     by pick order; `db.replace_person_recommendations(user_id, rows)` (delete-then-insert).

## 7. Chat tools — `src/collagent/people_tools.py` (+ Events retrofit)

`make_people_tools(user_id)` returns **two** tools:

- `get_person_recommendations` (door B, curated): reads
  `db.get_person_recommendations(user_id)`, renders a multi-line block per person
  (name, title, department, expertise, why-note, email, profile link). Empty case
  returns a "No recommendations yet — visit the People page and Refresh" message.
  Pattern matches `make_event_tools`.
- `search_people` (live): takes a `query` string, calls `people.search_faculty(query)`,
  **upserts the results into the shared `people` index** (`db.upsert_people`), and renders
  the found people inline. Used for ad-hoc/by-name/by-topic questions.

**Events retrofit — `src/collagent/event_tools.py`:** add a `search_events(query)` live
tool alongside the existing `get_event_recommendations`. It calls
`fetch_upcoming_events()` and **filters in-memory** by keyword over title/description/
location (no new endpoint recon), rendering matches inline. (Bounded result count.)

Both surfaces' tools are wired into the chat agent's `extra_tools` in
`api/routes/chat.py` alongside the existing profile and event tools.

## 8. API — `src/collagent/api/routes/people.py`

Router prefix `/api/people`, both endpoints `Depends(get_current_user_id)`:
- `GET ""` → `db.get_person_recommendations(user_id)`, `response_model=list[PersonRecommendation]`.
- `POST "/refresh"` → `db.upsert_people(fetch_faculty(_query_terms(profile, courses)))`
  then `curate_people(user_id)`; returns the refreshed list.

Registered in `api/main.py` via `app.include_router(people.router)`.

`src/collagent/models.py`: add `PersonRecommendation(BaseModel)` with
`model_config = {"extra": "ignore"}` — flattened person fields (`id`, `person_id`, `name`,
`title`, `departments`, `expertise_areas`, `email`, `profile_url`, `photo_url`,
`research_interests`, `short_bio`) plus `why_note` and `rank`.

## 9. Frontend

- `frontend/lib/types.ts`: add `PersonRecommendation` interface mirroring the model.
- `frontend/app/people/page.tsx`: client component; fetch `api.get("/api/people")` on
  mount; loading / empty / list states; cards showing name, title, department, expertise,
  why-note, email (mailto) + profile link (external), and a **"Discuss in chat"** button →
  `router.push("/chat?ask=" + encodeURIComponent("Tell me about " + rec.name + " ..."))`.
  A **Refresh** button → `POST /api/people/refresh`. Mirrors `app/events/page.tsx`.
- `frontend/components/Nav.tsx`: add `{ href: "/people", label: "People" }` to `LINKS`.
- Chat `?ask=` transfer already supported (M2 `app/chat/page.tsx`); no change needed.

## 10. Testing (TDD)

- `parse_people` unit-tested against a captured JSON fixture (no network): envelope
  unwrap, field mapping, `profile_url` from `eid`, faculty filter keeps/drops correctly.
- `curate_people` with a mocked LLM + mocked `db`: hallucinated `person_id`s dropped,
  ranks assigned, replace semantics, empty-candidate short-circuit (no LLM call).
- `db` functions (`upsert_people`, `get_people`, `get_person_recommendations`,
  `replace_person_recommendations`) with the mocked-supabase pattern from `test_db.py`.
- API routes via `TestClient` + dependency override (mock ingest/curate).
- Chat tools (`get_person_recommendations`, `search_people`, retrofitted `search_events`)
  tested like `test_event_tools.py` / `test_profile_tools.py` with mocked db/fetch.
- Final live smoke: real ingest → upsert → curate (real LLM) → DB write → join readback
  for the onboarded test profile; and a live `search_people` call.

## 11. Constraints & non-goals

- **Supabase MCP only** for all DB/migration work (project `collagent`, ref
  `qepwzwitwjhklxscrugr`); ignore the stale "Collagent Database" project. Existing data
  may be overwritten.
- Never touch/commit `.env`/`.env.local`; never print secrets; do not stage the untracked
  `canvas-mcp/` directory.
- **Outreach: contact path only** — surface email + profile link + why-note + transfer.
  No email drafting/sending capability is added (the agent may still advise on outreach
  in general chat).
- Manual refresh only (no scheduler), consistent with Events.
- Single LLM rank-and-explain; no embeddings/pgvector.
- Department/college crawl (Strategy B) and a dedicated profile-page enrichment scrape
  are out of scope.
