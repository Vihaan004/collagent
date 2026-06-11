# Collagent PoC Milestone 1: App Shell + Supabase + Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the CLI-only collagent into a deployable web app: Next.js frontend + FastAPI backend + Supabase (auth + Postgres), with an onboarding flow where the agent auto-builds the student's ASU major map for them to confirm.

**Architecture:** Python package stays at repo root (`src/collagent`); a FastAPI layer (`src/collagent/api/`) wraps the existing LangGraph agent and new ASU data modules; a new `frontend/` directory holds the Next.js app. Supabase provides auth (frontend) + Postgres (backend via service role). The profile-aware chat agent gets its system prompt assembled per-session from the profile and writes profile data only through typed tools.

**Tech Stack:** Python 3.12, FastAPI, LangGraph/LangChain v1, Supabase (Postgres + Auth), PyJWT, BeautifulSoup, Playwright (chromium), pytest; Next.js (App Router, TypeScript), Tailwind CSS, @supabase/ssr.

**Specs:** `docs/superpowers/specs/2026-06-09-collagent-vision-design.md`, `docs/superpowers/specs/2026-06-09-collagent-technical-feature-spec.md`

**Reconnaissance findings (verified 2026-06-10, build on these):**
- `https://degrees.apps.asu.edu/bachelors/major-list/interest-area/{01..15}` — server-rendered HTML containing links `href="/bachelors/major/ASU00/{ACAD_PLAN_CODE}/{slug}"` for every undergrad program. Plain `httpx` fetch with a browser User-Agent works.
- `https://webapp4.asu.edu/programs/t5/roadmaps/ASU00/{code}/null/ALL/{year}` — returns 200 with the page shell (e.g. code `ESCSEBS`, year `2025` → title "Computer Science,BS | Major Map"), but **course data is JS-loaded**: extraction requires Playwright render → inner text → LLM structured-output extraction.
- All ASU fetches need header `User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)` or they may be blocked.

**Testing philosophy for this plan:** Backend follows TDD (failing test → implement → pass → commit). Frontend tasks use `npm run build` (typecheck + compile) plus a manual smoke check as the verification bar — a deliberate PoC-speed tradeoff recorded in the spec's development philosophy. LLM-dependent extraction has an integration test gated on `OPENAI_API_KEY` being set.

**Working directory note:** All backend commands run from the repo root. `uv` is the package manager (`uv pip install -e ".[dev]"`, `uv run pytest`). Frontend commands run from `frontend/`.

---

### Task 1: Supabase project + schema migration

**Files:**
- Create: `supabase/migrations/0001_init.sql`
- Modify: `.env.example`

- [ ] **Step 1: Create the Supabase project (manual, requires user)**

Go to https://supabase.com/dashboard → New project, name `collagent`, region US-West, generate a DB password and save it. After creation, collect from Project Settings → API:
- Project URL (`https://<ref>.supabase.co`)
- `anon` public key
- `service_role` secret key
- Legacy JWT secret (Settings → API → JWT Settings → "JWT Secret")

> **Contingency:** if the dashboard shows only the new "JWT Signing Keys" (asymmetric) and no legacy HS256 secret, note it — Task 4 contains the JWKS fallback.

- [ ] **Step 2: Write the migration SQL**

```sql
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
```

- [ ] **Step 3: Apply the migration**

Paste the SQL into Supabase dashboard → SQL Editor → Run. Expected: "Success. No rows returned".

- [ ] **Step 4: Verify schema**

In SQL Editor run: `select table_name from information_schema.tables where table_schema='public';`
Expected rows: `profiles`, `major_map_courses`.

- [ ] **Step 5: Update `.env.example` and local `.env`**

Append to `.env.example`:

```
# Supabase (backend)
SUPABASE_URL=https://YOUR-REF.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_JWT_SECRET=...
FRONTEND_ORIGIN=http://localhost:3000
```

Fill the real values into `.env` (never committed; `.gitignore` already covers it).

- [ ] **Step 6: Commit**

```bash
git add supabase/migrations/0001_init.sql .env.example
git commit -m "feat: add supabase schema (profiles, major_map_courses, RLS, signup trigger)"
```

---

### Task 2: Backend dependencies + settings module

**Files:**
- Modify: `pyproject.toml`
- Create: `src/collagent/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Add dependencies**

In `pyproject.toml`, extend `dependencies` and add a dev group:

```toml
dependencies = [
    "click>=8.1.8",
    "dotenv>=0.9.9",
    "httpx>=0.28.1",
    "langchain>=1.2.16",
    "langchain-openai>=1.2.1",
    "langgraph>=1.1.10",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "supabase>=2.13",
    "pydantic-settings>=2.7",
    "pyjwt>=2.10",
    "beautifulsoup4>=4.12",
    "playwright>=1.50",
]

[dependency-groups]
dev = ["pytest>=8.3"]
```

Also add pytest config at the bottom:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

Run: `uv pip install -e . --group dev` (if the `--group` flag is unavailable in your uv version, run `uv pip install -e .` then `uv pip install pytest`)
Expected: resolves and installs without error.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_config.py
from collagent.config import Settings


def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "jwt")
    s = Settings(_env_file=None)
    assert s.supabase_url == "https://x.supabase.co"
    assert s.supabase_service_role_key == "svc"
    assert s.supabase_jwt_secret == "jwt"
    assert s.frontend_origin == "http://localhost:3000"  # default
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'collagent.config'`

- [ ] **Step 4: Implement**

```python
# src/collagent/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""
    frontend_origin: str = "http://localhost:3000"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/collagent/config.py tests/test_config.py
git commit -m "feat: add backend deps and pydantic-settings config"
```

---

### Task 3: Pydantic models + DB repository

**Files:**
- Create: `src/collagent/models.py`
- Create: `src/collagent/db.py`
- Test: `tests/test_models.py`, `tests/test_db.py`

- [ ] **Step 1: Write failing model tests**

```python
# tests/test_models.py
import pytest
from pydantic import ValidationError

from collagent.models import MajorMapCourse, Profile, ProfileUpdate


def test_profile_defaults():
    p = Profile(id="u1", email="a@asu.edu")
    assert p.interests == [] and p.clubs == [] and p.onboarded is False


def test_profile_ignores_extra_db_columns():
    p = Profile(id="u1", email="a@asu.edu", created_at="2026-01-01T00:00:00Z")
    assert p.id == "u1"


def test_course_status_validated():
    with pytest.raises(ValidationError):
        MajorMapCourse(id="c1", user_id="u1", term_number=1, title="X", status="done")


def test_profile_update_excludes_unset():
    u = ProfileUpdate(major_name="Computer Science")
    assert u.model_dump(exclude_unset=True) == {"major_name": "Computer Science"}
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'collagent.models'`

- [ ] **Step 3: Implement models**

```python
# src/collagent/models.py
from typing import Literal

from pydantic import BaseModel

CourseStatus = Literal["taken", "in_progress", "remaining"]
AcademicYear = Literal["freshman", "sophomore", "junior", "senior", "graduate"]


class Profile(BaseModel):
    model_config = {"extra": "ignore"}

    id: str
    email: str
    full_name: str | None = None
    major_name: str | None = None
    acad_plan_code: str | None = None
    catalog_year: str | None = None
    academic_year: AcademicYear | None = None
    interests: list[str] = []
    goals: str | None = None
    clubs: list[str] = []
    projects: str | None = None
    onboarded: bool = False


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    major_name: str | None = None
    acad_plan_code: str | None = None
    catalog_year: str | None = None
    academic_year: AcademicYear | None = None
    interests: list[str] | None = None
    goals: str | None = None
    clubs: list[str] | None = None
    projects: str | None = None
    onboarded: bool | None = None


class MajorMapCourse(BaseModel):
    model_config = {"extra": "ignore"}

    id: str
    user_id: str
    term_number: int
    course_code: str | None = None
    title: str
    credits: float | None = None
    requirement_note: str | None = None
    status: CourseStatus = "remaining"
    sort_order: int = 0
```

- [ ] **Step 4: Run model tests**

Run: `uv run pytest tests/test_models.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Write failing db tests (mocked supabase client)**

```python
# tests/test_db.py
from unittest.mock import MagicMock

from collagent import db
from collagent.models import ProfileUpdate

PROFILE_ROW = {"id": "u1", "email": "a@asu.edu", "major_name": None}
COURSE_ROW = {
    "id": "c1", "user_id": "u1", "term_number": 1,
    "course_code": "CSE 110", "title": "Programming", "status": "remaining",
}


def _client_returning(data):
    client = MagicMock()
    # terminal .execute() on any chained call returns an object with .data
    client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = data
    client.table.return_value.select.return_value.eq.return_value.order.return_value.order.return_value.execute.return_value.data = data
    client.table.return_value.update.return_value.eq.return_value.execute.return_value.data = data
    client.table.return_value.insert.return_value.execute.return_value.data = data
    client.table.return_value.delete.return_value.eq.return_value.execute.return_value.data = []
    return client


def test_get_profile_found(monkeypatch):
    monkeypatch.setattr(db, "get_client", lambda: _client_returning([PROFILE_ROW]))
    p = db.get_profile("u1")
    assert p is not None and p.email == "a@asu.edu"


def test_get_profile_missing(monkeypatch):
    monkeypatch.setattr(db, "get_client", lambda: _client_returning([]))
    assert db.get_profile("u1") is None


def test_update_profile_sends_only_set_fields(monkeypatch):
    client = _client_returning([PROFILE_ROW])
    monkeypatch.setattr(db, "get_client", lambda: client)
    db.update_profile("u1", ProfileUpdate(major_name="CS"))
    client.table.return_value.update.assert_called_once_with({"major_name": "CS"})


def test_get_major_map_courses(monkeypatch):
    monkeypatch.setattr(db, "get_client", lambda: _client_returning([COURSE_ROW]))
    courses = db.get_major_map_courses("u1")
    assert len(courses) == 1 and courses[0].course_code == "CSE 110"


def test_replace_major_map_courses_deletes_then_inserts(monkeypatch):
    client = _client_returning([COURSE_ROW])
    monkeypatch.setattr(db, "get_client", lambda: client)
    rows = [{"term_number": 1, "title": "Programming", "course_code": "CSE 110"}]
    result = db.replace_major_map_courses("u1", rows)
    client.table.return_value.delete.assert_called_once()
    inserted = client.table.return_value.insert.call_args.args[0]
    assert inserted[0]["user_id"] == "u1"
    assert result[0].id == "c1"
```

- [ ] **Step 6: Run to verify failure**

Run: `uv run pytest tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'collagent.db'` (or AttributeError)

- [ ] **Step 7: Implement the repository**

```python
# src/collagent/db.py
from functools import lru_cache

from supabase import Client, create_client

from collagent.config import settings
from collagent.models import CourseStatus, MajorMapCourse, Profile, ProfileUpdate


@lru_cache(maxsize=1)
def get_client() -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def get_profile(user_id: str) -> Profile | None:
    res = get_client().table("profiles").select("*").eq("id", user_id).execute()
    if not res.data:
        return None
    return Profile(**res.data[0])


def update_profile(user_id: str, update: ProfileUpdate) -> Profile:
    payload = update.model_dump(exclude_unset=True)
    res = get_client().table("profiles").update(payload).eq("id", user_id).execute()
    return Profile(**res.data[0])


def get_major_map_courses(user_id: str) -> list[MajorMapCourse]:
    res = (
        get_client().table("major_map_courses").select("*")
        .eq("user_id", user_id)
        .order("term_number").order("sort_order")
        .execute()
    )
    return [MajorMapCourse(**row) for row in res.data]


def replace_major_map_courses(user_id: str, courses: list[dict]) -> list[MajorMapCourse]:
    client = get_client()
    client.table("major_map_courses").delete().eq("user_id", user_id).execute()
    rows = [{**c, "user_id": user_id} for c in courses]
    res = client.table("major_map_courses").insert(rows).execute()
    return [MajorMapCourse(**row) for row in res.data]


def update_course_statuses(user_id: str, updates: list[tuple[str, CourseStatus]]) -> None:
    client = get_client()
    for course_id, status in updates:
        (
            client.table("major_map_courses").update({"status": status})
            .eq("id", course_id).eq("user_id", user_id)
            .execute()
        )
```

- [ ] **Step 8: Run all tests**

Run: `uv run pytest -v`
Expected: PASS (all)

- [ ] **Step 9: Commit**

```bash
git add src/collagent/models.py src/collagent/db.py tests/test_models.py tests/test_db.py
git commit -m "feat: add typed models and supabase repository layer"
```

---

### Task 4: Auth dependency (Supabase JWT verification)

**Files:**
- Create: `src/collagent/api/__init__.py` (empty), `src/collagent/api/auth.py`
- Test: `tests/test_auth.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_auth.py
import time

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from collagent.api import auth

SECRET = "test-secret"


def _token(sub="user-123", aud="authenticated", exp_offset=3600, secret=SECRET):
    return jwt.encode(
        {"sub": sub, "aud": aud, "exp": int(time.time()) + exp_offset},
        secret,
        algorithm="HS256",
    )


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    monkeypatch.setattr(auth.settings, "supabase_jwt_secret", SECRET)


def test_valid_token_returns_user_id():
    assert auth.get_current_user_id(_creds(_token())) == "user-123"


def test_missing_token_401():
    with pytest.raises(HTTPException) as e:
        auth.get_current_user_id(None)
    assert e.value.status_code == 401


def test_bad_signature_401():
    with pytest.raises(HTTPException) as e:
        auth.get_current_user_id(_creds(_token(secret="wrong")))
    assert e.value.status_code == 401


def test_expired_token_401():
    with pytest.raises(HTTPException) as e:
        auth.get_current_user_id(_creds(_token(exp_offset=-100)))
    assert e.value.status_code == 401
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_auth.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# src/collagent/api/auth.py
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from collagent.config import settings

_bearer = HTTPBearer(auto_error=False)


def get_current_user_id(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if creds is None:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        payload = jwt.decode(
            creds.credentials,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")
    return payload["sub"]
```

> **Contingency (only if Task 1 found no legacy JWT secret):** the Supabase project signs tokens asymmetrically. Replace the decode call with a module-level `jwt.PyJWKClient(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json")`, get the signing key via `client.get_signing_key_from_jwt(creds.credentials)`, and pass `algorithms=["ES256", "RS256"]`. Tests then mock `get_signing_key_from_jwt`.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_auth.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/collagent/api/ tests/test_auth.py
git commit -m "feat: add supabase JWT auth dependency"
```

---

### Task 5: FastAPI app + profile routes

**Files:**
- Create: `src/collagent/api/main.py`, `src/collagent/api/routes/__init__.py` (empty), `src/collagent/api/routes/profile.py`
- Test: `tests/test_api_profile.py`, `tests/conftest.py`

- [ ] **Step 1: Write shared test fixtures**

```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient

from collagent.api.auth import get_current_user_id
from collagent.api.main import app

TEST_USER = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER
    yield TestClient(app)
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Write failing route tests**

```python
# tests/test_api_profile.py
from collagent.api.routes import profile as profile_routes
from collagent.models import Profile
from tests.conftest import TEST_USER

PROFILE = Profile(id=TEST_USER, email="a@asu.edu")


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_get_profile(client, monkeypatch):
    monkeypatch.setattr(profile_routes.db, "get_profile", lambda uid: PROFILE)
    res = client.get("/api/profile")
    assert res.status_code == 200 and res.json()["email"] == "a@asu.edu"


def test_get_profile_404(client, monkeypatch):
    monkeypatch.setattr(profile_routes.db, "get_profile", lambda uid: None)
    assert client.get("/api/profile").status_code == 404


def test_put_profile(client, monkeypatch):
    captured = {}

    def fake_update(uid, update):
        captured["fields"] = update.model_dump(exclude_unset=True)
        return PROFILE.model_copy(update=captured["fields"])

    monkeypatch.setattr(profile_routes.db, "update_profile", fake_update)
    res = client.put("/api/profile", json={"major_name": "Computer Science"})
    assert res.status_code == 200
    assert captured["fields"] == {"major_name": "Computer Science"}


def test_unauthenticated_401():
    from fastapi.testclient import TestClient

    from collagent.api.main import app

    assert TestClient(app).get("/api/profile").status_code == 401
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_api_profile.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'collagent.api.main'`

- [ ] **Step 4: Implement app + routes**

```python
# src/collagent/api/routes/profile.py
from fastapi import APIRouter, Depends, HTTPException

from collagent import db
from collagent.api.auth import get_current_user_id
from collagent.models import Profile, ProfileUpdate

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=Profile)
def read_profile(user_id: str = Depends(get_current_user_id)):
    profile = db.get_profile(user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.put("", response_model=Profile)
def write_profile(update: ProfileUpdate, user_id: str = Depends(get_current_user_id)):
    return db.update_profile(user_id, update)
```

```python
# src/collagent/api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from collagent.api.routes import profile
from collagent.config import settings

app = FastAPI(title="collagent api")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(profile.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest -v`
Expected: PASS (all)

- [ ] **Step 6: Smoke-run the server**

Run: `uv run uvicorn collagent.api.main:app --port 8000` then in another shell `curl -s http://localhost:8000/api/health`
Expected: `{"status":"ok"}`. Stop the server.

- [ ] **Step 7: Commit**

```bash
git add src/collagent/api/ tests/conftest.py tests/test_api_profile.py
git commit -m "feat: add fastapi app with profile routes"
```

---

### Task 6: ASU program catalog — parser, seed script, search, endpoint

**Files:**
- Create: `src/collagent/asu/__init__.py` (empty), `src/collagent/asu/programs.py`, `scripts/seed_programs.py`, `src/collagent/api/routes/programs.py`
- Create (generated): `data/asu_programs.json`
- Modify: `src/collagent/api/main.py`
- Test: `tests/test_programs.py`

- [ ] **Step 1: Write failing parser + search tests**

```python
# tests/test_programs.py
import json

from collagent.asu import programs

LISTING_SNIPPET = """
<html><body>
<a href="/bachelors/major/ASU00/ESCSEBS/computer-science">Computer Science</a>
<a href="/bachelors/major/ASU00/ESCSEBS#accelerateDeg">Accelerated</a>
<a href="/bachelors/major/ASU00/ASPGSPPBS/psychology-positive-psychology">Psychology (Positive Psychology)</a>
<a href="/somewhere/else">Not a major</a>
</body></html>
"""


def test_parse_major_links_extracts_codes_and_names():
    result = programs.parse_major_links(LISTING_SNIPPET)
    codes = {p["code"]: p for p in result}
    assert codes["ESCSEBS"]["name"] == "Computer Science"
    assert codes["ESCSEBS"]["slug"] == "computer-science"
    assert "ASPGSPPBS" in codes
    assert len(result) == 2  # anchor-only and non-major links ignored


def test_search_programs_substring_beats_fuzzy(tmp_path, monkeypatch):
    data = [
        {"code": "ESCSEBS", "slug": "computer-science", "name": "Computer Science"},
        {"code": "ESCSEEBSE", "slug": "computer-systems-engineering", "name": "Computer Systems Engineering"},
        {"code": "ASPGSPPBS", "slug": "psychology", "name": "Psychology"},
    ]
    path = tmp_path / "programs.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(programs, "DATA_PATH", path)

    results = programs.search_programs("computer sys")
    assert results[0]["code"] == "ESCSEEBSE"
    results = programs.search_programs("psychology")
    assert results[0]["code"] == "ASPGSPPBS"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_programs.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the module**

```python
# src/collagent/asu/programs.py
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "asu_programs.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
LIST_URL = "https://degrees.apps.asu.edu/bachelors/major-list/interest-area/{n:02d}"
MAJOR_HREF = re.compile(r"^/bachelors/major/ASU00/([A-Z0-9]+)/([a-z0-9-]+)$")


def parse_major_links(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, dict] = {}
    for a in soup.find_all("a", href=True):
        m = MAJOR_HREF.match(a["href"])
        if not m:
            continue
        code, slug = m.groups()
        name = a.get_text(strip=True)
        if name and code not in found:
            found[code] = {"code": code, "slug": slug, "name": name}
    return list(found.values())


def fetch_all_programs() -> list[dict]:
    found: dict[str, dict] = {}
    with httpx.Client(headers=UA, timeout=30, follow_redirects=True) as client:
        for n in range(1, 16):
            resp = client.get(LIST_URL.format(n=n))
            if resp.status_code != 200:
                continue
            for p in parse_major_links(resp.text):
                found.setdefault(p["code"], p)
    return sorted(found.values(), key=lambda p: p["name"])


def load_programs() -> list[dict]:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def search_programs(query: str, limit: int = 10) -> list[dict]:
    q = query.lower().strip()

    def score(p: dict) -> float:
        name = p["name"].lower()
        if q in name:
            return 1.0 + len(q) / len(name)
        return SequenceMatcher(None, q, name).ratio()

    return sorted(load_programs(), key=score, reverse=True)[:limit]
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_programs.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Write and run the seed script**

```python
# scripts/seed_programs.py
"""One-shot: crawl ASU interest-area listings into data/asu_programs.json."""
import json

from collagent.asu.programs import DATA_PATH, fetch_all_programs

if __name__ == "__main__":
    programs = fetch_all_programs()
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(programs, indent=1), encoding="utf-8")
    print(f"wrote {len(programs)} programs to {DATA_PATH}")
```

Run: `uv run python scripts/seed_programs.py`
Expected: `wrote N programs to ...` with N in the hundreds (ASU has 400+ undergrad programs). **If N < 100 or names look empty:** the anchor text on listing pages may not be the program name (links could wrap cards). Open one fetched listing page, find the element carrying the program title near the link, and adjust `parse_major_links` (e.g. climb to the parent card and read its heading) — keep the unit test in sync with the real structure.

Sanity-check: `python -c "import json;d=json.load(open('data/asu_programs.json'));print([p for p in d if p['code']=='ESCSEBS'])"`
Expected: Computer Science entry present.

- [ ] **Step 6: Add the search endpoint**

```python
# src/collagent/api/routes/programs.py
from fastapi import APIRouter, Depends, Query

from collagent.api.auth import get_current_user_id
from collagent.asu.programs import search_programs

router = APIRouter(prefix="/api/programs", tags=["programs"])


@router.get("/search")
def search(q: str = Query(min_length=2), user_id: str = Depends(get_current_user_id)):
    return search_programs(q)
```

In `src/collagent/api/main.py`, add `programs` to the routes import and `app.include_router(programs.router)`.

- [ ] **Step 7: Add endpoint test and run all tests**

Append to `tests/test_programs.py`:

```python
def test_search_endpoint(client, monkeypatch):
    monkeypatch.setattr(
        "collagent.api.routes.programs.search_programs",
        lambda q: [{"code": "ESCSEBS", "slug": "computer-science", "name": "Computer Science"}],
    )
    res = client.get("/api/programs/search?q=computer")
    assert res.status_code == 200 and res.json()[0]["code"] == "ESCSEBS"
```

Run: `uv run pytest -v`
Expected: PASS (all)

- [ ] **Step 8: Commit**

```bash
git add src/collagent/asu/ scripts/seed_programs.py data/asu_programs.json src/collagent/api/routes/programs.py src/collagent/api/main.py tests/test_programs.py
git commit -m "feat: ASU program catalog seed, fuzzy search, and endpoint"
```

---

### Task 7: Major map — Playwright render + LLM extraction

**Files:**
- Create: `src/collagent/asu/majormap.py`, `scripts/capture_roadmap_fixture.py`
- Create (generated): `tests/fixtures/roadmap_escsebs_2025.txt`
- Modify: `src/collagent/graph.py` (extract `get_model()`)
- Test: `tests/test_majormap.py`

- [ ] **Step 1: Install Playwright chromium**

Run: `uv run playwright install chromium`
Expected: downloads chromium without error.

- [ ] **Step 2: Refactor model construction in `graph.py`**

In `src/collagent/graph.py`, replace the module-level model construction (currently `model = ChatOpenAI(...)` around lines 34–41) with:

```python
def get_model() -> ChatOpenAI:
    return ChatOpenAI(
        api_key=_env("OPENAI_API_KEY", "LLM_API_KEY"),
        base_url=_env("OPENAI_BASE_URL", default="https://openai.rc.asu.edu/v1"),
        model=_env("MODEL_NAME", default="qwen3-30b-a3b-instruct-2507"),
        temperature=float(_env("TEMPERATURE", default="0.0")),
        streaming=True,
    )


model = get_model()
model_with_tools = model.bind_tools(_tools)
```

Run: `uv run pytest -v` — Expected: PASS (no behavior change). Then run `uv run collagent run`, send one message ("hi"), confirm the CLI still answers, and exit.

- [ ] **Step 3: Implement render + extraction module**

```python
# src/collagent/asu/majormap.py
from pydantic import BaseModel, Field

from collagent.graph import get_model

ROADMAP_URL = "https://webapp4.asu.edu/programs/t5/roadmaps/ASU00/{code}/null/ALL/{year}"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


class ExtractedCourse(BaseModel):
    term_number: int = Field(description="Term/semester number on the map, 1-8")
    course_code: str | None = Field(
        default=None, description='Catalog code like "CSE 110"; null for non-course requirements'
    )
    title: str = Field(description="Course or requirement title")
    credits: float | None = Field(default=None, description="Credit hours")
    requirement_note: str | None = Field(
        default=None, description='Notes like "Critical course" or "General Studies: HU"'
    )


class ExtractedMajorMap(BaseModel):
    program_name: str
    courses: list[ExtractedCourse]


_EXTRACT_PROMPT = """You are given the visible text of an ASU major map (degree roadmap) page.
Extract every course and requirement row into structured data.

Rules:
- term_number: the term/semester block the row appears under (Term 1 = 1, ... Term 8 = 8).
- course_code: the catalog code (e.g. "CSE 110", "MAT 265"). If the row is a generic
  requirement (e.g. "Humanities, Arts and Design (HU)", "Elective"), set it to null.
- title: the course/requirement name without the code.
- credits: the credit hours number for the row, if shown.
- requirement_note: flags like "Critical course", General Studies codes, or "Minimum 2.00 GPA" notes.
- Include electives and general-studies placeholder rows. Do not invent rows.
"""


def render_roadmap_text(code: str, year: str) -> str:
    from playwright.sync_api import sync_playwright

    url = ROADMAP_URL.format(code=code, year=year)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto(url, wait_until="networkidle", timeout=60_000)
        text = page.inner_text("#roadmap_middle_section")
        browser.close()
    return text


def extract_major_map(roadmap_text: str) -> ExtractedMajorMap:
    llm = get_model().with_structured_output(ExtractedMajorMap)
    return llm.invoke(
        [("system", _EXTRACT_PROMPT), ("user", roadmap_text)]
    )


def build_major_map(code: str, year: str) -> ExtractedMajorMap:
    return extract_major_map(render_roadmap_text(code, year))
```

> **Note:** `render_roadmap_text` is synchronous (Playwright sync API). API routes that call it MUST be plain `def` (not `async def`) so FastAPI runs them in a threadpool.

- [ ] **Step 4: Capture the real fixture**

```python
# scripts/capture_roadmap_fixture.py
"""Capture rendered roadmap text for tests. Run once (network + browser required)."""
from pathlib import Path

from collagent.asu.majormap import render_roadmap_text

OUT = Path("tests/fixtures/roadmap_escsebs_2025.txt")

if __name__ == "__main__":
    text = render_roadmap_text("ESCSEBS", "2025")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {len(text)} chars to {OUT}")
```

Run: `uv run python scripts/capture_roadmap_fixture.py`
Expected: several thousand chars written. Verify courses are present: `grep -c "CSE" tests/fixtures/roadmap_escsebs_2025.txt` → Expected: > 5.
**If the inner_text is empty or has no courses:** the data may load after `networkidle`; in `render_roadmap_text` add `page.wait_for_selector("text=/[A-Z]{3} [0-9]{3}/", timeout=30_000)` before reading, and retry. If the selector `#roadmap_middle_section` is missing, fall back to `page.inner_text("body")`.

- [ ] **Step 5: Write tests (unit + gated integration)**

```python
# tests/test_majormap.py
import os
from pathlib import Path

import pytest

from collagent.asu.majormap import ExtractedMajorMap, extract_major_map

FIXTURE = Path("tests/fixtures/roadmap_escsebs_2025.txt")


def test_extracted_schema_round_trip():
    m = ExtractedMajorMap(
        program_name="Computer Science, BS",
        courses=[{"term_number": 1, "title": "Programming", "course_code": "CSE 110"}],
    )
    assert m.courses[0].credits is None and m.courses[0].term_number == 1


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") and not os.getenv("LLM_API_KEY"),
    reason="integration: needs LLM key",
)
def test_extraction_on_real_fixture():
    result = extract_major_map(FIXTURE.read_text(encoding="utf-8"))
    assert len(result.courses) >= 20
    codes = {c.course_code for c in result.courses if c.course_code}
    assert "CSE 110" in codes
    assert {c.term_number for c in result.courses} >= {1, 2, 3, 4}
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_majormap.py -v`
Expected: schema test PASS; integration test PASS (with key set; takes ~30-60s) or SKIP without key. Run the integration test at least once with the key before committing.

- [ ] **Step 7: Commit**

```bash
git add src/collagent/asu/majormap.py scripts/capture_roadmap_fixture.py tests/fixtures/ tests/test_majormap.py src/collagent/graph.py
git commit -m "feat: major map playwright render + LLM structured extraction"
```

---

### Task 8: Major map API routes

**Files:**
- Create: `src/collagent/api/routes/majormap.py`
- Modify: `src/collagent/api/main.py`
- Test: `tests/test_api_majormap.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_api_majormap.py
from collagent.api.routes import majormap as mm_routes
from collagent.asu.majormap import ExtractedCourse, ExtractedMajorMap
from collagent.models import MajorMapCourse
from tests.conftest import TEST_USER

COURSE = MajorMapCourse(
    id="c1", user_id=TEST_USER, term_number=1, course_code="CSE 110",
    title="Programming", status="remaining",
)


def test_get_major_map(client, monkeypatch):
    monkeypatch.setattr(mm_routes.db, "get_major_map_courses", lambda uid: [COURSE])
    res = client.get("/api/major-map")
    assert res.status_code == 200 and res.json()[0]["course_code"] == "CSE 110"


def test_generate_major_map(client, monkeypatch):
    extracted = ExtractedMajorMap(
        program_name="Computer Science, BS",
        courses=[ExtractedCourse(term_number=1, course_code="CSE 110", title="Programming")],
    )
    monkeypatch.setattr(mm_routes, "build_major_map", lambda code, year: extracted)
    captured = {}

    def fake_replace(uid, rows):
        captured["rows"] = rows
        return [COURSE]

    monkeypatch.setattr(mm_routes.db, "replace_major_map_courses", fake_replace)
    res = client.post("/api/major-map/generate", json={"acad_plan_code": "ESCSEBS", "catalog_year": "2025"})
    assert res.status_code == 200
    assert captured["rows"][0]["course_code"] == "CSE 110"
    assert captured["rows"][0]["sort_order"] == 0


def test_update_statuses(client, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        mm_routes.db, "update_course_statuses",
        lambda uid, updates: captured.setdefault("updates", updates),
    )
    res = client.put("/api/major-map/statuses", json={"updates": [{"id": "c1", "status": "taken"}]})
    assert res.status_code == 200
    assert captured["updates"] == [("c1", "taken")]
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_api_majormap.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement routes**

```python
# src/collagent/api/routes/majormap.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from collagent import db
from collagent.api.auth import get_current_user_id
from collagent.asu.majormap import build_major_map
from collagent.models import CourseStatus, MajorMapCourse

router = APIRouter(prefix="/api/major-map", tags=["major-map"])


class GenerateRequest(BaseModel):
    acad_plan_code: str
    catalog_year: str


class StatusUpdate(BaseModel):
    id: str
    status: CourseStatus


class StatusUpdateRequest(BaseModel):
    updates: list[StatusUpdate]


@router.get("", response_model=list[MajorMapCourse])
def read_major_map(user_id: str = Depends(get_current_user_id)):
    return db.get_major_map_courses(user_id)


# Plain `def` on purpose: build_major_map runs sync Playwright; FastAPI threadpools it.
@router.post("/generate", response_model=list[MajorMapCourse])
def generate(req: GenerateRequest, user_id: str = Depends(get_current_user_id)):
    extracted = build_major_map(req.acad_plan_code, req.catalog_year)
    rows = [
        {
            "term_number": c.term_number,
            "course_code": c.course_code,
            "title": c.title,
            "credits": c.credits,
            "requirement_note": c.requirement_note,
            "status": "remaining",
            "sort_order": i,
        }
        for i, c in enumerate(extracted.courses)
    ]
    return db.replace_major_map_courses(user_id, rows)


@router.put("/statuses")
def update_statuses(req: StatusUpdateRequest, user_id: str = Depends(get_current_user_id)):
    db.update_course_statuses(user_id, [(u.id, u.status) for u in req.updates])
    return {"ok": True}
```

In `src/collagent/api/main.py`, import `majormap` alongside the other routes and add `app.include_router(majormap.router)`.

- [ ] **Step 4: Run all tests**

Run: `uv run pytest -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add src/collagent/api/routes/majormap.py src/collagent/api/main.py tests/test_api_majormap.py
git commit -m "feat: major map generate/read/status API routes"
```

---

### Task 9: Profile-aware agent — system prompt, profile tools, graph refactor

**Files:**
- Create: `src/collagent/prompts.py`, `src/collagent/profile_tools.py`
- Modify: `src/collagent/graph.py`
- Test: `tests/test_prompts.py`, `tests/test_profile_tools.py`

- [ ] **Step 1: Write failing prompt tests**

```python
# tests/test_prompts.py
from collagent.models import MajorMapCourse, Profile
from collagent.prompts import build_system_prompt

PROFILE = Profile(
    id="u1", email="a@asu.edu", full_name="Vihaan", major_name="Computer Systems Engineering",
    academic_year="junior", interests=["FPGAs", "hardware acceleration"], goals="Work with FPGAs",
)
COURSES = [
    MajorMapCourse(id="c1", user_id="u1", term_number=1, course_code="CSE 110", title="Programming", status="taken"),
    MajorMapCourse(id="c2", user_id="u1", term_number=5, course_code="CSE 420", title="Computer Architecture", status="remaining"),
]


def test_prompt_includes_profile_facts():
    prompt = build_system_prompt(PROFILE, COURSES)
    assert "Vihaan" in prompt
    assert "Computer Systems Engineering" in prompt
    assert "FPGAs" in prompt
    assert "junior" in prompt


def test_prompt_summarizes_major_map():
    prompt = build_system_prompt(PROFILE, COURSES)
    assert "1 taken" in prompt and "1 remaining" in prompt
    assert "CSE 420" in prompt


def test_prompt_handles_empty_profile():
    prompt = build_system_prompt(Profile(id="u1", email="a@asu.edu"), [])
    assert "has not completed onboarding" in prompt
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_prompts.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement prompts**

```python
# src/collagent/prompts.py
from collagent.models import MajorMapCourse, Profile

_BASE = """You are Collagent, a proactive personal assistant and advisor for an ASU student.
You work for the student: be concrete, helpful, and grounded in their actual context below.
When the student tells you something new about themselves (interests, clubs, goals, course
progress), persist it using your profile tools — never just acknowledge it.
"""


def _format_major_map(courses: list[MajorMapCourse]) -> str:
    if not courses:
        return "Major map: not set up yet."
    taken = sum(1 for c in courses if c.status == "taken")
    in_progress = sum(1 for c in courses if c.status == "in_progress")
    remaining = [c for c in courses if c.status == "remaining"]
    lines = [
        f"Major map progress: {taken} taken, {in_progress} in progress, {len(remaining)} remaining."
    ]
    if remaining:
        sample = ", ".join(
            f"{c.course_code or c.title}" for c in remaining[:15]
        )
        lines.append(f"Remaining requirements include: {sample}")
    return "\n".join(lines)


def build_system_prompt(profile: Profile | None, courses: list[MajorMapCourse]) -> str:
    if profile is None or not profile.onboarded and not profile.major_name:
        return _BASE + "\nThe student has not completed onboarding yet; encourage them to."

    parts = [_BASE, "Student context:"]
    if profile.full_name:
        parts.append(f"- Name: {profile.full_name}")
    if profile.major_name:
        parts.append(f"- Major: {profile.major_name}")
    if profile.academic_year:
        parts.append(f"- Year: {profile.academic_year}")
    if profile.interests:
        parts.append(f"- Interests: {', '.join(profile.interests)}")
    if profile.goals:
        parts.append(f"- Goals: {profile.goals}")
    if profile.clubs:
        parts.append(f"- Clubs: {', '.join(profile.clubs)}")
    if profile.projects:
        parts.append(f"- Projects: {profile.projects}")
    parts.append(_format_major_map(courses))
    return "\n".join(parts)
```

- [ ] **Step 4: Run prompt tests**

Run: `uv run pytest tests/test_prompts.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Write failing profile-tool tests**

```python
# tests/test_profile_tools.py
from collagent import profile_tools
from collagent.models import MajorMapCourse


def test_update_profile_tool_writes_structured_fields(monkeypatch):
    captured = {}

    def fake_update(uid, update):
        captured["uid"] = uid
        captured["fields"] = update.model_dump(exclude_unset=True)
        return None

    monkeypatch.setattr(profile_tools.db, "update_profile", fake_update)
    tools = {t.name: t for t in profile_tools.make_profile_tools("u1")}
    result = tools["update_profile"].invoke({"interests": ["FPGAs"], "goals": "RTL design"})
    assert captured["uid"] == "u1"
    assert captured["fields"] == {"interests": ["FPGAs"], "goals": "RTL design"}
    assert "updated" in result.lower()


def test_set_course_status_matches_by_code(monkeypatch):
    course = MajorMapCourse(
        id="c9", user_id="u1", term_number=3, course_code="CSE 230",
        title="Assembly", status="remaining",
    )
    monkeypatch.setattr(profile_tools.db, "get_major_map_courses", lambda uid: [course])
    captured = {}
    monkeypatch.setattr(
        profile_tools.db, "update_course_statuses",
        lambda uid, updates: captured.setdefault("updates", updates),
    )
    tools = {t.name: t for t in profile_tools.make_profile_tools("u1")}
    result = tools["set_course_status"].invoke({"course_code": "cse 230", "status": "taken"})
    assert captured["updates"] == [("c9", "taken")]
    assert "CSE 230" in result


def test_set_course_status_unknown_code(monkeypatch):
    monkeypatch.setattr(profile_tools.db, "get_major_map_courses", lambda uid: [])
    tools = {t.name: t for t in profile_tools.make_profile_tools("u1")}
    result = tools["set_course_status"].invoke({"course_code": "XYZ 999", "status": "taken"})
    assert "not found" in result.lower()
```

- [ ] **Step 6: Run to verify failure**

Run: `uv run pytest tests/test_profile_tools.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 7: Implement profile tools**

```python
# src/collagent/profile_tools.py
"""Per-user tool factory: the agent edits the profile only through these typed tools."""
from langchain.tools import tool

from collagent import db
from collagent.models import AcademicYear, CourseStatus, ProfileUpdate


def make_profile_tools(user_id: str) -> list:
    @tool("update_profile")
    def update_profile(
        full_name: str | None = None,
        major_name: str | None = None,
        academic_year: AcademicYear | None = None,
        interests: list[str] | None = None,
        goals: str | None = None,
        clubs: list[str] | None = None,
        projects: str | None = None,
    ) -> str:
        """Update the student's profile. Only pass fields the student explicitly
        stated or confirmed. interests/clubs REPLACE the stored list, so include
        existing values plus the new ones when adding."""
        fields = {
            k: v
            for k, v in dict(
                full_name=full_name, major_name=major_name, academic_year=academic_year,
                interests=interests, goals=goals, clubs=clubs, projects=projects,
            ).items()
            if v is not None
        }
        if not fields:
            return "No fields provided; nothing updated."
        db.update_profile(user_id, ProfileUpdate(**fields))
        return f"Profile updated: {', '.join(fields)}."

    @tool("set_course_status")
    def set_course_status(course_code: str, status: CourseStatus) -> str:
        """Mark a major-map course as taken, in_progress, or remaining.
        course_code is the catalog code, e.g. 'CSE 110'."""
        courses = db.get_major_map_courses(user_id)
        normalized = course_code.upper().replace("  ", " ").strip()
        match = next((c for c in courses if (c.course_code or "").upper() == normalized), None)
        if match is None:
            return f"Course '{course_code}' not found on the major map."
        db.update_course_statuses(user_id, [(match.id, status)])
        return f"{match.course_code} marked as {status}."

    return [update_profile, set_course_status]
```

- [ ] **Step 8: Run profile-tool tests**

Run: `uv run pytest tests/test_profile_tools.py -v`
Expected: PASS (3 tests)

- [ ] **Step 9: Refactor `create_graph` to accept prompt + extra tools**

In `src/collagent/graph.py`, replace the module-level `llm_node` / `route_after_llm` / `create_graph` block with a parameterized version (CLI behavior unchanged via defaults):

```python
def create_graph(checkpointer=None, system_prompt: str = _SYSTEM_PROMPT, extra_tools: tuple = ()):
    tools = [*_tools, *extra_tools]
    bound = get_model().bind_tools(tools)

    def llm_node(state: AgentState) -> AgentState:
        response = bound.invoke([SystemMessage(content=system_prompt)] + state["messages"])
        return {
            "messages": [response],
            "llm_calls": state.get("llm_calls", 0) + 1,
        }

    def route_after_llm(state: AgentState) -> Literal["tool_node", "__end__"]:
        if state["messages"][-1].tool_calls:
            return "tool_node"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("llm_node", llm_node)
    graph.add_node("tool_node", ToolNode(tools))
    graph.add_edge(START, "llm_node")
    graph.add_conditional_edges("llm_node", route_after_llm, ["tool_node", END])
    graph.add_edge("tool_node", "llm_node")
    return graph.compile(checkpointer=checkpointer)
```

(The old module-level `llm_node`, `route_after_llm`, and `model_with_tools` are deleted; `model = get_model()` stays for any external imports.)

- [ ] **Step 10: Verify everything still works**

Run: `uv run pytest -v` → Expected: PASS (all).
Run: `uv run collagent run`, send "hi", confirm a reply, exit.

- [ ] **Step 11: Commit**

```bash
git add src/collagent/prompts.py src/collagent/profile_tools.py src/collagent/graph.py tests/test_prompts.py tests/test_profile_tools.py
git commit -m "feat: profile-aware system prompt, typed profile tools, parameterized graph"
```

---

### Task 10: Chat SSE endpoint

**Files:**
- Modify: `src/collagent/graph.py` (extract `stream_events` from `stream_turn`)
- Create: `src/collagent/api/routes/chat.py`
- Modify: `src/collagent/api/main.py`
- Test: `tests/test_chat_stream.py`

- [ ] **Step 1: Write failing tests for the event generator + SSE formatting**

```python
# tests/test_chat_stream.py
import json

from collagent.api.routes.chat import sse_format


def test_sse_format():
    line = sse_format({"type": "token", "content": "hi"})
    assert line == 'data: {"type": "token", "content": "hi"}\n\n'
    assert json.loads(line[len("data: "):].strip()) == {"type": "token", "content": "hi"}
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_chat_stream.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Refactor `stream_turn` into `stream_events` + printer**

In `src/collagent/graph.py`, replace the existing `stream_turn` with a generator that yields typed event dicts, plus a thin CLI printer that consumes it. The chunk-handling logic is copied from the current `stream_turn` — same stream call, same guards:

```python
def stream_events(graph, user_input: str, config: dict):
    """Yield {'type': 'token'|'tool'|'tool_result', ...} events for one turn."""
    for chunk in graph.stream(
        {"messages": [HumanMessage(content=user_input)], "llm_calls": 0},
        config=config,
        stream_mode="messages",
        version="v2",
    ):
        if chunk["type"] != "messages":
            continue

        message_chunk, _ = chunk["data"]
        tool_calls = getattr(message_chunk, "tool_calls", None) or []
        message_type = getattr(message_chunk, "type", None)

        for call in tool_calls:
            name = call.get("name", "") if isinstance(call, dict) else ""
            args = call.get("args", {}) if isinstance(call, dict) else {}
            if name:  # skip partial chunks that only carry args
                yield {"type": "tool", "name": name, "args": args}

        if message_type == "tool":
            yield {
                "type": "tool_result",
                "name": getattr(message_chunk, "name", "tool"),
                "content": message_chunk.content or "",
            }
            continue

        content = message_chunk.content
        if content and not content.isspace():
            yield {"type": "token", "content": content}


def stream_turn(graph, user_input: str, config: dict) -> None:
    """CLI printer over stream_events (keeps `collagent run` behavior)."""
    in_model_text = False
    for event in stream_events(graph, user_input, config):
        if event["type"] == "tool":
            if in_model_text:
                print()
                in_model_text = False
            print(f"  [tool] {event['name']} {event['args']}")
        elif event["type"] == "tool_result":
            if in_model_text:
                print()
                in_model_text = False
            print(f"  [result] {event['name']}: {event['content']}")
        else:
            if not in_model_text:
                print("COLLAGENT: ", end="", flush=True)
            print(event["content"], end="", flush=True)
            in_model_text = True
    if in_model_text:
        print()
```

- [ ] **Step 4: Implement the chat route**

```python
# src/collagent/api/routes/chat.py
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel

from collagent import db
from collagent.api.auth import get_current_user_id
from collagent.graph import create_graph, stream_events
from collagent.profile_tools import make_profile_tools
from collagent.prompts import build_system_prompt

router = APIRouter(prefix="/api/chat", tags=["chat"])

# In-process conversation memory. PoC tradeoff: history is lost on restart and
# does not scale past one process — swap for a Postgres checkpointer post-PoC.
_CHECKPOINTER = MemorySaver()


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"


def sse_format(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


# Plain `def`: graph streaming is sync; FastAPI threadpools it.
@router.post("")
def chat(req: ChatRequest, user_id: str = Depends(get_current_user_id)):
    profile = db.get_profile(user_id)
    courses = db.get_major_map_courses(user_id)
    agent = create_graph(
        checkpointer=_CHECKPOINTER,
        system_prompt=build_system_prompt(profile, courses),
        extra_tools=tuple(make_profile_tools(user_id)),
    )
    config = {"configurable": {"thread_id": f"{user_id}:{req.thread_id}"}}

    def gen():
        for event in stream_events(agent, req.message, config):
            yield sse_format(event)
        yield sse_format({"type": "done"})

    return StreamingResponse(gen(), media_type="text/event-stream")
```

In `src/collagent/api/main.py`, import `chat` and add `app.include_router(chat.router)`.

- [ ] **Step 5: Run tests + CLI regression**

Run: `uv run pytest -v` → Expected: PASS (all).
Run: `uv run collagent run`, send "what is 2+2" (exercises the calculator tool path through the refactored printer), confirm sensible output, exit.

- [ ] **Step 6: Manual SSE smoke test**

Start the server: `uv run uvicorn collagent.api.main:app --port 8000`.
Mint a test token (PowerShell, single line):
`uv run python -c "import jwt,time; from collagent.config import settings; print(jwt.encode({'sub':'<a-real-user-uuid-from-supabase>','aud':'authenticated','exp':int(time.time())+3600}, settings.supabase_jwt_secret, algorithm='HS256'))"`

(Use a real user id: create one via Supabase dashboard → Authentication → Add user, which fires the profile trigger.)

`curl -N -X POST http://localhost:8000/api/chat -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" -d "{\"message\": \"hi\"}"`
Expected: `data: {"type": "token", ...}` lines streaming, ending with `data: {"type": "done"}`.

- [ ] **Step 7: Commit**

```bash
git add src/collagent/graph.py src/collagent/api/routes/chat.py src/collagent/api/main.py tests/test_chat_stream.py
git commit -m "feat: SSE chat endpoint with profile-aware agent"
```

---

### Task 11: Frontend scaffold + Supabase auth

**Files:**
- Create: `frontend/` (Next.js app), `frontend/lib/supabase/client.ts`, `frontend/lib/supabase/server.ts`, `frontend/middleware.ts`, `frontend/app/login/page.tsx`, `frontend/app/auth/callback/route.ts`, `frontend/.env.local.example`
- Modify: `frontend/app/layout.tsx`

- [ ] **Step 1: Scaffold the app**

From repo root:
```bash
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir=false --import-alias "@/*" --use-npm --yes
cd frontend
npm install @supabase/supabase-js @supabase/ssr
```
Expected: scaffold completes, `npm run build` passes.

- [ ] **Step 2: Env files**

Create `frontend/.env.local.example` (and a real `.env.local` with actual values — git-ignored by the scaffold):

```
NEXT_PUBLIC_SUPABASE_URL=https://YOUR-REF.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
NEXT_PUBLIC_API_URL=http://localhost:8000
```

- [ ] **Step 3: Supabase clients + middleware**

```ts
// frontend/lib/supabase/client.ts
import { createBrowserClient } from "@supabase/ssr";

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
}
```

```ts
// frontend/lib/supabase/server.ts
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

export async function createClient() {
  const cookieStore = await cookies();
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => cookieStore.getAll(),
        setAll: (cookiesToSet) => {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options)
            );
          } catch {
            // called from a Server Component; middleware refreshes sessions
          }
        },
      },
    }
  );
}
```

```ts
// frontend/middleware.ts
import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

export async function middleware(request: NextRequest) {
  let response = NextResponse.next({ request });
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => request.cookies.getAll(),
        setAll: (cookiesToSet) => {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          response = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  const { data: { user } } = await supabase.auth.getUser();
  const isPublic =
    request.nextUrl.pathname.startsWith("/login") ||
    request.nextUrl.pathname.startsWith("/auth");

  if (!user && !isPublic) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|ico)$).*)"],
};
```

- [ ] **Step 4: Login page + auth callback**

```tsx
// frontend/app/login/page.tsx
"use client";
import { useState } from "react";
import { createClient } from "@/lib/supabase/client";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function sendLink(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const supabase = createClient();
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
    });
    if (error) setError(error.message);
    else setSent(true);
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-sm space-y-6">
        <div>
          <h1 className="text-2xl font-semibold">Collagent</h1>
          <p className="text-sm text-gray-500">Your personal interface to ASU.</p>
        </div>
        {sent ? (
          <p className="rounded-md bg-green-50 p-4 text-sm text-green-800">
            Check your email for a sign-in link.
          </p>
        ) : (
          <form onSubmit={sendLink} className="space-y-3">
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@asu.edu"
              className="w-full rounded-md border px-3 py-2 text-sm"
            />
            <button
              type="submit"
              className="w-full rounded-md bg-black px-3 py-2 text-sm font-medium text-white"
            >
              Send sign-in link
            </button>
            {error && <p className="text-sm text-red-600">{error}</p>}
          </form>
        )}
      </div>
    </main>
  );
}
```

```ts
// frontend/app/auth/callback/route.ts
import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  if (code) {
    const supabase = await createClient();
    await supabase.auth.exchangeCodeForSession(code);
  }
  return NextResponse.redirect(`${origin}/`);
}
```

- [ ] **Step 5: Verify build + manual smoke**

Run: `npm run build` → Expected: compiles with no type errors.
Run: `npm run dev`, open http://localhost:3000 → Expected: redirected to `/login`. Enter your email, receive the magic link (Supabase default SMTP), click it, land on `/` (default Next page for now).

- [ ] **Step 6: Commit**

```bash
cd ..
git add frontend/
git commit -m "feat: next.js scaffold with supabase magic-link auth"
```

---

### Task 12: API client + onboarding flow

**Files:**
- Create: `frontend/lib/api.ts`, `frontend/lib/types.ts`, `frontend/app/onboarding/page.tsx`, `frontend/components/MajorMapEditor.tsx`

- [ ] **Step 1: Shared types + API client**

```ts
// frontend/lib/types.ts
export type CourseStatus = "taken" | "in_progress" | "remaining";

export interface Profile {
  id: string;
  email: string;
  full_name: string | null;
  major_name: string | null;
  acad_plan_code: string | null;
  catalog_year: string | null;
  academic_year: string | null;
  interests: string[];
  goals: string | null;
  clubs: string[];
  projects: string | null;
  onboarded: boolean;
}

export interface MajorMapCourse {
  id: string;
  term_number: number;
  course_code: string | null;
  title: string;
  credits: number | null;
  requirement_note: string | null;
  status: CourseStatus;
  sort_order: number;
}

export interface ProgramHit {
  code: string;
  slug: string;
  name: string;
}
```

```ts
// frontend/lib/api.ts
import { createClient } from "@/lib/supabase/client";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function getAccessToken(): Promise<string | null> {
  const supabase = createClient();
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await getAccessToken();
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...init.headers,
    },
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res;
}

export const api = {
  get: (path: string) => apiFetch(path).then((r) => r.json()),
  put: (path: string, body: unknown) =>
    apiFetch(path, { method: "PUT", body: JSON.stringify(body) }).then((r) => r.json()),
  post: (path: string, body: unknown) =>
    apiFetch(path, { method: "POST", body: JSON.stringify(body) }).then((r) => r.json()),
};
```

- [ ] **Step 2: Major map editor component (shared by onboarding + profile)**

```tsx
// frontend/components/MajorMapEditor.tsx
"use client";
import type { CourseStatus, MajorMapCourse } from "@/lib/types";

const NEXT_STATUS: Record<CourseStatus, CourseStatus> = {
  remaining: "taken",
  taken: "in_progress",
  in_progress: "remaining",
};

const STATUS_STYLE: Record<CourseStatus, string> = {
  taken: "bg-green-100 text-green-800 border-green-300",
  in_progress: "bg-amber-100 text-amber-800 border-amber-300",
  remaining: "bg-gray-50 text-gray-600 border-gray-200",
};

export default function MajorMapEditor({
  courses,
  onToggle,
}: {
  courses: MajorMapCourse[];
  onToggle: (id: string, status: CourseStatus) => void;
}) {
  const terms = [...new Set(courses.map((c) => c.term_number))].sort((a, b) => a - b);
  return (
    <div className="space-y-6">
      <p className="text-sm text-gray-500">
        Click a course to cycle its status: remaining → taken → in progress.
      </p>
      {terms.map((term) => (
        <section key={term}>
          <h3 className="mb-2 text-sm font-semibold text-gray-700">Term {term}</h3>
          <ul className="grid gap-2 sm:grid-cols-2">
            {courses
              .filter((c) => c.term_number === term)
              .map((c) => (
                <li key={c.id}>
                  <button
                    onClick={() => onToggle(c.id, NEXT_STATUS[c.status])}
                    className={`w-full rounded-md border px-3 py-2 text-left text-sm ${STATUS_STYLE[c.status]}`}
                  >
                    <span className="font-medium">{c.course_code ?? "—"}</span> {c.title}
                    <span className="float-right text-xs">{c.status.replace("_", " ")}</span>
                  </button>
                </li>
              ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Onboarding page (3 steps: basics → generate map → confirm)**

```tsx
// frontend/app/onboarding/page.tsx
"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { CourseStatus, MajorMapCourse, ProgramHit } from "@/lib/types";
import MajorMapEditor from "@/components/MajorMapEditor";

const YEARS = ["freshman", "sophomore", "junior", "senior", "graduate"];

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [error, setError] = useState<string | null>(null);

  // step 1 state
  const [fullName, setFullName] = useState("");
  const [year, setYear] = useState("freshman");
  const [interests, setInterests] = useState("");
  const [goals, setGoals] = useState("");
  const [clubs, setClubs] = useState("");
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<ProgramHit[]>([]);
  const [program, setProgram] = useState<ProgramHit | null>(null);

  // step 2/3 state
  const [generating, setGenerating] = useState(false);
  const [courses, setCourses] = useState<MajorMapCourse[]>([]);

  useEffect(() => {
    if (query.length < 2 || program) return;
    const t = setTimeout(() => {
      api.get(`/api/programs/search?q=${encodeURIComponent(query)}`).then(setHits).catch(() => {});
    }, 250);
    return () => clearTimeout(t);
  }, [query, program]);

  async function saveBasics(e: React.FormEvent) {
    e.preventDefault();
    if (!program) return setError("Pick your major from the search results.");
    setError(null);
    await api.put("/api/profile", {
      full_name: fullName,
      academic_year: year,
      major_name: program.name,
      acad_plan_code: program.code,
      catalog_year: "2025",
      interests: interests.split(",").map((s) => s.trim()).filter(Boolean),
      goals,
      clubs: clubs.split(",").map((s) => s.trim()).filter(Boolean),
    });
    setStep(2);
  }

  async function generateMap() {
    if (!program) return;
    setGenerating(true);
    setError(null);
    try {
      const result = await api.post("/api/major-map/generate", {
        acad_plan_code: program.code,
        catalog_year: "2025",
      });
      setCourses(result);
      setStep(3);
    } catch {
      setError("Couldn't build your major map automatically. You can retry or skip for now.");
    } finally {
      setGenerating(false);
    }
  }

  function toggleStatus(id: string, status: CourseStatus) {
    setCourses((cs) => cs.map((c) => (c.id === id ? { ...c, status } : c)));
  }

  async function finish() {
    const updates = courses
      .filter((c) => c.status !== "remaining")
      .map((c) => ({ id: c.id, status: c.status }));
    if (updates.length) await api.put("/api/major-map/statuses", { updates });
    await api.put("/api/profile", { onboarded: true });
    router.push("/");
  }

  return (
    <main className="mx-auto max-w-2xl space-y-6 p-6">
      <h1 className="text-2xl font-semibold">Set up Collagent</h1>
      <p className="text-sm text-gray-500">Step {step} of 3</p>
      {error && <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>}

      {step === 1 && (
        <form onSubmit={saveBasics} className="space-y-4">
          <input value={fullName} onChange={(e) => setFullName(e.target.value)} required
            placeholder="Full name" className="w-full rounded-md border px-3 py-2 text-sm" />
          <select value={year} onChange={(e) => setYear(e.target.value)}
            className="w-full rounded-md border px-3 py-2 text-sm">
            {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
          <div className="relative">
            <input
              value={program ? program.name : query}
              onChange={(e) => { setProgram(null); setQuery(e.target.value); }}
              required placeholder="Search your major (e.g. Computer Science)"
              className="w-full rounded-md border px-3 py-2 text-sm"
            />
            {!program && hits.length > 0 && (
              <ul className="absolute z-10 mt-1 w-full rounded-md border bg-white shadow">
                {hits.map((h) => (
                  <li key={h.code}>
                    <button type="button" onClick={() => { setProgram(h); setHits([]); }}
                      className="w-full px-3 py-2 text-left text-sm hover:bg-gray-50">
                      {h.name}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <input value={interests} onChange={(e) => setInterests(e.target.value)}
            placeholder="Interests, comma-separated (e.g. FPGAs, robotics)"
            className="w-full rounded-md border px-3 py-2 text-sm" />
          <input value={clubs} onChange={(e) => setClubs(e.target.value)}
            placeholder="Clubs you're in, comma-separated (optional)"
            className="w-full rounded-md border px-3 py-2 text-sm" />
          <textarea value={goals} onChange={(e) => setGoals(e.target.value)}
            placeholder="What are your goals? (e.g. research, internships, grad school)"
            className="w-full rounded-md border px-3 py-2 text-sm" rows={3} />
          <button type="submit" className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white">
            Continue
          </button>
        </form>
      )}

      {step === 2 && (
        <div className="space-y-4">
          <p className="text-sm">
            Collagent will now read ASU&apos;s official major map for{" "}
            <span className="font-medium">{program?.name}</span> and build your personal
            degree map. Takes about a minute.
          </p>
          <button onClick={generateMap} disabled={generating}
            className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
            {generating ? "Building your major map…" : "Build my major map"}
          </button>
          <button onClick={finish} className="ml-3 text-sm text-gray-500 underline">
            Skip for now
          </button>
        </div>
      )}

      {step === 3 && (
        <div className="space-y-4">
          <p className="text-sm">
            Here&apos;s your major map. Mark what you&apos;ve already taken or are taking now.
          </p>
          <MajorMapEditor courses={courses} onToggle={toggleStatus} />
          <button onClick={finish} className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white">
            Finish setup
          </button>
        </div>
      )}
    </main>
  );
}
```

- [ ] **Step 4: Verify build + manual smoke**

Run: `npm run build` → Expected: no type errors.
With backend running (`uv run uvicorn collagent.api.main:app --port 8000`) and `npm run dev`: log in, visit `/onboarding`, complete step 1 (search "computer" → pick a program), run step 2 (wait for generation), toggle a few courses in step 3, finish. Verify in Supabase Table Editor: `profiles` row updated (onboarded=true), `major_map_courses` rows present with your toggled statuses.

- [ ] **Step 5: Commit**

```bash
git add frontend/
git commit -m "feat: onboarding flow with program search and agent-built major map"
```

---

### Task 13: Dashboard, chat page, profile page

**Files:**
- Create: `frontend/app/chat/page.tsx`, `frontend/app/profile/page.tsx`, `frontend/components/Nav.tsx`
- Modify: `frontend/app/page.tsx`, `frontend/app/layout.tsx`

- [ ] **Step 1: Nav + layout**

```tsx
// frontend/components/Nav.tsx
"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/chat", label: "Chat" },
  { href: "/profile", label: "Profile" },
];

export default function Nav() {
  const pathname = usePathname();
  const router = useRouter();
  if (pathname.startsWith("/login") || pathname.startsWith("/onboarding")) return null;

  async function signOut() {
    await createClient().auth.signOut();
    router.push("/login");
  }

  return (
    <nav className="flex items-center gap-4 border-b px-6 py-3">
      <span className="font-semibold">Collagent</span>
      {LINKS.map((l) => (
        <Link key={l.href} href={l.href}
          className={`text-sm ${pathname === l.href ? "font-medium" : "text-gray-500"}`}>
          {l.label}
        </Link>
      ))}
      <button onClick={signOut} className="ml-auto text-sm text-gray-500">Sign out</button>
    </nav>
  );
}
```

In `frontend/app/layout.tsx`, render `<Nav />` above `{children}` inside `<body>` (add the import; keep the scaffold's font/css setup).

- [ ] **Step 2: Dashboard (home) with onboarding redirect**

```tsx
// frontend/app/page.tsx
"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Profile } from "@/lib/types";

export default function HomePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);

  useEffect(() => {
    api.get("/api/profile")
      .then((p: Profile) => {
        if (!p.onboarded) router.replace("/onboarding");
        else setProfile(p);
      })
      .catch(() => router.replace("/login"));
  }, [router]);

  if (!profile) return <main className="p-6 text-sm text-gray-500">Loading…</main>;

  return (
    <main className="mx-auto max-w-3xl space-y-6 p-6">
      <h1 className="text-2xl font-semibold">
        Hey{profile.full_name ? `, ${profile.full_name.split(" ")[0]}` : ""} 👋
      </h1>
      <div className="rounded-lg border p-4 text-sm">
        <p className="font-medium">{profile.major_name ?? "No major set"}</p>
        <p className="text-gray-500">
          {profile.academic_year ?? ""}{profile.interests.length ? ` · ${profile.interests.join(", ")}` : ""}
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {["Events for you", "People to know"].map((title) => (
          <div key={title} className="rounded-lg border border-dashed p-4">
            <p className="text-sm font-medium">{title}</p>
            <p className="text-xs text-gray-400">Coming soon — ask in Chat meanwhile.</p>
          </div>
        ))}
      </div>
    </main>
  );
}
```

- [ ] **Step 3: Chat page with SSE streaming**

```tsx
// frontend/app/chat/page.tsx
"use client";
import { useRef, useState } from "react";
import { apiFetch } from "@/lib/api";

interface Msg {
  role: "user" | "assistant" | "tool";
  content: string;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);
    setMessages((m) => [...m, { role: "user", content: text }, { role: "assistant", content: "" }]);

    try {
      const res = await apiFetch("/api/chat", {
        method: "POST",
        body: JSON.stringify({ message: text, thread_id: "web" }),
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
          }
          bottomRef.current?.scrollIntoView({ behavior: "smooth" });
        }
      }
    } catch {
      setMessages((m) => [...m, { role: "assistant", content: "Something went wrong — try again." }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex h-[calc(100vh-57px)] max-w-2xl flex-col p-4">
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
      <form onSubmit={send} className="flex gap-2">
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
```

- [ ] **Step 4: Profile page (view/edit + major map)**

```tsx
// frontend/app/profile/page.tsx
"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CourseStatus, MajorMapCourse, Profile } from "@/lib/types";
import MajorMapEditor from "@/components/MajorMapEditor";

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [courses, setCourses] = useState<MajorMapCourse[]>([]);
  const [interests, setInterests] = useState("");
  const [clubs, setClubs] = useState("");
  const [goals, setGoals] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.get("/api/profile").then((p: Profile) => {
      setProfile(p);
      setInterests(p.interests.join(", "));
      setClubs(p.clubs.join(", "));
      setGoals(p.goals ?? "");
    });
    api.get("/api/major-map").then(setCourses);
  }, []);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    await api.put("/api/profile", {
      interests: interests.split(",").map((s) => s.trim()).filter(Boolean),
      clubs: clubs.split(",").map((s) => s.trim()).filter(Boolean),
      goals,
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  async function toggle(id: string, status: CourseStatus) {
    setCourses((cs) => cs.map((c) => (c.id === id ? { ...c, status } : c)));
    await api.put("/api/major-map/statuses", { updates: [{ id, status }] });
  }

  if (!profile) return <main className="p-6 text-sm text-gray-500">Loading…</main>;

  return (
    <main className="mx-auto max-w-2xl space-y-8 p-6">
      <section>
        <h1 className="text-xl font-semibold">{profile.full_name ?? profile.email}</h1>
        <p className="text-sm text-gray-500">
          {profile.major_name} · {profile.academic_year}
        </p>
      </section>
      <form onSubmit={save} className="space-y-3">
        <label className="block text-sm">
          Interests
          <input value={interests} onChange={(e) => setInterests(e.target.value)}
            className="mt-1 w-full rounded-md border px-3 py-2 text-sm" />
        </label>
        <label className="block text-sm">
          Clubs
          <input value={clubs} onChange={(e) => setClubs(e.target.value)}
            className="mt-1 w-full rounded-md border px-3 py-2 text-sm" />
        </label>
        <label className="block text-sm">
          Goals
          <textarea value={goals} onChange={(e) => setGoals(e.target.value)} rows={2}
            className="mt-1 w-full rounded-md border px-3 py-2 text-sm" />
        </label>
        <button type="submit" className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white">
          {saved ? "Saved ✓" : "Save"}
        </button>
      </form>
      <section>
        <h2 className="mb-3 text-lg font-semibold">Major map</h2>
        <MajorMapEditor courses={courses} onToggle={toggle} />
      </section>
    </main>
  );
}
```

- [ ] **Step 5: Verify build + manual smoke**

Run: `npm run build` → Expected: no type errors.
With both servers running: dashboard greets you by name; `/chat` streams a reply (try "mark CSE 110 as taken" — then check `/profile` shows the course green, proving the agent's typed tool wrote through); `/profile` edits persist after reload.

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "feat: dashboard, streaming chat page, profile page"
```

---

### Task 14: Docs + end-to-end smoke checklist

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Rewrite README**

```markdown
# Collagent

A proactive, personalized interface between a student and their university. ASU-first.
Vision and specs: `docs/superpowers/specs/`.

**Current state (PoC milestone 1):** web app with Supabase auth, profile +
agent-built ASU major map onboarding, and a profile-aware chat agent with
Canvas tools. CLI still available via `collagent run`.

## Stack
Next.js (frontend/) · FastAPI + LangGraph (src/collagent/) · Supabase (auth + Postgres) · Playwright (ASU data)

## Dev setup

Backend (repo root):
```sh
uv venv && uv pip install -e . --group dev
uv run playwright install chromium
cp .env.example .env   # fill in Supabase + LLM + Canvas keys
uv run uvicorn collagent.api.main:app --reload --port 8000
```

Frontend:
```sh
cd frontend
npm install
cp .env.local.example .env.local   # fill in Supabase public keys
npm run dev
```

One-time data seed (already committed, rerun to refresh):
```sh
uv run python scripts/seed_programs.py
```

Tests: `uv run pytest` (backend) · `npm run build` (frontend typecheck)
```

- [ ] **Step 2: Full end-to-end smoke checklist**

Run through, fresh browser profile, both servers up:

1. Visit `/` logged out → redirected to `/login`.
2. Magic-link sign-in with a fresh email → lands on `/` → redirected to `/onboarding` (new user, profile row auto-created by trigger).
3. Onboarding step 1: search "computer", select program, fill fields, continue.
4. Step 2: build major map (~1 min) → step 3 shows terms with courses.
5. Toggle 2-3 courses to taken → Finish → dashboard greets by first name.
6. `/chat`: "what classes do I have left?" → answer reflects the major map.
7. `/chat`: "I joined the robotics club" → `/profile` shows robotics club after reload (typed tool wrote it).
8. `uv run pytest` → all pass. `cd frontend && npm run build` → clean.

Record any failures as issues; do not ship the milestone with a failing item.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: README for milestone 1 web app"
```

---

## Out of scope for Milestone 1 (per spec phasing)
Events surface, Networking surface, curation pipeline/scheduler (APScheduler), shared index tables, RAG, email/calendar sync, deployment (Vercel/Railway) — Milestone 2+. The deployment task will be planned once M1 runs locally end-to-end.
