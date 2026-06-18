# Collagent PoC Milestone 2: Events Surface + Curation Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first curated surface end to end — a manual-refresh workflow that ingests public ASU events, LLM-ranks them against the student's profile with a personalized why-note into a per-user store, exposed through a surface page ("Discuss in chat" per card) and a chat agent tool reading the same store.

**Architecture:** A shared `events` index table (ingested from `asuevents.asu.edu` via plain `httpx` + Google-Calendar-link parsing, no LLM/Playwright) and a per-user `event_recommendations` table written by a pure-function curation pipeline (one structured-output LLM call). One `POST /api/events/refresh` runs ingest → curate; `GET /api/events` and a `get_event_recommendations` chat tool are the two read doors. This is the reusable "curation feeds chat" template networking/opportunities will later instantiate.

**Tech Stack:** Python 3.12, FastAPI, LangGraph/LangChain v1, Supabase (Postgres + Auth), httpx, BeautifulSoup, PyJWT, pytest, `uv`; Next.js (App Router, TypeScript), Tailwind, @supabase/ssr.

**Spec:** `docs/superpowers/specs/2026-06-12-events-surface-curation-design.md`

**Working directory note:** Backend commands run from repo root with `uv` (`uv run pytest`, `uv run python ...`). Frontend commands run from `frontend/` (`npm run build`). `PYTHONIOENCODING=utf-8` may be needed for piped CLI runs on Windows.

**Reconnaissance findings (verified 2026-06-12, build on these):**
- `https://asuevents.asu.edu/?page=N` — server-rendered HTML, HTTP 200 with a browser `User-Agent`, paginated. No Playwright.
- Listing event links: `/event/<slug>?eventDate=YYYY-MM-DD&id=N`.
- Each event detail page contains a **Google Calendar render link** whose query params encode the structured data: `dates=START/END` (e.g. `20260620T140000/20260620T160000` or all-day `20260620/20260621`), `ctz` (e.g. `America/Phoenix`), `text` (title), `details` (URL-encoded HTML description), `location`. Parse with `urllib.parse.parse_qs` — `parse_qs` already URL-decodes and turns `+` into spaces.
- No per-event `.ics` link, but the gcal link is an equivalent structured carrier — **ingestion needs no LLM**.
- All requests need `User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)`.

---

### Task 1: Events schema migration

**Files:**
- Create: `supabase/migrations/0002_events.sql`

- [ ] **Step 1: Write the migration SQL**

```sql
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
```

- [ ] **Step 2: Apply the migration to the live project**

Apply via the Supabase MCP `apply_migration` tool (migration name `events`) against the `collagent` project, **or** paste the SQL into Supabase Dashboard → SQL Editor → Run.
Expected: "Success. No rows returned."

- [ ] **Step 3: Verify the tables exist**

Via Supabase MCP `list_tables` (or SQL Editor: `select table_name from information_schema.tables where table_schema='public';`).
Expected: `events` and `event_recommendations` now present alongside `profiles`, `major_map_courses`.

- [ ] **Step 4: Verify no new security advisories**

Via Supabase MCP `get_advisors` (type `security`).
Expected: 0 warnings (RLS is enabled on both new tables).

- [ ] **Step 5: Commit**

```bash
git add supabase/migrations/0002_events.sql
git commit -m "feat: add events + event_recommendations schema (M2)"
```

---

### Task 2: EventRecommendation model

**Files:**
- Modify: `src/collagent/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_models.py`:

```python
def test_event_recommendation_defaults_and_required():
    from collagent.models import EventRecommendation

    rec = EventRecommendation(
        id="r1", event_id="e1", title="Intro to FPGAs", url="https://x/event",
        why_note="Matches your FPGA interest.", rank=0,
    )
    assert rec.description is None and rec.location is None
    assert rec.starts_at is None and rec.rank == 0


def test_event_recommendation_ignores_extra_columns():
    from collagent.models import EventRecommendation

    rec = EventRecommendation(
        id="r1", event_id="e1", title="X", url="u", why_note="w", rank=1,
        created_at="2026-06-12T00:00:00Z",
    )
    assert rec.id == "r1"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_models.py -k event_recommendation -v`
Expected: FAIL with `ImportError: cannot import name 'EventRecommendation'`

- [ ] **Step 3: Implement the model**

Append to `src/collagent/models.py`:

```python
class EventRecommendation(BaseModel):
    """Flattened view of an event_recommendations row joined to its event."""

    model_config = {"extra": "ignore"}

    id: str            # recommendation row id
    event_id: str
    title: str
    description: str | None = None
    starts_at: str | None = None
    ends_at: str | None = None
    location: str | None = None
    url: str
    why_note: str
    rank: int
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_models.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add src/collagent/models.py tests/test_models.py
git commit -m "feat: add EventRecommendation model"
```

---

### Task 3: Ingestion parsers (pure functions)

**Files:**
- Create: `src/collagent/asu/events.py`
- Test: `tests/test_events_parse.py`

- [ ] **Step 1: Write failing parser tests**

```python
# tests/test_events_parse.py
from collagent.asu import events

LISTING_SNIPPET = """
<html><body>
<a href="/event/intro-to-fpgas?eventDate=2026-06-20&id=3">Intro to FPGAs</a>
<a href="/event/intro-to-fpgas?eventDate=2026-06-20&id=3">Intro to FPGAs (dup)</a>
<a href="/event/career-fair?eventDate=2026-06-22&id=0">Career Fair</a>
<a href="/about">Not an event</a>
</body></html>
"""

DETAIL_SNIPPET = """
<html><body>
<a href="https://calendar.google.com/calendar/render?action=TEMPLATE&dates=20260620T140000/20260620T160000&ctz=America/Phoenix&text=Intro+to+FPGAs&details=%3Cp%3ELearn+about+FPGAs%3C%2Fp%3E&location=Tempe+Campus">Add to Google Calendar</a>
</body></html>
"""

ALLDAY_SNIPPET = """
<a href="https://calendar.google.com/calendar/render?dates=20260620/20260621&text=Art+Show">x</a>
"""


def test_parse_event_links_dedupes_and_filters():
    result = events.parse_event_links(LISTING_SNIPPET)
    keys = {(p["slug"], p["event_date"]) for p in result}
    assert ("intro-to-fpgas", "2026-06-20") in keys
    assert ("career-fair", "2026-06-22") in keys
    assert len(result) == 2  # dup collapsed, /about ignored
    assert result[0]["url"] == "https://asuevents.asu.edu/event/intro-to-fpgas?eventDate=2026-06-20&id=3"


def test_parse_gcal_link_extracts_fields():
    g = events.parse_gcal_link(DETAIL_SNIPPET)
    assert g["title"] == "Intro to FPGAs"
    assert g["starts_at"] == "2026-06-20T14:00:00-07:00"
    assert g["ends_at"] == "2026-06-20T16:00:00-07:00"
    assert g["description"] == "Learn about FPGAs"
    assert g["location"] == "Tempe Campus"


def test_parse_gcal_link_handles_all_day():
    g = events.parse_gcal_link(ALLDAY_SNIPPET)
    assert g["title"] == "Art Show"
    assert g["starts_at"] == "2026-06-20T00:00:00-07:00"
    assert g["ends_at"] == "2026-06-21T00:00:00-07:00"


def test_parse_gcal_link_missing_returns_empty():
    assert events.parse_gcal_link("<html><body>no link</body></html>") == {}
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_events_parse.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'collagent.asu.events'`

- [ ] **Step 3: Implement the parsers**

```python
# src/collagent/asu/events.py
import re
from datetime import datetime
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

BASE = "https://asuevents.asu.edu"
LIST_URL = BASE + "/?page={page}"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
_EVENT_HREF = re.compile(r"^/event/([a-z0-9-]+)\?eventDate=(\d{4}-\d{2}-\d{2})")
_GCAL_HREF = re.compile(r"calendar\.google\.com/calendar/render")


def parse_event_links(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    found: dict[tuple[str, str], dict] = {}
    for a in soup.find_all("a", href=True):
        m = _EVENT_HREF.match(a["href"])
        if not m:
            continue
        slug, date = m.groups()
        key = (slug, date)
        if key not in found:
            found[key] = {"slug": slug, "event_date": date, "url": BASE + a["href"]}
    return list(found.values())


def _parse_gcal_dt(value: str, tz: ZoneInfo) -> str:
    fmt = "%Y%m%dT%H%M%S" if "T" in value else "%Y%m%d"
    return datetime.strptime(value, fmt).replace(tzinfo=tz).isoformat()


def parse_gcal_link(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    a = soup.find("a", href=_GCAL_HREF)
    if not a:
        return {}
    q = parse_qs(urlparse(a["href"]).query)  # parse_qs URL-decodes and maps + -> space
    tz = ZoneInfo((q.get("ctz") or ["America/Phoenix"])[0])
    starts_at = ends_at = None
    if q.get("dates"):
        parts = q["dates"][0].split("/")
        starts_at = _parse_gcal_dt(parts[0], tz)
        if len(parts) > 1:
            ends_at = _parse_gcal_dt(parts[1], tz)
    details_html = (q.get("details") or [""])[0]
    description = BeautifulSoup(details_html, "html.parser").get_text(" ", strip=True) or None
    return {
        "title": (q.get("text") or [None])[0],
        "starts_at": starts_at,
        "ends_at": ends_at,
        "description": description,
        "location": (q.get("location") or [None])[0],
    }
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_events_parse.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/collagent/asu/events.py tests/test_events_parse.py
git commit -m "feat: ASU events listing + gcal-link parsers"
```

---

### Task 4: Ingestion fetch + capture script

**Files:**
- Modify: `src/collagent/asu/events.py`
- Create: `scripts/capture_events_fixture.py`

- [ ] **Step 1: Implement `fetch_upcoming_events`**

Append to `src/collagent/asu/events.py`:

```python
def fetch_upcoming_events(max_events: int = 40) -> list[dict]:
    """Crawl listing pages, then fetch each detail page and parse its gcal link.
    Network-bound; pure parsing logic lives in parse_event_links/parse_gcal_link."""
    rows: list[dict] = []
    seen: set[str] = set()
    with httpx.Client(headers=UA, timeout=30, follow_redirects=True) as client:
        links: list[dict] = []
        for page in range(0, 5):
            resp = client.get(LIST_URL.format(page=page))
            if resp.status_code != 200:
                break
            page_links = parse_event_links(resp.text)
            if not page_links:
                break
            links.extend(page_links)
            if len(links) >= max_events:
                break
        for link in links[:max_events]:
            key = f"{link['slug']}:{link['event_date']}"
            if key in seen:
                continue
            seen.add(key)
            detail = client.get(link["url"])
            if detail.status_code != 200:
                continue
            g = parse_gcal_link(detail.text)
            if not g.get("title"):
                continue
            rows.append({
                "source": "asu_events",
                "source_event_key": key,
                "title": g["title"],
                "description": g.get("description"),
                "starts_at": g.get("starts_at"),
                "ends_at": g.get("ends_at"),
                "location": g.get("location"),
                "url": link["url"],
            })
    return rows
```

- [ ] **Step 2: Write the capture script**

```python
# scripts/capture_events_fixture.py
"""Smoke-capture: fetch a real events window and print a summary. Network required.
Run manually to verify ingestion works against the live site."""
from collagent.asu.events import fetch_upcoming_events

if __name__ == "__main__":
    rows = fetch_upcoming_events(max_events=10)
    print(f"fetched {len(rows)} events")
    for r in rows[:5]:
        print(f"  - {r['title']} @ {r['starts_at']} ({r['location']})")
```

- [ ] **Step 3: Run the capture script to verify ingestion (network)**

Run: `PYTHONIOENCODING=utf-8 uv run python scripts/capture_events_fixture.py`
Expected: `fetched N events` with N between 1 and 10, and titles/dates printed.
**If N is 0:** the listing markup changed — re-inspect an `/event/...` detail page for the `calendar.google.com/calendar/render` link and adjust `parse_gcal_link`; re-inspect a listing page for the `/event/<slug>?eventDate=` href shape and adjust `_EVENT_HREF`. Keep the Task 3 unit snippets in sync with reality.

- [ ] **Step 4: Commit**

```bash
git add src/collagent/asu/events.py scripts/capture_events_fixture.py
git commit -m "feat: fetch_upcoming_events ingestion + capture script"
```

---

### Task 5: DB repository functions

**Files:**
- Modify: `src/collagent/db.py`
- Test: `tests/test_db_events.py`

- [ ] **Step 1: Write failing db tests**

```python
# tests/test_db_events.py
from unittest.mock import MagicMock

from collagent import db

REC_ROW = {
    "id": "r1", "event_id": "e1", "why_note": "fits you", "rank": 0,
    "events": {
        "title": "Intro to FPGAs", "description": "Learn FPGAs",
        "starts_at": "2026-06-20T14:00:00-07:00", "ends_at": None,
        "location": "Tempe", "url": "https://asuevents.asu.edu/event/intro-to-fpgas",
    },
}


def _client():
    client = MagicMock()
    client.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "e1"}]
    client.table.return_value.select.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value.data = [{"id": "e1", "title": "X"}]
    client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [REC_ROW]
    client.table.return_value.delete.return_value.eq.return_value.execute.return_value.data = []
    client.table.return_value.insert.return_value.execute.return_value.data = [{"id": "r1"}]
    return client


def test_upsert_events_uses_conflict_target(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    db.upsert_events([{"source": "asu_events", "source_event_key": "k", "title": "X", "url": "u"}])
    _, kwargs = client.table.return_value.upsert.call_args
    assert kwargs.get("on_conflict") == "source,source_event_key"


def test_get_upcoming_events_filters_future(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    rows = db.get_upcoming_events(limit=5)
    assert rows == [{"id": "e1", "title": "X"}]
    client.table.return_value.select.return_value.gte.assert_called_once()


def test_get_event_recommendations_flattens_join(monkeypatch):
    monkeypatch.setattr(db, "get_client", lambda: _client())
    recs = db.get_event_recommendations("u1")
    assert len(recs) == 1
    assert recs[0].title == "Intro to FPGAs"
    assert recs[0].why_note == "fits you"
    assert recs[0].event_id == "e1" and recs[0].rank == 0


def test_replace_event_recommendations_deletes_then_inserts(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    db.replace_event_recommendations("u1", [{"event_id": "e1", "why_note": "w", "rank": 0}])
    client.table.return_value.delete.assert_called_once()
    inserted = client.table.return_value.insert.call_args.args[0]
    assert inserted[0]["user_id"] == "u1" and inserted[0]["event_id"] == "e1"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_db_events.py -v`
Expected: FAIL with `AttributeError: module 'collagent.db' has no attribute 'upsert_events'`

- [ ] **Step 3: Implement the functions**

Add to the imports at the top of `src/collagent/db.py`:

```python
from datetime import datetime, timezone
```

Update the model import line in `src/collagent/db.py` to include the new model:

```python
from collagent.models import (
    CourseStatus,
    EventRecommendation,
    MajorMapCourse,
    Profile,
    ProfileUpdate,
)
```

Append to `src/collagent/db.py`:

```python
def upsert_events(rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    res = (
        get_client().table("events")
        .upsert(rows, on_conflict="source,source_event_key")
        .execute()
    )
    return res.data


def get_upcoming_events(limit: int = 40, since: str | None = None) -> list[dict]:
    since = since or datetime.now(timezone.utc).isoformat()
    res = (
        get_client().table("events").select("*")
        .gte("starts_at", since)
        .order("starts_at")
        .limit(limit)
        .execute()
    )
    return res.data


def _flatten_rec(row: dict) -> EventRecommendation:
    ev = row.get("events") or {}
    return EventRecommendation(
        id=row["id"],
        event_id=row["event_id"],
        why_note=row["why_note"],
        rank=row["rank"],
        title=ev.get("title", ""),
        description=ev.get("description"),
        starts_at=ev.get("starts_at"),
        ends_at=ev.get("ends_at"),
        location=ev.get("location"),
        url=ev.get("url", ""),
    )


def get_event_recommendations(user_id: str) -> list[EventRecommendation]:
    res = (
        get_client().table("event_recommendations")
        .select("id, event_id, why_note, rank, events(*)")
        .eq("user_id", user_id)
        .order("rank")
        .execute()
    )
    return [_flatten_rec(row) for row in res.data]


def replace_event_recommendations(
    user_id: str, rows: list[dict]
) -> list[EventRecommendation]:
    client = get_client()
    client.table("event_recommendations").delete().eq("user_id", user_id).execute()
    if rows:
        payload = [{**r, "user_id": user_id} for r in rows]
        client.table("event_recommendations").insert(payload).execute()
    return get_event_recommendations(user_id)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_db_events.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the full suite (no regressions)**

Run: `uv run pytest -v`
Expected: PASS (all)

- [ ] **Step 6: Commit**

```bash
git add src/collagent/db.py tests/test_db_events.py
git commit -m "feat: events + recommendations repository functions"
```

---

### Task 6: Curation pipeline

**Files:**
- Create: `src/collagent/curation/__init__.py` (empty)
- Create: `src/collagent/curation/events.py`
- Test: `tests/test_curation_events.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_curation_events.py
from collagent.curation import events as curation
from collagent.curation.events import EventRanking, RankedEvent
from collagent.models import Profile


def test_curate_drops_hallucinated_ids_and_reranks(monkeypatch):
    profile = Profile(id="u1", email="a@asu.edu", interests=["FPGAs"])
    monkeypatch.setattr(curation.db, "get_profile", lambda uid: profile)
    monkeypatch.setattr(curation.db, "get_major_map_courses", lambda uid: [])
    monkeypatch.setattr(
        curation.db, "get_upcoming_events",
        lambda limit=40: [{"id": "e1", "title": "FPGA Talk"}, {"id": "e2", "title": "Yoga"}],
    )
    # LLM returns a hallucinated id ("e9") and a valid one; e9 must be dropped.
    monkeypatch.setattr(
        curation, "_rank",
        lambda profile, courses, evs: EventRanking(picks=[
            RankedEvent(event_id="e9", why_note="ghost"),
            RankedEvent(event_id="e1", why_note="matches FPGAs"),
        ]),
    )
    captured = {}
    monkeypatch.setattr(
        curation.db, "replace_event_recommendations",
        lambda uid, rows: captured.setdefault("rows", rows) or [],
    )
    curation.curate_events("u1")
    assert captured["rows"] == [{"event_id": "e1", "why_note": "matches FPGAs", "rank": 0}]


def test_curate_with_no_events_clears_recs(monkeypatch):
    monkeypatch.setattr(curation.db, "get_profile", lambda uid: None)
    monkeypatch.setattr(curation.db, "get_major_map_courses", lambda uid: [])
    monkeypatch.setattr(curation.db, "get_upcoming_events", lambda limit=40: [])
    captured = {}
    monkeypatch.setattr(
        curation.db, "replace_event_recommendations",
        lambda uid, rows: captured.setdefault("rows", rows) or [],
    )
    curation.curate_events("u1")
    assert captured["rows"] == []
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_curation_events.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'collagent.curation'`

- [ ] **Step 3: Create the package marker**

Create `src/collagent/curation/__init__.py` (empty file).

- [ ] **Step 4: Implement the pipeline**

```python
# src/collagent/curation/events.py
"""Per-student events curation: profile + candidate events -> ranked recs with why-notes.
A pure function with one structured-output LLM call (spec: 'pipeline, not agent')."""
from pydantic import BaseModel, Field

from collagent import db
from collagent.graph import get_model
from collagent.models import EventRecommendation, MajorMapCourse, Profile


class RankedEvent(BaseModel):
    event_id: str = Field(description="Exact event_id of a candidate, copied verbatim")
    why_note: str = Field(description="1-2 sentences on why THIS event fits the student")


class EventRanking(BaseModel):
    picks: list[RankedEvent] = Field(description="Top 5-10 events, best first")


_RANK_PROMPT = """You are an executive assistant curating ASU campus events for one student.
From the numbered candidate events, choose the 5-10 that best fit this student and rank them
best-first. For each pick, write a 1-2 sentence why_note grounded in the student's specific
interests, major, goals, clubs, or coursework — not generic praise.
Only choose from the candidates and copy each event_id exactly. Do not invent events."""


def _student_summary(profile: Profile | None, courses: list[MajorMapCourse]) -> str:
    if profile is None:
        return "No profile on file; recommend broadly appealing, high-signal events."
    parts: list[str] = []
    if profile.full_name:
        parts.append(f"Name: {profile.full_name}")
    if profile.major_name:
        parts.append(f"Major: {profile.major_name}")
    if profile.academic_year:
        parts.append(f"Year: {profile.academic_year}")
    if profile.interests:
        parts.append(f"Interests: {', '.join(profile.interests)}")
    if profile.goals:
        parts.append(f"Goals: {profile.goals}")
    if profile.clubs:
        parts.append(f"Clubs: {', '.join(profile.clubs)}")
    if profile.projects:
        parts.append(f"Projects: {profile.projects}")
    if courses:
        taken = sum(1 for c in courses if c.status == "taken")
        parts.append(f"Major-map progress: {taken} of {len(courses)} courses taken")
    return "\n".join(parts) or "Profile is sparse; recommend broadly relevant events."


def _candidate_block(events: list[dict]) -> str:
    blocks = []
    for e in events:
        about = (e.get("description") or "")[:300]
        blocks.append(
            f"event_id: {e['id']}\n"
            f"Title: {e.get('title')}\n"
            f"When: {e.get('starts_at')}\n"
            f"Where: {e.get('location')}\n"
            f"About: {about}"
        )
    return "\n\n".join(blocks)


def _rank(
    profile: Profile | None, courses: list[MajorMapCourse], events: list[dict]
) -> EventRanking:
    llm = get_model().with_structured_output(EventRanking)
    user = (
        f"STUDENT:\n{_student_summary(profile, courses)}\n\n"
        f"CANDIDATE EVENTS:\n{_candidate_block(events)}"
    )
    return llm.invoke([("system", _RANK_PROMPT), ("user", user)])


def curate_events(user_id: str) -> list[EventRecommendation]:
    profile = db.get_profile(user_id)
    courses = db.get_major_map_courses(user_id)
    events = db.get_upcoming_events(limit=40)
    if not events:
        return db.replace_event_recommendations(user_id, [])

    ranking = _rank(profile, courses, events)
    valid_ids = {e["id"] for e in events}
    rows: list[dict] = []
    seen: set[str] = set()
    for pick in ranking.picks:
        if pick.event_id in valid_ids and pick.event_id not in seen:
            rows.append(
                {"event_id": pick.event_id, "why_note": pick.why_note, "rank": len(rows)}
            )
            seen.add(pick.event_id)
    return db.replace_event_recommendations(user_id, rows)
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/test_curation_events.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add src/collagent/curation/ tests/test_curation_events.py
git commit -m "feat: per-student events curation pipeline"
```

---

### Task 7: Events API routes

**Files:**
- Create: `src/collagent/api/routes/events.py`
- Modify: `src/collagent/api/main.py`
- Test: `tests/test_api_events.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_api_events.py
from collagent.api.routes import events as ev_routes
from collagent.models import EventRecommendation
from tests.conftest import TEST_USER

REC = EventRecommendation(
    id="r1", event_id="e1", title="Intro to FPGAs",
    url="https://asuevents.asu.edu/event/intro-to-fpgas",
    why_note="Matches your FPGA interest.", rank=0,
)


def test_get_events(client, monkeypatch):
    monkeypatch.setattr(ev_routes.db, "get_event_recommendations", lambda uid: [REC])
    res = client.get("/api/events")
    assert res.status_code == 200
    assert res.json()[0]["title"] == "Intro to FPGAs"
    assert res.json()[0]["why_note"] == "Matches your FPGA interest."


def test_refresh_events_ingests_then_curates(client, monkeypatch):
    calls = []
    monkeypatch.setattr(ev_routes, "fetch_upcoming_events", lambda: calls.append("fetch") or [{"x": 1}])
    monkeypatch.setattr(ev_routes.db, "upsert_events", lambda rows: calls.append("upsert"))
    monkeypatch.setattr(ev_routes, "curate_events", lambda uid: calls.append("curate") or [REC])
    res = client.post("/api/events/refresh", json={})
    assert res.status_code == 200
    assert calls == ["fetch", "upsert", "curate"]  # ingest before curate
    assert res.json()[0]["event_id"] == "e1"


def test_events_unauthenticated_401():
    from fastapi.testclient import TestClient

    from collagent.api.main import app

    assert TestClient(app).get("/api/events").status_code == 401
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_api_events.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'collagent.api.routes.events'`

- [ ] **Step 3: Implement the routes**

```python
# src/collagent/api/routes/events.py
from fastapi import APIRouter, Depends

from collagent import db
from collagent.api.auth import get_current_user_id
from collagent.asu.events import fetch_upcoming_events
from collagent.curation.events import curate_events
from collagent.models import EventRecommendation

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", response_model=list[EventRecommendation])
def read_events(user_id: str = Depends(get_current_user_id)):
    return db.get_event_recommendations(user_id)


# Plain def: ingestion does sync httpx fan-out + an LLM call; FastAPI threadpools it.
@router.post("/refresh", response_model=list[EventRecommendation])
def refresh_events(user_id: str = Depends(get_current_user_id)):
    db.upsert_events(fetch_upcoming_events())
    return curate_events(user_id)
```

- [ ] **Step 4: Register the router**

In `src/collagent/api/main.py`, update the routes import line and add the include. The import becomes:

```python
from collagent.api.routes import chat, events, majormap, profile, programs
```

And add after `app.include_router(chat.router)`:

```python
app.include_router(events.router)
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/test_api_events.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest -v`
Expected: PASS (all)

- [ ] **Step 7: Commit**

```bash
git add src/collagent/api/routes/events.py src/collagent/api/main.py tests/test_api_events.py
git commit -m "feat: events read + refresh API routes"
```

---

### Task 8: Chat tool (door B)

**Files:**
- Create: `src/collagent/event_tools.py`
- Modify: `src/collagent/api/routes/chat.py:35-39`
- Test: `tests/test_event_tools.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_event_tools.py
from collagent import event_tools
from collagent.models import EventRecommendation

REC = EventRecommendation(
    id="r1", event_id="e1", title="Intro to FPGAs", url="u",
    starts_at="2026-06-20T14:00:00-07:00", location="Tempe",
    why_note="Matches your FPGA interest.", rank=0,
)


def test_get_event_recommendations_renders_list(monkeypatch):
    monkeypatch.setattr(event_tools.db, "get_event_recommendations", lambda uid: [REC])
    tools = {t.name: t for t in event_tools.make_event_tools("u1")}
    out = tools["get_event_recommendations"].invoke({})
    assert "Intro to FPGAs" in out
    assert "Matches your FPGA interest." in out
    assert "Tempe" in out


def test_get_event_recommendations_empty(monkeypatch):
    monkeypatch.setattr(event_tools.db, "get_event_recommendations", lambda uid: [])
    tools = {t.name: t for t in event_tools.make_event_tools("u1")}
    out = tools["get_event_recommendations"].invoke({})
    assert "no event recommendations" in out.lower()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_event_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'collagent.event_tools'`

- [ ] **Step 3: Implement the tool factory**

```python
# src/collagent/event_tools.py
"""Per-user tool: the chat agent reads the same curated event store the surface renders."""
from langchain.tools import tool

from collagent import db


def make_event_tools(user_id: str) -> list:
    @tool("get_event_recommendations")
    def get_event_recommendations() -> str:
        """Return this student's current curated event recommendations
        (title, date, location, and why each was recommended)."""
        recs = db.get_event_recommendations(user_id)
        if not recs:
            return (
                "No event recommendations yet. Suggest the student open the Events "
                "page and click Refresh to generate them."
            )
        lines = []
        for r in recs:
            when = r.starts_at or "TBD"
            where = f", {r.location}" if r.location else ""
            lines.append(f"- {r.title} ({when}{where}): {r.why_note}")
        return "\n".join(lines)

    return [get_event_recommendations]
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_event_tools.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Wire the tool into the chat route**

In `src/collagent/api/routes/chat.py`, add to the imports:

```python
from collagent.event_tools import make_event_tools
```

Then change the `extra_tools` argument in the `create_graph(...)` call (currently `extra_tools=tuple(make_profile_tools(user_id)),`) to:

```python
        extra_tools=tuple(make_profile_tools(user_id)) + tuple(make_event_tools(user_id)),
```

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest -v`
Expected: PASS (all)

- [ ] **Step 7: Commit**

```bash
git add src/collagent/event_tools.py src/collagent/api/routes/chat.py tests/test_event_tools.py
git commit -m "feat: get_event_recommendations chat tool wired into chat route"
```

---

### Task 9: Frontend — types, Events page, nav link

**Files:**
- Modify: `frontend/lib/types.ts`
- Create: `frontend/app/events/page.tsx`
- Modify: `frontend/components/Nav.tsx:6-10`

- [ ] **Step 1: Add the EventRecommendation type**

Append to `frontend/lib/types.ts`:

```typescript
export interface EventRecommendation {
  id: string;
  event_id: string;
  title: string;
  description: string | null;
  starts_at: string | null;
  ends_at: string | null;
  location: string | null;
  url: string;
  why_note: string;
  rank: number;
}
```

- [ ] **Step 2: Add the Events nav link**

In `frontend/components/Nav.tsx`, change the `LINKS` array to include Events:

```typescript
const LINKS = [
  { href: "/", label: "Home" },
  { href: "/chat", label: "Chat" },
  { href: "/events", label: "Events" },
  { href: "/profile", label: "Profile" },
];
```

- [ ] **Step 3: Create the Events page**

```tsx
// frontend/app/events/page.tsx
"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { EventRecommendation } from "@/lib/types";

function formatWhen(iso: string | null): string {
  if (!iso) return "Date TBD";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });
}

export default function EventsPage() {
  const router = useRouter();
  const [recs, setRecs] = useState<EventRecommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    api.get("/api/events")
      .then(setRecs)
      .catch(() => setRecs([]))
      .finally(() => setLoading(false));
  }, []);

  async function refresh() {
    setRefreshing(true);
    try {
      setRecs(await api.post("/api/events/refresh", {}));
    } catch {
      // surface a minimal error; keep existing recs
    } finally {
      setRefreshing(false);
    }
  }

  function discuss(rec: EventRecommendation) {
    const ask = `Tell me about the event: ${rec.title}`;
    router.push(`/chat?ask=${encodeURIComponent(ask)}`);
  }

  return (
    <main className="mx-auto w-full max-w-2xl p-4">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold">Events for you</h1>
        <button onClick={refresh} disabled={refreshing}
          className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
          {refreshing ? "Finding events…" : "Refresh"}
        </button>
      </div>

      {loading ? (
        <p className="pt-12 text-center text-sm text-gray-400">Loading…</p>
      ) : recs.length === 0 ? (
        <p className="pt-12 text-center text-sm text-gray-400">
          No recommendations yet — hit Refresh to generate them.
        </p>
      ) : (
        <ul className="space-y-3">
          {recs.map((rec) => (
            <li key={rec.id} className="rounded-lg border p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <a href={rec.url} target="_blank" rel="noopener noreferrer"
                    className="font-medium hover:underline">
                    {rec.title}
                  </a>
                  <p className="text-xs text-gray-500">
                    {formatWhen(rec.starts_at)}{rec.location ? ` · ${rec.location}` : ""}
                  </p>
                </div>
                <button onClick={() => discuss(rec)}
                  className="shrink-0 rounded-md border px-3 py-1 text-xs font-medium hover:bg-gray-50">
                  Discuss in chat
                </button>
              </div>
              <p className="mt-2 rounded bg-gray-50 px-3 py-2 text-sm text-gray-700">
                {rec.why_note}
              </p>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
```

- [ ] **Step 4: Typecheck/build**

Run (from `frontend/`): `npm run build`
Expected: compiles with no type errors. (The chat `?ask=` wiring is Task 10; the Events page itself builds independently.)

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/types.ts frontend/app/events/page.tsx frontend/components/Nav.tsx
git commit -m "feat: events surface page + nav link"
```

---

### Task 10: Frontend — chat auto-send from `?ask=`

**Files:**
- Modify: `frontend/app/chat/page.tsx`

- [ ] **Step 1: Read the Next.js docs for useSearchParams**

This Next.js version has breaking changes from training data (`frontend/AGENTS.md`). Before editing, read the relevant guide under `frontend/node_modules/next/dist/docs/` for `useSearchParams` (it must be inside a `<Suspense>` boundary or the build fails). Confirm the Suspense requirement and the correct import path before writing code.

- [ ] **Step 2: Refactor chat to extract `sendMessage` and auto-send from the query param**

Replace the entire contents of `frontend/app/chat/page.tsx` with:

```tsx
"use client";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { apiFetch } from "@/lib/api";

interface Msg {
  role: "user" | "assistant" | "tool";
  content: string;
}

function ChatInner() {
  const searchParams = useSearchParams();
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const busyRef = useRef(false);

  const sendMessage = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setMessages((m) => [...m, { role: "user", content: trimmed }, { role: "assistant", content: "" }]);

    try {
      const res = await apiFetch("/api/chat", {
        method: "POST",
        body: JSON.stringify({ message: trimmed, thread_id: "web" }),
      });
      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const event = JSON.parse(line.slice(6));
          if (event.type === "token") {
            setMessages((m) => {
              const copy = [...m];
              copy[copy.length - 1] = {
                role: "assistant",
                content: copy[copy.length - 1].content + event.content,
              };
              return copy;
            });
          } else if (event.type === "tool") {
            setMessages((m) => [
              ...m.slice(0, -1),
              { role: "tool", content: `Using ${event.name}…` },
              m[m.length - 1],
            ]);
          } else if (event.type === "error") {
            setMessages((m) => [...m, { role: "assistant", content: "Something went wrong — try again." }]);
          }
          bottomRef.current?.scrollIntoView({ behavior: "smooth" });
        }
      }
    } catch {
      setMessages((m) => [...m, { role: "assistant", content: "Something went wrong — try again." }]);
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }, []);

  // Auto-send a prefilled question transferred from another surface (e.g. an event card).
  useEffect(() => {
    const ask = searchParams.get("ask");
    if (ask) {
      sendMessage(ask);
      window.history.replaceState(null, "", "/chat");
    }
  }, [searchParams, sendMessage]);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const text = input;
    setInput("");
    void sendMessage(text);
  }

  return (
    <main className="mx-auto flex h-[calc(100vh-57px)] w-full max-w-2xl flex-col p-4">
      <div className="flex-1 space-y-3 overflow-y-auto pb-4">
        {messages.length === 0 && (
          <p className="pt-12 text-center text-sm text-gray-400">
            Ask me anything about your classes, ASU, or your degree plan.
          </p>
        )}
        {messages.map((m, i) =>
          m.role === "tool" ? (
            <p key={i} className="text-center text-xs text-gray-400">{m.content}</p>
          ) : (
            <div key={i}
              className={`max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm ${
                m.role === "user" ? "ml-auto bg-black text-white" : "bg-gray-100"
              }`}>
              {m.content || "…"}
            </div>
          )
        )}
        <div ref={bottomRef} />
      </div>
      <form onSubmit={onSubmit} className="flex gap-2">
        <input value={input} onChange={(e) => setInput(e.target.value)}
          placeholder="Message Collagent…" className="flex-1 rounded-md border px-3 py-2 text-sm" />
        <button type="submit" disabled={busy}
          className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
          Send
        </button>
      </form>
    </main>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<main className="p-4 text-sm text-gray-400">Loading…</main>}>
      <ChatInner />
    </Suspense>
  );
}
```

- [ ] **Step 3: Build to verify**

Run (from `frontend/`): `npm run build`
Expected: compiles with no type errors and no "useSearchParams must be wrapped in a suspense boundary" error.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/chat/page.tsx
git commit -m "feat: chat auto-sends prefilled ?ask= from event transfer"
```

---

### Task 11: Live smoke test + finish the branch

**Files:** none (verification only)

- [ ] **Step 1: Start the backend**

Run: `uv run uvicorn collagent.api.main:app --port 8000` (leave running in one shell).
Expected: Uvicorn startup, no import errors.

- [ ] **Step 2: Start the frontend**

Run (from `frontend/`): `npm run dev`
Expected: Next.js dev server on http://localhost:3000.

- [ ] **Step 3: End-to-end click-through (manual, with the M1 test user)**

1. Log in (magic link) and ensure the profile has interests/major set (onboarding from M1).
2. Open **Events** in the nav → empty state shows.
3. Click **Refresh** → after ~30–60s, 5–10 event cards render, each with a why-note grounded in the profile.
4. Confirm in Supabase (MCP `execute_sql` or Dashboard) that `events` has rows and `event_recommendations` has this user's ranked rows.
5. Click **Discuss in chat** on a card → lands on `/chat`, a visible "Tell me about the event: …" message auto-sends, and the agent answers using the event details (it should call `get_event_recommendations`).
6. In chat, ask "what events are good for me this week?" → the agent calls the tool unprompted and lists the curated events.

Expected: all six steps succeed. If the refresh is slow but completes, that is acceptable (matches major-map generation latency).

- [ ] **Step 4: Final full backend suite**

Run: `uv run pytest -v`
Expected: PASS (all). Stop the dev servers.

- [ ] **Step 5: Finish the branch**

Use the superpowers:finishing-a-development-branch skill: verify all tests pass, then present merge/PR options for `feat/m2-events-surface` into `main`.

---

## Notes for the implementer

- **Service role bypasses RLS:** the backend uses the Supabase service-role key, so the new RLS policies are defense-in-depth (and enable future direct frontend reads). Backend tests mock the client and never hit the network.
- **No new dependencies:** `zoneinfo` is stdlib (3.9+); `httpx`/`beautifulsoup4` are already in `pyproject.toml` from M1.
- **Generalization:** networking/opportunities reuse this shape — Tier-1 ingestion → shared index table → `curate_*` pipeline → per-user rec table → `GET /api/<surface>` + `make_<surface>_tools` chat tool + a surface page. Keep the events code readable as the template.
