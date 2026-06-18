# M3: Networking (People) Surface + Live Directory Lookup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a curated People/Networking surface (recommended ASU faculty/mentors with why-notes + contact path + "Discuss in chat"), plus live directory-lookup chat tools for both People and Events.

**Architecture:** Near-verbatim reuse of the M2 events "curation-feeds-chat" template — ingestion → shared index table → per-student curate pipeline → per-user recs table → `GET`/`POST /refresh` routes → curated chat tool + surface page. New in M3: the iSearch faculty JSON API as the source, and a live-search chat tool added to each surface (`search_people`, retrofitted `search_events`).

**Tech Stack:** Python 3.12, FastAPI, LangChain/LangGraph v1, Supabase (Postgres + Auth via service-role), httpx, PyJWT, pytest, `uv`; Next.js (App Router, TS), Tailwind. Spec: `docs/superpowers/specs/2026-06-18-networking-people-surface-design.md`.

**Constraints (carry into every task):**
- Supabase work via **Supabase MCP only** — project `collagent`, ref `qepwzwitwjhklxscrugr`. Ignore the stale "Collagent Database" project. Existing data may be overwritten.
- Never touch/commit `.env`/`.env.local`; never print secrets; do not stage the untracked `canvas-mcp/` directory.
- Run backend commands with `uv run` from the repo root. Run frontend commands from `frontend/`.

---

### Task 1: People schema migration

**Files:**
- Create: `supabase/migrations/0003_people.sql`

- [ ] **Step 1: Write the migration file**

```sql
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
```

- [ ] **Step 2: Apply the migration via Supabase MCP**

Load the Supabase MCP tools first: `ToolSearch` with query `select:mcp__89a6efff-3b83-4439-8253-89e4ab79f9c9__apply_migration,mcp__89a6efff-3b83-4439-8253-89e4ab79f9c9__list_tables`.

Call `apply_migration` with `project_id="qepwzwitwjhklxscrugr"`, `name="0003_people"`, and `query` = the full SQL above.

- [ ] **Step 3: Verify tables exist**

Call `list_tables` with `project_id="qepwzwitwjhklxscrugr"`, `schemas=["public"]`.
Expected: `people` and `person_recommendations` are present with the columns above, RLS enabled.

- [ ] **Step 4: Commit**

```bash
git add supabase/migrations/0003_people.sql
git commit -m "feat: M3 people schema (people + person_recommendations)"
```

---

### Task 2: PersonRecommendation model

**Files:**
- Modify: `src/collagent/models.py` (append after `EventRecommendation`)
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_models.py`:

```python
def test_person_recommendation_ignores_extra_fields():
    from collagent.models import PersonRecommendation

    rec = PersonRecommendation(
        id="r1", person_id="p1", name="Bing Si", title="Associate Professor",
        departments=["SCAI"], expertise_areas=["Machine Learning"],
        email="bing.si@asu.edu", profile_url="https://search.asu.edu/profile/123",
        why_note="Matches your ML interest.", rank=0, unexpected="x",
    )
    assert rec.name == "Bing Si"
    assert rec.expertise_areas == ["Machine Learning"]
    assert not hasattr(rec, "unexpected")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py::test_person_recommendation_ignores_extra_fields -v`
Expected: FAIL with `ImportError`/`cannot import name 'PersonRecommendation'`.

- [ ] **Step 3: Add the model**

Append to `src/collagent/models.py`:

```python
class PersonRecommendation(BaseModel):
    """Flattened view of a person_recommendations row joined to its person."""

    model_config = {"extra": "ignore"}

    id: str            # recommendation row id
    person_id: str
    name: str
    title: str | None = None
    departments: list[str] = []
    expertise_areas: list[str] = []
    email: str | None = None
    profile_url: str
    photo_url: str | None = None
    research_interests: str | None = None
    short_bio: str | None = None
    why_note: str
    rank: int
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/collagent/models.py tests/test_models.py
git commit -m "feat: PersonRecommendation model"
```

---

### Task 3: Ingestion parser (`parse_people`)

**Files:**
- Create: `src/collagent/asu/people.py`
- Test: `tests/test_people_parse.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_people_parse.py`:

```python
# tests/test_people_parse.py
from collagent.asu import people

# Trimmed to the fields parse_people reads; mirrors the real iSearch faculty-staff
# response shape where every value is wrapped in {"raw": ...}.
SAMPLE = {
    "results": [
        {  # faculty with expertise -> kept
            "asurite_id": {"raw": "bingsi"},
            "eid": {"raw": "123456"},
            "display_name": {"raw": "Bing Si"},
            "email_address": {"raw": "Bing.Si@asu.edu"},
            "primary_title": {"raw": ["Associate Professor"]},
            "departments": {"raw": ["School of Computing and Augmented Intelligence"]},
            "expertise_areas": {"raw": ["Machine Learning", "Data Mining"]},
            "research_interests": {"raw": None},
            "short_bio": {"raw": None},
            "photo_url": {"raw": "https://webapp4.asu.edu/photo-ws/directory_photo/123456"},
            "simplified_empl_classes": {"raw": ["Faculty"]},
        },
        {  # student worker, no expertise -> dropped
            "asurite_id": {"raw": "phjiang"},
            "eid": {"raw": "999"},
            "display_name": {"raw": "Patrick Jiang"},
            "email_address": {"raw": "phjiang@asu.edu"},
            "primary_title": {"raw": ["Student Worker IV"]},
            "departments": {"raw": None},
            "expertise_areas": {"raw": None},
            "simplified_empl_classes": {"raw": ["Student Worker"]},
        },
        {  # missing name -> skipped
            "asurite_id": {"raw": "noname"},
            "display_name": {"raw": None},
        },
    ]
}


def test_parse_people_keeps_faculty_unwraps_envelope():
    rows = people.parse_people(SAMPLE)
    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "asu_isearch"
    assert row["source_person_key"] == "bingsi"
    assert row["name"] == "Bing Si"
    assert row["email"] == "Bing.Si@asu.edu"
    assert row["title"] == "Associate Professor"
    assert row["departments"] == ["School of Computing and Augmented Intelligence"]
    assert row["expertise_areas"] == ["Machine Learning", "Data Mining"]
    assert row["profile_url"] == "https://search.asu.edu/profile/123456"


def test_parse_people_drops_staff_without_expertise():
    rows = people.parse_people(SAMPLE)
    keys = {r["source_person_key"] for r in rows}
    assert "phjiang" not in keys
    assert "noname" not in keys
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_people_parse.py -v`
Expected: FAIL with `ModuleNotFoundError: collagent.asu.people`.

- [ ] **Step 3: Write the parser module**

Create `src/collagent/asu/people.py`:

```python
# src/collagent/asu/people.py
"""iSearch faculty/staff ingestion. Pure parsing (parse_people) is unit-tested;
fetch_faculty/search_faculty are network-bound and verified via the capture script.
Source: GET https://search.asu.edu/api/v1/webdir-profiles/faculty-staff?query=...
Every API field is wrapped in a {"raw": <value>} envelope."""
import re

import httpx

from collagent.models import Profile

API_URL = "https://search.asu.edu/api/v1/webdir-profiles/faculty-staff"
PROFILE_BASE = "https://search.asu.edu/profile/"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "application/json"}
_FACULTY_HINT = re.compile(r"faculty|professor|lecturer", re.I)


def _raw(field):
    return field.get("raw") if isinstance(field, dict) else field


def _as_list(value) -> list[str]:
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    return [str(x).strip() for x in items if x is not None and str(x).strip()]


def _first(value) -> str | None:
    items = _as_list(value)
    return items[0] if items else None


def _text(value) -> str | None:
    items = _as_list(value)
    return "; ".join(items) if items else None


def _looks_like_faculty(empl_classes: list[str], title: str | None, expertise: list[str]) -> bool:
    if any(_FACULTY_HINT.search(c) for c in empl_classes):
        return True
    if title and _FACULTY_HINT.search(title):
        return True
    return bool(expertise)


def parse_people(payload: dict) -> list[dict]:
    """Map the iSearch response to the `people` row shape, filtering to likely faculty/
    mentors and deduping by asurite_id. Pure: no network."""
    rows: dict[str, dict] = {}
    for item in payload.get("results", []):
        def g(key):
            return _raw(item.get(key))

        asurite = g("asurite_id")
        name = g("display_name")
        if not asurite or not name:
            continue
        empl = _as_list(g("simplified_empl_classes"))
        title = _first(g("primary_title")) or _first(g("working_title"))
        expertise = _as_list(g("expertise_areas"))
        if not _looks_like_faculty(empl, title, expertise):
            continue
        eid = g("eid")
        profile_url = (
            f"{PROFILE_BASE}{eid}" if eid
            else f"https://search.asu.edu/?query={asurite}&searchType=people"
        )
        rows[asurite] = {
            "source": "asu_isearch",
            "source_person_key": asurite,
            "name": name,
            "email": g("email_address"),
            "title": title,
            "departments": _as_list(g("departments")),
            "expertise_areas": expertise,
            "research_interests": _text(g("research_interests")),
            "short_bio": _text(g("short_bio")),
            "profile_url": profile_url,
            "photo_url": g("photo_url"),
        }
    return list(rows.values())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_people_parse.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/collagent/asu/people.py tests/test_people_parse.py
git commit -m "feat: iSearch people parser (faculty filter + envelope unwrap)"
```

---

### Task 4: Ingestion fetch + query terms + capture script

**Files:**
- Modify: `src/collagent/asu/people.py` (append functions)
- Create: `scripts/capture_people_fixture.py`
- Test: `tests/test_people_parse.py` (append a `query_terms` test)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_people_parse.py`:

```python
from collagent.models import Profile


def test_query_terms_from_interests_and_major():
    profile = Profile(
        id="u1", email="a@asu.edu", major_name="Computer Systems Engineering",
        interests=["FPGA", "CUDA", "FPGA"],  # duplicate collapses
    )
    terms = people.query_terms(profile)
    assert terms[0] == "FPGA"
    assert "CUDA" in terms
    assert "Computer Systems Engineering" in terms
    assert len(terms) == len(set(t.lower() for t in terms))  # deduped


def test_query_terms_no_profile_is_empty():
    assert people.query_terms(None) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_people_parse.py::test_query_terms_from_interests_and_major -v`
Expected: FAIL with `AttributeError: module ... has no attribute 'query_terms'`.

- [ ] **Step 3: Append fetch + query_terms to `src/collagent/asu/people.py`**

```python
def query_terms(profile: Profile | None) -> list[str]:
    """Seed iSearch queries from the student's interests + major (deduped, capped)."""
    if profile is None:
        return []
    raw = list(profile.interests)
    if profile.major_name:
        raw.append(profile.major_name)
    seen: set[str] = set()
    out: list[str] = []
    for term in raw:
        t = term.strip()
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
        if len(out) >= 6:
            break
    return out


def _get_profiles(client: httpx.Client, query: str, size: int) -> list[dict]:
    resp = client.get(
        API_URL,
        params={"sort-by": "", "query": query, "page": 1, "size": size, "client": "asuis"},
    )
    if resp.status_code != 200:
        return []
    return parse_people(resp.json())


def fetch_faculty(query_list: list[str], per_term: int = 10) -> list[dict]:
    """Query the iSearch API once per term, parse, and dedupe by asurite_id.
    Resilient: a failing term is skipped rather than aborting ingestion."""
    rows: dict[str, dict] = {}
    with httpx.Client(headers=UA, timeout=15, follow_redirects=True) as client:
        for term in query_list:
            try:
                parsed = _get_profiles(client, term, per_term)
            except httpx.HTTPError:
                continue
            for row in parsed:
                rows[row["source_person_key"]] = row
    return list(rows.values())


def search_faculty(query: str, size: int = 8) -> list[dict]:
    """Single live directory query for the chat search_people tool."""
    with httpx.Client(headers=UA, timeout=15, follow_redirects=True) as client:
        try:
            return _get_profiles(client, query, size)
        except httpx.HTTPError:
            return []
```

- [ ] **Step 4: Create the capture script**

Create `scripts/capture_people_fixture.py`:

```python
# scripts/capture_people_fixture.py
"""Smoke-capture: query the iSearch faculty API and print a summary. Network required.
Run manually to verify ingestion works against the live API."""
from collagent.asu.people import fetch_faculty

if __name__ == "__main__":
    rows = fetch_faculty(["machine learning", "computer architecture"], per_term=5)
    print(f"fetched {len(rows)} people")
    for r in rows[:5]:
        print(f"  - {r['name']} — {r['title']} ({', '.join(r['departments'])})")
        print(f"    expertise: {', '.join(r['expertise_areas'])}")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_people_parse.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add src/collagent/asu/people.py scripts/capture_people_fixture.py tests/test_people_parse.py
git commit -m "feat: iSearch fetch_faculty/search_faculty + query_terms + capture script"
```

---

### Task 5: DB repository functions

**Files:**
- Modify: `src/collagent/db.py`
- Test: `tests/test_db_people.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_db_people.py`:

```python
# tests/test_db_people.py
from unittest.mock import MagicMock

from collagent import db

REC_ROW = {
    "id": "r1", "person_id": "p1", "why_note": "fits you", "rank": 0,
    "people": {
        "name": "Bing Si", "title": "Associate Professor",
        "departments": ["SCAI"], "expertise_areas": ["Machine Learning"],
        "email": "bing.si@asu.edu", "profile_url": "https://search.asu.edu/profile/123",
        "photo_url": None, "research_interests": None, "short_bio": None,
    },
}


def _client():
    client = MagicMock()
    client.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "p1"}]
    client.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value.data = [{"id": "p1", "name": "Bing Si"}]
    client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [REC_ROW]
    client.table.return_value.delete.return_value.eq.return_value.execute.return_value.data = []
    client.table.return_value.insert.return_value.execute.return_value.data = [{"id": "r1"}]
    return client


def test_upsert_people_uses_conflict_target(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    db.upsert_people([{"source": "asu_isearch", "source_person_key": "k", "name": "X", "profile_url": "u"}])
    _, kwargs = client.table.return_value.upsert.call_args
    assert kwargs.get("on_conflict") == "source,source_person_key"


def test_get_people_orders_and_limits(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    rows = db.get_people(limit=30)
    assert rows == [{"id": "p1", "name": "Bing Si"}]
    client.table.return_value.select.return_value.order.return_value.limit.assert_called_once_with(30)


def test_get_person_recommendations_flattens_join(monkeypatch):
    monkeypatch.setattr(db, "get_client", lambda: _client())
    recs = db.get_person_recommendations("u1")
    assert len(recs) == 1
    assert recs[0].name == "Bing Si"
    assert recs[0].why_note == "fits you"
    assert recs[0].person_id == "p1" and recs[0].rank == 0
    assert recs[0].expertise_areas == ["Machine Learning"]


def test_replace_person_recommendations_deletes_then_inserts(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    recs = db.replace_person_recommendations("u1", [{"person_id": "p1", "why_note": "w", "rank": 0}])
    client.table.return_value.delete.assert_called_once()
    inserted = client.table.return_value.insert.call_args.args[0]
    assert inserted[0]["user_id"] == "u1" and inserted[0]["person_id"] == "p1"
    assert recs[0].name == "Bing Si"  # round-trips through get_person_recommendations
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_db_people.py -v`
Expected: FAIL with `AttributeError: module 'collagent.db' has no attribute 'upsert_people'`.

- [ ] **Step 3: Add the DB functions**

In `src/collagent/db.py`, add `PersonRecommendation` to the models import block:

```python
from collagent.models import (
    CourseStatus,
    EventRecommendation,
    MajorMapCourse,
    PersonRecommendation,
    Profile,
    ProfileUpdate,
)
```

Append at the end of `src/collagent/db.py`:

```python
def upsert_people(rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    res = (
        get_client().table("people")
        .upsert(rows, on_conflict="source,source_person_key")
        .execute()
    )
    return res.data


def get_people(limit: int = 60) -> list[dict]:
    res = (
        get_client().table("people").select("*")
        .order("fetched_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data


def _flatten_person_rec(row: dict) -> PersonRecommendation:
    p = row.get("people") or {}
    return PersonRecommendation(
        id=row["id"],
        person_id=row["person_id"],
        why_note=row["why_note"],
        rank=row["rank"],
        name=p.get("name", ""),
        title=p.get("title"),
        departments=p.get("departments") or [],
        expertise_areas=p.get("expertise_areas") or [],
        email=p.get("email"),
        profile_url=p.get("profile_url", ""),
        photo_url=p.get("photo_url"),
        research_interests=p.get("research_interests"),
        short_bio=p.get("short_bio"),
    )


def get_person_recommendations(user_id: str) -> list[PersonRecommendation]:
    res = (
        get_client().table("person_recommendations")
        .select("id, person_id, why_note, rank, people(*)")
        .eq("user_id", user_id)
        .order("rank")
        .execute()
    )
    return [_flatten_person_rec(row) for row in res.data]


def replace_person_recommendations(
    user_id: str, rows: list[dict]
) -> list[PersonRecommendation]:
    client = get_client()
    client.table("person_recommendations").delete().eq("user_id", user_id).execute()
    if rows:
        payload = [{**r, "user_id": user_id} for r in rows]
        client.table("person_recommendations").insert(payload).execute()
    return get_person_recommendations(user_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_db_people.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/collagent/db.py tests/test_db_people.py
git commit -m "feat: people DB repository functions"
```

---

### Task 6: Shared student summary + people curation

**Files:**
- Create: `src/collagent/curation/student.py`
- Modify: `src/collagent/curation/events.py` (use the shared summary)
- Create: `src/collagent/curation/people.py`
- Test: `tests/test_curation_people.py`

- [ ] **Step 1: Extract the shared student summary**

Create `src/collagent/curation/student.py`:

```python
# src/collagent/curation/student.py
"""Shared student-context summary used by curation pipelines."""
from collagent.models import MajorMapCourse, Profile


def student_summary(profile: Profile | None, courses: list[MajorMapCourse]) -> str:
    if profile is None:
        return "No profile on file; recommend broadly relevant, high-signal matches."
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
    return "\n".join(parts) or "Profile is sparse; recommend broadly relevant matches."
```

- [ ] **Step 2: Point events curation at the shared summary**

In `src/collagent/curation/events.py`: delete the local `_student_summary` function, add the import `from collagent.curation.student import student_summary`, and in `_rank` replace `_student_summary(profile, courses)` with `student_summary(profile, courses)`.

- [ ] **Step 3: Verify the events suite still passes**

Run: `uv run pytest tests/test_curation_events.py -v`
Expected: PASS (2 tests) — `_rank` is monkeypatched in those tests, so the refactor is transparent.

- [ ] **Step 4: Write the failing people-curation test**

Create `tests/test_curation_people.py`:

```python
# tests/test_curation_people.py
from collagent.curation import people as curation
from collagent.curation.people import PersonRanking, RankedPerson
from collagent.models import Profile


def test_curate_drops_hallucinated_ids_and_reranks(monkeypatch):
    profile = Profile(id="u1", email="a@asu.edu", interests=["robotics"])
    monkeypatch.setattr(curation.db, "get_profile", lambda uid: profile)
    monkeypatch.setattr(curation.db, "get_major_map_courses", lambda uid: [])
    monkeypatch.setattr(
        curation.db, "get_people",
        lambda limit=60: [{"id": "p1", "name": "Prof A"}, {"id": "p2", "name": "Prof B"}],
    )
    monkeypatch.setattr(
        curation, "_rank",
        lambda profile, courses, ppl: PersonRanking(picks=[
            RankedPerson(person_id="p9", why_note="ghost"),
            RankedPerson(person_id="p1", why_note="works on robotics"),
        ]),
    )
    captured = {}
    monkeypatch.setattr(
        curation.db, "replace_person_recommendations",
        lambda uid, rows: captured.setdefault("rows", rows) or [],
    )
    curation.curate_people("u1")
    assert captured["rows"] == [{"person_id": "p1", "why_note": "works on robotics", "rank": 0}]


def test_curate_with_no_people_clears_recs(monkeypatch):
    monkeypatch.setattr(curation.db, "get_profile", lambda uid: None)
    monkeypatch.setattr(curation.db, "get_major_map_courses", lambda uid: [])
    monkeypatch.setattr(curation.db, "get_people", lambda limit=60: [])
    monkeypatch.setattr(
        curation, "_rank",
        lambda *a: (_ for _ in ()).throw(AssertionError("_rank must not run when people is empty")),
    )
    captured = {}
    monkeypatch.setattr(
        curation.db, "replace_person_recommendations",
        lambda uid, rows: captured.setdefault("rows", rows) or [],
    )
    curation.curate_people("u1")
    assert captured["rows"] == []
```

- [ ] **Step 5: Run test to verify it fails**

Run: `uv run pytest tests/test_curation_people.py -v`
Expected: FAIL with `ModuleNotFoundError: collagent.curation.people`.

- [ ] **Step 6: Write the people curation module**

Create `src/collagent/curation/people.py`:

```python
# src/collagent/curation/people.py
"""Per-student people curation: profile + candidate people -> ranked recs with why-notes.
A pure function with one structured-output LLM call (mirrors curation/events.py)."""
from pydantic import BaseModel, Field

from collagent import db
from collagent.curation.student import student_summary
from collagent.graph import get_model
from collagent.models import MajorMapCourse, PersonRecommendation, Profile


class RankedPerson(BaseModel):
    person_id: str = Field(description="Exact person_id of a candidate, copied verbatim")
    why_note: str = Field(description="1-2 sentences on why THIS person fits the student")


class PersonRanking(BaseModel):
    picks: list[RankedPerson] = Field(description="Top 5-10 people, best first")


_RANK_PROMPT = """You are an academic advisor helping one ASU student find faculty and
research mentors to reach out to. From the candidate people below, choose the 5-10 who
best fit this student's interests, major, goals, and coursework, and rank them best-first.
For each pick, write a 1-2 sentence why_note grounded in the person's expertise and the
student's specifics — not generic praise.
Only choose from the candidates and copy each person_id exactly. Do not invent people."""


def _candidate_block(candidates: list[dict]) -> str:
    blocks = []
    for p in candidates:
        expertise = ", ".join(p.get("expertise_areas") or []) or "(not listed)"
        depts = ", ".join(p.get("departments") or []) or "TBD"
        about = (p.get("research_interests") or p.get("short_bio") or "")[:300]
        blocks.append(
            f"person_id: {p['id']}\n"
            f"Name: {p.get('name') or '(unknown)'}\n"
            f"Title: {p.get('title') or 'TBD'}\n"
            f"Department: {depts}\n"
            f"Expertise: {expertise}\n"
            f"About: {about}"
        )
    return "\n\n".join(blocks)


def _rank(
    profile: Profile | None, courses: list[MajorMapCourse], candidates: list[dict]
) -> PersonRanking:
    llm = get_model().with_structured_output(PersonRanking)
    user = (
        f"STUDENT:\n{student_summary(profile, courses)}\n\n"
        f"CANDIDATE PEOPLE:\n{_candidate_block(candidates)}"
    )
    return llm.invoke([("system", _RANK_PROMPT), ("user", user)])


def curate_people(user_id: str) -> list[PersonRecommendation]:
    profile = db.get_profile(user_id)
    courses = db.get_major_map_courses(user_id)
    people = db.get_people(limit=60)
    if not people:
        return db.replace_person_recommendations(user_id, [])

    ranking = _rank(profile, courses, people)
    valid_ids = {p["id"] for p in people}
    rows: list[dict] = []
    seen: set[str] = set()
    for pick in ranking.picks:
        if pick.person_id in valid_ids and pick.person_id not in seen:
            rows.append(
                {"person_id": pick.person_id, "why_note": pick.why_note, "rank": len(rows)}
            )
            seen.add(pick.person_id)
    return db.replace_person_recommendations(user_id, rows)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/test_curation_people.py tests/test_curation_events.py -v`
Expected: PASS (4 tests).

- [ ] **Step 8: Commit**

```bash
git add src/collagent/curation/student.py src/collagent/curation/events.py src/collagent/curation/people.py tests/test_curation_people.py
git commit -m "feat: people curation pipeline + shared student summary"
```

---

### Task 7: People API routes

**Files:**
- Create: `src/collagent/api/routes/people.py`
- Modify: `src/collagent/api/main.py`
- Test: `tests/test_api_people.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_api_people.py`:

```python
# tests/test_api_people.py
from collagent.api.routes import people as people_routes
from collagent.models import PersonRecommendation

REC = PersonRecommendation(
    id="r1", person_id="p1", name="Bing Si", title="Associate Professor",
    departments=["SCAI"], expertise_areas=["Machine Learning"],
    email="bing.si@asu.edu", profile_url="https://search.asu.edu/profile/123",
    why_note="Matches your ML interest.", rank=0,
)


def test_get_people(client, monkeypatch):
    monkeypatch.setattr(people_routes.db, "get_person_recommendations", lambda uid: [REC])
    res = client.get("/api/people")
    assert res.status_code == 200
    assert res.json()[0]["name"] == "Bing Si"
    assert res.json()[0]["why_note"] == "Matches your ML interest."


def test_refresh_people_ingests_then_curates(client, monkeypatch):
    calls = []
    monkeypatch.setattr(people_routes.db, "get_profile", lambda uid: None)
    monkeypatch.setattr(people_routes.db, "get_major_map_courses", lambda uid: [])
    monkeypatch.setattr(people_routes, "query_terms", lambda profile: ["robotics"])
    monkeypatch.setattr(people_routes, "fetch_faculty", lambda terms: calls.append("fetch") or [{"x": 1}])
    monkeypatch.setattr(people_routes.db, "upsert_people", lambda rows: calls.append("upsert"))
    monkeypatch.setattr(people_routes, "curate_people", lambda uid: calls.append("curate") or [REC])
    res = client.post("/api/people/refresh", json={})
    assert res.status_code == 200
    assert calls == ["fetch", "upsert", "curate"]  # ingest before curate
    assert res.json()[0]["person_id"] == "p1"


def test_people_unauthenticated_401():
    from fastapi.testclient import TestClient

    from collagent.api.main import app

    assert TestClient(app).get("/api/people").status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api_people.py -v`
Expected: FAIL with `ModuleNotFoundError: collagent.api.routes.people`.

- [ ] **Step 3: Write the route module**

Create `src/collagent/api/routes/people.py`:

```python
# src/collagent/api/routes/people.py
from fastapi import APIRouter, Depends

from collagent import db
from collagent.api.auth import get_current_user_id
from collagent.asu.people import fetch_faculty, query_terms
from collagent.curation.people import curate_people
from collagent.models import PersonRecommendation

router = APIRouter(prefix="/api/people", tags=["people"])


@router.get("", response_model=list[PersonRecommendation])
def read_people(user_id: str = Depends(get_current_user_id)):
    return db.get_person_recommendations(user_id)


# Plain def: ingestion does sync httpx fan-out + an LLM call; FastAPI threadpools it.
@router.post("/refresh", response_model=list[PersonRecommendation])
def refresh_people(user_id: str = Depends(get_current_user_id)):
    profile = db.get_profile(user_id)
    db.upsert_people(fetch_faculty(query_terms(profile)))
    return curate_people(user_id)
```

- [ ] **Step 4: Register the router in `src/collagent/api/main.py`**

Change the routes import line to include `people`:

```python
from collagent.api.routes import chat, events, majormap, people, profile, programs
```

And add the registration immediately after the events router line:

```python
app.include_router(events.router)
app.include_router(people.router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_api_people.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add src/collagent/api/routes/people.py src/collagent/api/main.py tests/test_api_people.py
git commit -m "feat: people API routes (GET + refresh)"
```

---

### Task 8: People chat tools (curated + live search)

**Files:**
- Create: `src/collagent/people_tools.py`
- Modify: `src/collagent/api/routes/chat.py`
- Test: `tests/test_people_tools.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_people_tools.py`:

```python
# tests/test_people_tools.py
from collagent import people_tools
from collagent.models import PersonRecommendation

REC = PersonRecommendation(
    id="r1", person_id="p1", name="Bing Si", title="Associate Professor",
    departments=["SCAI"], expertise_areas=["Machine Learning"],
    email="bing.si@asu.edu", profile_url="https://search.asu.edu/profile/123",
    why_note="Matches your ML interest.", rank=0,
)

FOUND = {
    "source_person_key": "jdoe", "name": "Jane Doe", "title": "Professor",
    "departments": ["SCAI"], "expertise_areas": ["Robotics"],
    "email": "jane.doe@asu.edu", "profile_url": "https://search.asu.edu/profile/456",
}


def test_get_person_recommendations_renders_list(monkeypatch):
    monkeypatch.setattr(people_tools.db, "get_person_recommendations", lambda uid: [REC])
    tools = {t.name: t for t in people_tools.make_people_tools("u1")}
    out = tools["get_person_recommendations"].invoke({})
    assert "Bing Si" in out
    assert "Machine Learning" in out
    assert "Matches your ML interest." in out
    assert "bing.si@asu.edu" in out
    assert "https://search.asu.edu/profile/123" in out


def test_get_person_recommendations_empty(monkeypatch):
    monkeypatch.setattr(people_tools.db, "get_person_recommendations", lambda uid: [])
    tools = {t.name: t for t in people_tools.make_people_tools("u1")}
    out = tools["get_person_recommendations"].invoke({})
    assert "no people recommendations" in out.lower()


def test_search_people_renders_and_upserts(monkeypatch):
    upserted = {}
    monkeypatch.setattr(people_tools, "search_faculty", lambda q, **k: [FOUND])
    monkeypatch.setattr(people_tools.db, "upsert_people", lambda rows: upserted.setdefault("rows", rows))
    tools = {t.name: t for t in people_tools.make_people_tools("u1")}
    out = tools["search_people"].invoke({"query": "robotics"})
    assert "Jane Doe" in out
    assert "Robotics" in out
    assert upserted["rows"] == [FOUND]  # live results persisted to the shared index


def test_search_people_no_matches(monkeypatch):
    monkeypatch.setattr(people_tools, "search_faculty", lambda q, **k: [])
    tools = {t.name: t for t in people_tools.make_people_tools("u1")}
    out = tools["search_people"].invoke({"query": "zzz"})
    assert "no asu directory matches" in out.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_people_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: collagent.people_tools`.

- [ ] **Step 3: Write the tools module**

Create `src/collagent/people_tools.py`:

```python
# src/collagent/people_tools.py
"""Per-user people tools: the chat agent reads the curated store (door B) and can run
a live ASU directory lookup, persisting found people into the shared index."""
from langchain.tools import tool

from collagent import db
from collagent.asu.people import search_faculty


def _render(*, name, title, departments, expertise_areas, email, profile_url, why_note=None) -> str:
    dept = f" · {', '.join(departments)}" if departments else ""
    lines = [f"- {name} — {title or 'TBD'}{dept}"]
    if expertise_areas:
        lines.append(f"  Expertise: {', '.join(expertise_areas)}")
    if why_note:
        lines.append(f"  Why recommended: {why_note}")
    if email:
        lines.append(f"  Email: {email}")
    lines.append(f"  Profile: {profile_url}")
    return "\n".join(lines)


def make_people_tools(user_id: str) -> list:
    @tool("get_person_recommendations")
    def get_person_recommendations() -> str:
        """Return this student's current curated people-to-contact recommendations
        (name, title, department, expertise, contact, and why each was recommended)."""
        recs = db.get_person_recommendations(user_id)
        if not recs:
            return (
                "No people recommendations yet. Suggest the student open the People "
                "page and click Refresh to generate them."
            )
        return "\n\n".join(
            _render(
                name=r.name, title=r.title, departments=r.departments,
                expertise_areas=r.expertise_areas, email=r.email,
                profile_url=r.profile_url, why_note=r.why_note,
            )
            for r in recs
        )

    @tool("search_people")
    def search_people(query: str) -> str:
        """Search the ASU directory live for faculty/staff by name or topic
        (e.g. 'robotics', 'Professor Smith'). Use for ad-hoc lookups that are not
        already in the student's saved recommendations."""
        found = search_faculty(query)
        if not found:
            return f"No ASU directory matches found for '{query}'."
        db.upsert_people(found)
        return "\n\n".join(
            _render(
                name=p["name"], title=p.get("title"),
                departments=p.get("departments") or [],
                expertise_areas=p.get("expertise_areas") or [],
                email=p.get("email"), profile_url=p.get("profile_url", ""),
            )
            for p in found
        )

    return [get_person_recommendations, search_people]
```

- [ ] **Step 4: Wire into chat in `src/collagent/api/routes/chat.py`**

Add the import `from collagent.people_tools import make_people_tools` (next to the event-tools import), and extend `extra_tools` in the `create_graph(...)` call:

```python
        extra_tools=(
            tuple(make_profile_tools(user_id))
            + tuple(make_event_tools(user_id))
            + tuple(make_people_tools(user_id))
        ),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_people_tools.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add src/collagent/people_tools.py src/collagent/api/routes/chat.py tests/test_people_tools.py
git commit -m "feat: people chat tools (curated + live search) wired into chat"
```

---

### Task 9: Events live-search retrofit (`search_events`)

**Files:**
- Modify: `src/collagent/event_tools.py`
- Test: `tests/test_event_tools.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_event_tools.py`:

```python
SAMPLE_EVENTS = [
    {"title": "Robotics Workshop", "description": "Build a robot arm", "location": "Tempe",
     "starts_at": "2026-06-20T14:00:00-07:00", "url": "https://asuevents.asu.edu/e/robot"},
    {"title": "Yoga on the Lawn", "description": "Relax", "location": "Tempe",
     "starts_at": "2026-06-21T09:00:00-07:00", "url": "https://asuevents.asu.edu/e/yoga"},
]


def test_search_events_filters_by_keyword(monkeypatch):
    monkeypatch.setattr(event_tools, "fetch_upcoming_events", lambda: SAMPLE_EVENTS)
    tools = {t.name: t for t in event_tools.make_event_tools("u1")}
    out = tools["search_events"].invoke({"query": "robot"})
    assert "Robotics Workshop" in out
    assert "Yoga on the Lawn" not in out
    assert "https://asuevents.asu.edu/e/robot" in out


def test_search_events_no_matches(monkeypatch):
    monkeypatch.setattr(event_tools, "fetch_upcoming_events", lambda: SAMPLE_EVENTS)
    tools = {t.name: t for t in event_tools.make_event_tools("u1")}
    out = tools["search_events"].invoke({"query": "quantum"})
    assert "no upcoming events" in out.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_event_tools.py::test_search_events_filters_by_keyword -v`
Expected: FAIL with `KeyError: 'search_events'`.

- [ ] **Step 3: Add the live-search tool**

In `src/collagent/event_tools.py`, add the import near the top:

```python
from collagent.asu.events import fetch_upcoming_events
```

Inside `make_event_tools`, add a second tool before the `return`, and include it in the returned list:

```python
    @tool("search_events")
    def search_events(query: str) -> str:
        """Search upcoming ASU events live by keyword (matches title, description, or
        location). Use for ad-hoc event lookups not in the student's saved recommendations."""
        q = query.lower().strip()
        matches = []
        for e in fetch_upcoming_events():
            haystack = " ".join(
                filter(None, [e.get("title"), e.get("description"), e.get("location")])
            ).lower()
            if q in haystack:
                matches.append(e)
            if len(matches) >= 8:
                break
        if not matches:
            return f"No upcoming events found matching '{query}'."
        blocks = []
        for e in matches:
            when = e.get("starts_at") or "TBD"
            where = f", {e['location']}" if e.get("location") else ""
            blocks.append(f"- {e['title']} ({when}{where})\n  Link: {e['url']}")
        return "\n\n".join(blocks)

    return [get_event_recommendations, search_events]
```

(Remove the old `return [get_event_recommendations]` line.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_event_tools.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/collagent/event_tools.py tests/test_event_tools.py
git commit -m "feat: retrofit live search_events chat tool onto Events"
```

---

### Task 10: Frontend — types, People page, nav

**Files:**
- Modify: `frontend/lib/types.ts`
- Create: `frontend/app/people/page.tsx`
- Modify: `frontend/components/Nav.tsx`

> Note (`frontend/AGENTS.md`): this Next.js may differ from training data. The People page mirrors the working `app/events/page.tsx` exactly in structure — do not introduce new patterns. No `useSearchParams` here, so no `<Suspense>` wrapper is needed.

- [ ] **Step 1: Add the type**

Append to `frontend/lib/types.ts`:

```ts
export interface PersonRecommendation {
  id: string;
  person_id: string;
  name: string;
  title: string | null;
  departments: string[];
  expertise_areas: string[];
  email: string | null;
  profile_url: string;
  photo_url: string | null;
  research_interests: string | null;
  short_bio: string | null;
  why_note: string;
  rank: number;
}
```

- [ ] **Step 2: Create the People page**

Create `frontend/app/people/page.tsx`:

```tsx
// frontend/app/people/page.tsx
"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { PersonRecommendation } from "@/lib/types";

export default function PeoplePage() {
  const router = useRouter();
  const [recs, setRecs] = useState<PersonRecommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    api.get("/api/people")
      .then(setRecs)
      .catch(() => setRecs([]))
      .finally(() => setLoading(false));
  }, []);

  async function refresh() {
    setRefreshing(true);
    try {
      setRecs(await api.post("/api/people/refresh", {}));
    } catch {
      // keep existing recs on failure
    } finally {
      setRefreshing(false);
    }
  }

  function discuss(rec: PersonRecommendation) {
    const role = rec.title ? `, ${rec.title}` : "";
    const ask = `Tell me about ${rec.name}${role} at ASU and how I might connect with them.`;
    router.push(`/chat?ask=${encodeURIComponent(ask)}`);
  }

  return (
    <main className="mx-auto w-full max-w-2xl p-4">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold">People to connect with</h1>
        <button onClick={refresh} disabled={refreshing}
          className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
          {refreshing ? "Finding people…" : "Refresh"}
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
                  <a href={rec.profile_url} target="_blank" rel="noopener noreferrer"
                    className="font-medium hover:underline">
                    {rec.name}
                  </a>
                  <p className="text-xs text-gray-500">
                    {rec.title ?? "ASU"}{rec.departments.length ? ` · ${rec.departments.join(", ")}` : ""}
                  </p>
                  {rec.expertise_areas.length > 0 && (
                    <p className="mt-1 text-xs text-gray-500">
                      Expertise: {rec.expertise_areas.join(", ")}
                    </p>
                  )}
                </div>
                <button onClick={() => discuss(rec)}
                  className="shrink-0 rounded-md border px-3 py-1 text-xs font-medium hover:bg-gray-50">
                  Discuss in chat
                </button>
              </div>
              <p className="mt-2 rounded bg-gray-50 px-3 py-2 text-sm text-gray-700">
                {rec.why_note}
              </p>
              {rec.email && (
                <a href={`mailto:${rec.email}`}
                  className="mt-2 inline-block text-xs font-medium text-blue-600 hover:underline">
                  {rec.email}
                </a>
              )}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
```

- [ ] **Step 3: Add the nav link**

In `frontend/components/Nav.tsx`, add to `LINKS` after the events entry:

```tsx
  { href: "/people", label: "People" },
```

- [ ] **Step 4: Verify the frontend builds**

Run (from `frontend/`): `npm run build`
Expected: build succeeds with no type errors; `/people` appears in the route list.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/types.ts frontend/app/people/page.tsx frontend/components/Nav.tsx
git commit -m "feat: People surface page, type, and nav link"
```

---

### Task 11: Full test run + live smoke + finish branch

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend suite**

Run: `uv run pytest -q`
Expected: all tests pass (M2's slow live-LLM extraction test may be deselected, as before).

- [ ] **Step 2: Live ingestion smoke**

Run: `uv run python scripts/capture_people_fixture.py`
Expected: prints "fetched N people" (N > 0) with names, titles, departments, and expertise. If it prints 0, the live API shape changed — investigate before proceeding.

- [ ] **Step 3: Full live pipeline smoke for the onboarded test profile**

Run this one-off (uses the onboarded test user from M2):

```bash
uv run python -c "from collagent import db; from collagent.asu.people import fetch_faculty, query_terms; from collagent.curation.people import curate_people; uid='2dcbebda-70a7-4d1f-8fb9-f8d2e43289ff'; p=db.get_profile(uid); n=db.upsert_people(fetch_faculty(query_terms(p))); print('upserted', len(n)); recs=curate_people(uid); print('recs', len(recs)); [print(' -', r.name, '|', r.title, '|', r.why_note) for r in recs]"
```

Expected: upserts > 0 people and prints a small ranked list of faculty with why-notes grounded in the profile's interests. (If the OpenAI endpoint times out, it is the known VPN issue — retry once connectivity is restored.)

- [ ] **Step 4: Live directory search smoke**

```bash
uv run python -c "from collagent.asu.people import search_faculty; r=search_faculty('robotics'); print('found', len(r)); [print(' -', x['name'], '|', x['title']) for x in r[:5]]"
```

Expected: prints several matching people.

- [ ] **Step 5: Finish the development branch**

Use the **superpowers:finishing-a-development-branch** skill. Verify tests pass, then present the merge/PR options for `feat/m3-networking` → `main`.

---

## Self-Review

**Spec coverage:**
- §3 data source (iSearch API, envelope, profile_url from eid, faculty filter) → Tasks 3–4.
- §4 schema (people + person_recommendations, RLS) → Task 1.
- §5 ingestion (parse_people, query_terms, fetch_faculty, search_faculty, capture script) → Tasks 3–4.
- §6 curation (RankedPerson/PersonRanking, candidate validation, replace semantics, empty short-circuit) → Task 6.
- §7 chat tools (curated `get_person_recommendations` + live `search_people` w/ upsert; `search_events` retrofit) → Tasks 8–9.
- §8 API (GET + POST /refresh, model) → Tasks 2, 7.
- §9 frontend (type, /people page, nav, mailto + Discuss-in-chat) → Task 10.
- §10 testing (parser, curation, db, api, tools) → each task's tests; live smoke → Task 11.
- §11 constraints (Supabase MCP only, no .env, contact-path-only, manual refresh) → honored throughout; no outreach/email feature added.

**Placeholder scan:** No TBD/TODO; every code step contains complete code; no "similar to" references.

**Type consistency:** `PersonRecommendation` fields are identical across `models.py`, `db._flatten_person_rec`, `test_*`, and the TS interface. `RankedPerson.person_id` / `why_note` match `curate_people`'s row dict (`{"person_id", "why_note", "rank"}`) and `replace_person_recommendations`. `query_terms`, `fetch_faculty`, `search_faculty`, `parse_people` signatures match their call sites in the route and tools. `_render(...)` keyword args match both call sites in `people_tools.py`.
