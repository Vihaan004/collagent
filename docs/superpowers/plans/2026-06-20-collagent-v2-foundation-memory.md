# Collagent v2 — Foundation + Agent Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lay the v2 database + model-config foundation, and ship a ChatGPT/Claude-style agent memory system (CRUD tools, system-prompt injection, a visible/deletable Profile panel).

**Architecture:** Add four v2 tables in one migration (only `user_memories` is wired up this plan; the other three are schema-ahead scaffolding for later plans). Memory follows the established per-user pattern: a Pydantic model → `db.py` repository functions (all scoped to `user_id`) → a `make_memory_tools(user_id)` tool factory bound into the chat graph → injection into the system prompt → a FastAPI route the Profile page reads/deletes from. Model provider is already env-driven via `graph.get_model()`; this plan documents the Groq/ASU profiles and pins the behavior with a test.

**Tech Stack:** Python 3.12, FastAPI, LangChain/LangGraph, Supabase (Postgres) via the Supabase MCP, pytest (`uv run pytest`), Next.js 16 + Tailwind v4 frontend.

**Source of truth:** `docs/superpowers/specs/2026-06-19-collagent-v2-dashboard-design.md` (§4 data model, §6 memory, §7 model config).

**Constraints (carry through every task):**
- **Supabase MCP only** for all DB work — project ref `qepwzwitwjhklxscrugr`. Never use any other DB tool or a second project.
- **Never touch or commit `.env` / `.env.local`; never print secrets.** (`.env.example` with placeholder values is fine and expected.)
- **Do NOT stage or touch the untracked `canvas-mcp/` directory.**
- Backend commands run via `uv` (e.g. `uv run pytest`). Commit messages end with:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- Branch for this work: `feat/v2-daily-brief` (already checked out; the spec lives there).

---

## File Structure

**Backend — created:**
- `supabase/migrations/0004_foundation.sql` — the four v2 tables + RLS.
- `src/collagent/memory_tools.py` — `make_memory_tools(user_id)` factory (remember/list_memories/update_memory/forget).
- `src/collagent/api/routes/memory.py` — `GET /api/memory`, `DELETE /api/memory/{id}`.
- `.env.example` — documents Supabase + model-provider profiles + Tavily placeholder.
- `tests/test_db_memory.py`, `tests/test_memory_tools.py`, `tests/test_api_memory.py`, `tests/test_model_config.py`, plus additions to `tests/test_prompts.py`.

**Backend — modified:**
- `src/collagent/models.py` — add `Memory`.
- `src/collagent/db.py` — add `get_memories`, `create_memory`, `update_memory`, `delete_memory`.
- `src/collagent/prompts.py` — `build_system_prompt` gains an optional `memories` arg + memory guidance in `_BASE`.
- `src/collagent/api/routes/chat.py` — load memories, inject, bind memory tools.
- `src/collagent/api/main.py` — register the memory router.

**Frontend — modified:**
- `frontend/lib/types.ts` — add `Memory`.
- `frontend/lib/api.ts` — add `del` helper.
- `frontend/app/profile/page.tsx` — "What Collagent remembers" panel.

---

## Task 1: Foundation migration (four v2 tables)

**Files:**
- Create: `supabase/migrations/0004_foundation.sql`

- [ ] **Step 1: Write the migration file**

Create `supabase/migrations/0004_foundation.sql` with exactly this content (mirrors `0003_people.sql` conventions — `gen_random_uuid()` PKs, `text[]` defaults, RLS, `auth.uid()` ownership):

```sql
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
```

- [ ] **Step 2: Apply via the Supabase MCP**

Use the Supabase MCP `apply_migration` tool (project ref `qepwzwitwjhklxscrugr`), `name: "0004_foundation"`, `query:` the full SQL above. Do not use any other DB mechanism.

- [ ] **Step 3: Verify the tables exist**

Use the Supabase MCP `execute_sql` tool with:

```sql
select table_name from information_schema.tables
where table_schema = 'public'
  and table_name in ('user_memories','news_items','calendar_items','dashboard_snapshots')
order by table_name;
```

Expected: four rows — `calendar_items`, `dashboard_snapshots`, `news_items`, `user_memories`.

- [ ] **Step 4: Commit**

```bash
git add supabase/migrations/0004_foundation.sql
git commit -m "feat: v2 foundation migration (memory, news, calendar, snapshots)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Model-provider config (Groq / ASU profiles)

`graph.get_model()` already reads `OPENAI_BASE_URL` / `OPENAI_API_KEY` / `MODEL_NAME` from the environment, so this task documents the swap and pins the behavior with a test. No code change to `get_model()`.

**Files:**
- Create: `.env.example`
- Create: `tests/test_model_config.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_model_config.py`:

```python
# tests/test_model_config.py
import collagent.graph as graph


def test_get_model_honors_env(monkeypatch):
    # Switching providers must be a config change only: get_model reads these
    # three env vars at call time and builds an OpenAI-compatible client.
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("MODEL_NAME", "llama-3.3-70b-versatile")
    m = graph.get_model()
    assert m.model_name == "llama-3.3-70b-versatile"
    assert str(m.openai_api_base) == "https://api.groq.com/openai/v1"
```

- [ ] **Step 2: Run it to verify it passes (characterization test)**

Run: `uv run pytest tests/test_model_config.py -v`
Expected: PASS. (This is a characterization test — `get_model()` already supports env overrides; the test locks that contract so a future refactor can't silently break provider-swapping.) If it FAILS, read `src/collagent/graph.py:34-41` and fix the assertion to match the real `ChatOpenAI` attribute names (`model_name`, `openai_api_base`) rather than changing `get_model`.

- [ ] **Step 3: Create `.env.example`**

Create `.env.example` (placeholders only — never copy real secrets here):

```bash
# ---- Supabase (project ref qepwzwitwjhklxscrugr) ----
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret
FRONTEND_ORIGIN=http://localhost:3000

# ---- Model provider (OpenAI-compatible; swap providers by editing these 3) ----
# dev profile — ASU endpoint (free, VPN/account-gated)
OPENAI_BASE_URL=https://openai.rc.asu.edu/v1
OPENAI_API_KEY=your-asu-key
MODEL_NAME=qwen3-30b-a3b-instruct-2507

# prod profile — Groq (free tier, publicly reachable). To use, replace the three above:
# OPENAI_BASE_URL=https://api.groq.com/openai/v1
# OPENAI_API_KEY=your-groq-key
# MODEL_NAME=llama-3.3-70b-versatile

TEMPERATURE=0.0

# ---- Tavily (news ingestion; used in a later v2 plan) ----
# TAVILY_API_KEY=your-tavily-key
```

- [ ] **Step 4: Confirm `.env.example` is tracked but real env files are not**

Run: `git status --porcelain .env.example && git check-ignore .env || echo ".env not present"`
Expected: `.env.example` shows as untracked/added; `.env` is ignored (or absent). Never `git add .env`.

- [ ] **Step 5: Commit**

```bash
git add .env.example tests/test_model_config.py
git commit -m "feat: document Groq/ASU model profiles + pin env-swap behavior

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `Memory` model

**Files:**
- Modify: `src/collagent/models.py`
- Create: `tests/test_models.py` already exists — add one test there.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_models.py`:

```python
def test_memory_model_parses_row_and_defaults():
    from collagent.models import Memory
    m = Memory(id="m1", user_id="u1", content="Prefers FPGA research")
    assert m.kind == "fact"
    assert m.created_at is None
    # tolerates extra DB columns + populated timestamps
    full = Memory(id="m1", user_id="u1", content="x", kind="goal",
                  created_at="2026-06-20T00:00:00Z", updated_at="2026-06-20T00:00:00Z",
                  extra="ignored")
    assert full.kind == "goal" and full.updated_at == "2026-06-20T00:00:00Z"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_models.py::test_memory_model_parses_row_and_defaults -v`
Expected: FAIL with `ImportError` / `cannot import name 'Memory'`.

- [ ] **Step 3: Add the model**

Append to `src/collagent/models.py`:

```python
class Memory(BaseModel):
    """A durable, user-owned fact the chat agent curates. Mirrors a user_memories row."""

    model_config = {"extra": "ignore"}

    id: str
    user_id: str
    content: str
    kind: str = "fact"
    created_at: str | None = None
    updated_at: str | None = None
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/test_models.py::test_memory_model_parses_row_and_defaults -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/collagent/models.py tests/test_models.py
git commit -m "feat: add Memory model

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Memory DB repository

**Files:**
- Modify: `src/collagent/db.py`
- Create: `tests/test_db_memory.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_db_memory.py` (mirrors `tests/test_db_people.py`'s MagicMock pattern):

```python
# tests/test_db_memory.py
from unittest.mock import MagicMock

from collagent import db

ROW = {"id": "m1", "user_id": "u1", "content": "Prefers FPGA research", "kind": "fact",
       "created_at": "2026-06-20T00:00:00Z", "updated_at": "2026-06-20T00:00:00Z"}


def _client():
    client = MagicMock()
    # get_memories: select().eq().order().execute()
    client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [ROW]
    # create_memory: insert().execute()
    client.table.return_value.insert.return_value.execute.return_value.data = [ROW]
    # update_memory: update().eq().eq().execute()
    client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = [ROW]
    # delete_memory: delete().eq().eq().execute()
    client.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
    return client


def test_get_memories_scopes_to_user(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    mems = db.get_memories("u1")
    assert len(mems) == 1 and mems[0].content == "Prefers FPGA research"
    client.table.return_value.select.return_value.eq.assert_called_once_with("user_id", "u1")


def test_create_memory_inserts_user_scoped_row(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    m = db.create_memory("u1", "Prefers FPGA research", "fact")
    inserted = client.table.return_value.insert.call_args.args[0]
    assert inserted["user_id"] == "u1" and inserted["content"] == "Prefers FPGA research"
    assert inserted["kind"] == "fact"
    assert m.id == "m1"


def test_update_memory_filters_by_id_and_user(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    m = db.update_memory("u1", "m1", "new content")
    assert m.id == "m1"
    eq_chain = client.table.return_value.update.return_value.eq
    eq_chain.assert_called_once_with("id", "m1")
    eq_chain.return_value.eq.assert_called_once_with("user_id", "u1")


def test_update_memory_missing_raises(monkeypatch):
    client = _client()
    client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
    monkeypatch.setattr(db, "get_client", lambda: client)
    import pytest
    with pytest.raises(ValueError):
        db.update_memory("u1", "nope", "x")


def test_delete_memory_filters_by_id_and_user(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    db.delete_memory("u1", "m1")
    eq_chain = client.table.return_value.delete.return_value.eq
    eq_chain.assert_called_once_with("id", "m1")
    eq_chain.return_value.eq.assert_called_once_with("user_id", "u1")
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_db_memory.py -v`
Expected: FAIL with `AttributeError: module 'collagent.db' has no attribute 'get_memories'`.

- [ ] **Step 3: Add the repository functions**

Append to `src/collagent/db.py` (note: `datetime`, `timezone`, and `Memory` must be available — `datetime`/`timezone` are already imported at the top of the file; add `Memory` to the existing `from collagent.models import (...)` block):

```python
def get_memories(user_id: str) -> list[Memory]:
    res = (
        get_client().table("user_memories").select("*")
        .eq("user_id", user_id)
        .order("created_at")
        .execute()
    )
    return [Memory(**row) for row in res.data]


def create_memory(user_id: str, content: str, kind: str = "fact") -> Memory:
    res = (
        get_client().table("user_memories")
        .insert({"user_id": user_id, "content": content, "kind": kind})
        .execute()
    )
    return Memory(**res.data[0])


def update_memory(user_id: str, memory_id: str, content: str) -> Memory:
    res = (
        get_client().table("user_memories")
        .update({"content": content, "updated_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", memory_id).eq("user_id", user_id)
        .execute()
    )
    if not res.data:
        raise ValueError(f"Memory {memory_id} not found for user")
    return Memory(**res.data[0])


def delete_memory(user_id: str, memory_id: str) -> None:
    (
        get_client().table("user_memories").delete()
        .eq("id", memory_id).eq("user_id", user_id)
        .execute()
    )
```

Also update the import near the top of `src/collagent/db.py`:

```python
from collagent.models import (
    CourseStatus,
    EventRecommendation,
    MajorMapCourse,
    Memory,
    PersonRecommendation,
    Profile,
    ProfileUpdate,
)
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/test_db_memory.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/collagent/db.py tests/test_db_memory.py
git commit -m "feat: user-scoped memory repository (get/create/update/delete)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Memory tools (the agent's CRUD interface)

**Files:**
- Create: `src/collagent/memory_tools.py`
- Create: `tests/test_memory_tools.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_memory_tools.py` (mirrors `tests/test_people_tools.py`):

```python
# tests/test_memory_tools.py
from collagent import memory_tools
from collagent.models import Memory

MEM = Memory(id="m1", user_id="u1", content="Prefers FPGA research", kind="fact")


def _tools():
    return {t.name: t for t in memory_tools.make_memory_tools("u1")}


def test_remember_creates_and_confirms(monkeypatch):
    captured = {}
    monkeypatch.setattr(memory_tools.db, "create_memory",
                        lambda uid, content, kind="fact": captured.update(uid=uid, content=content, kind=kind) or MEM)
    out = _tools()["remember"].invoke({"content": "Prefers FPGA research"})
    assert captured == {"uid": "u1", "content": "Prefers FPGA research", "kind": "fact"}
    assert "Prefers FPGA research" in out


def test_list_memories_renders_ids(monkeypatch):
    monkeypatch.setattr(memory_tools.db, "get_memories", lambda uid: [MEM])
    out = _tools()["list_memories"].invoke({})
    assert "m1" in out and "Prefers FPGA research" in out


def test_list_memories_empty(monkeypatch):
    monkeypatch.setattr(memory_tools.db, "get_memories", lambda uid: [])
    out = _tools()["list_memories"].invoke({})
    assert "no memories" in out.lower()


def test_update_memory_handles_missing(monkeypatch):
    def boom(uid, mid, content):
        raise ValueError("not found")
    monkeypatch.setattr(memory_tools.db, "update_memory", boom)
    out = _tools()["update_memory"].invoke({"memory_id": "nope", "content": "x"})
    assert "no memory" in out.lower()


def test_forget_deletes(monkeypatch):
    captured = {}
    monkeypatch.setattr(memory_tools.db, "delete_memory",
                        lambda uid, mid: captured.update(uid=uid, mid=mid))
    out = _tools()["forget"].invoke({"memory_id": "m1"})
    assert captured == {"uid": "u1", "mid": "m1"}
    assert "m1" in out
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_memory_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'collagent.memory_tools'`.

- [ ] **Step 3: Implement the tool factory**

Create `src/collagent/memory_tools.py`:

```python
# src/collagent/memory_tools.py
"""Per-user memory tools: the chat agent curates durable facts about the student
through these CRUD tools (ChatGPT/Claude-style). Every tool is scoped to user_id."""
from langchain.tools import tool

from collagent import db


def make_memory_tools(user_id: str) -> list:
    @tool("remember")
    def remember(content: str, kind: str = "fact") -> str:
        """Save a durable fact about the student for future conversations — a stable
        preference, goal, constraint, or detail they shared (e.g. 'Prefers FPGA
        research', 'Graduating Spring 2027'). Do NOT store transient chit-chat or
        anything already in their profile. `kind` is a free label like 'fact',
        'goal', or 'preference'."""
        m = db.create_memory(user_id, content, kind)
        return f"Remembered (id {m.id}): {m.content}"

    @tool("list_memories")
    def list_memories() -> str:
        """List everything currently remembered about the student, each with its id.
        Use this to find an id before updating or forgetting a memory."""
        mems = db.get_memories(user_id)
        if not mems:
            return "No memories stored yet."
        return "\n".join(f"- [{m.id}] {m.content}" for m in mems)

    @tool("update_memory")
    def update_memory(memory_id: str, content: str) -> str:
        """Revise an existing memory's content. Get the id from list_memories first."""
        try:
            m = db.update_memory(user_id, memory_id, content)
        except ValueError:
            return f"No memory with id {memory_id}."
        return f"Updated (id {m.id}): {m.content}"

    @tool("forget")
    def forget(memory_id: str) -> str:
        """Delete a memory the student no longer wants kept, or that has become wrong.
        Get the id from list_memories first."""
        db.delete_memory(user_id, memory_id)
        return f"Forgot memory {memory_id}."

    return [remember, list_memories, update_memory, forget]
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/test_memory_tools.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/collagent/memory_tools.py tests/test_memory_tools.py
git commit -m "feat: agent memory CRUD tools (remember/list/update/forget)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Inject memories into the system prompt

**Files:**
- Modify: `src/collagent/prompts.py`
- Modify: `tests/test_prompts.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_prompts.py` (the existing imports already include `build_system_prompt`, `Profile`, `MajorMapCourse`; add `Memory`):

```python
def test_prompt_includes_memories_when_present():
    from collagent.models import Memory
    mems = [Memory(id="m1", user_id="u1", content="Prefers FPGA research")]
    prompt = build_system_prompt(PROFILE, COURSES, mems)
    assert "Prefers FPGA research" in prompt


def test_prompt_memories_block_injected_for_empty_profile():
    from collagent.models import Memory
    mems = [Memory(id="m1", user_id="u1", content="Wants a research internship")]
    prompt = build_system_prompt(Profile(id="u1", email="a@asu.edu"), [], mems)
    assert "has not completed onboarding" in prompt  # base path preserved
    assert "Wants a research internship" in prompt    # memories still injected


def test_prompt_no_memory_block_when_none():
    prompt = build_system_prompt(PROFILE, COURSES)  # memories defaults to None
    assert "remember about this student" not in prompt
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_prompts.py -v`
Expected: the three new tests FAIL (`build_system_prompt` takes 2 positional args / no memory block). Existing prompt tests still PASS.

- [ ] **Step 3: Update `prompts.py`**

Replace the contents of `src/collagent/prompts.py` with:

```python
from collagent.models import MajorMapCourse, Memory, Profile

_BASE = """You are Collagent, a proactive personal assistant and advisor for an ASU student.
You work for the student: be concrete, helpful, and grounded in their actual context below.
When the student tells you something new about themselves (interests, clubs, goals, course
progress), persist it using your profile tools — never just acknowledge it.
When the student shares a durable preference, goal, or detail worth recalling in future
conversations, save it with your memory tools (remember / update_memory / forget). Use
list_memories to review or correct what you've stored. Don't store transient chit-chat.
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


def _format_memories(memories: list[Memory] | None) -> str:
    if not memories:
        return ""
    lines = ["", "What you remember about this student (from past conversations):"]
    lines.extend(f"- {m.content}" for m in memories)
    return "\n".join(lines)


def build_system_prompt(
    profile: Profile | None,
    courses: list[MajorMapCourse],
    memories: list[Memory] | None = None,
) -> str:
    mem_block = _format_memories(memories)
    if profile is None or (not profile.onboarded and not profile.major_name):
        return (
            _BASE
            + "\nThe student has not completed onboarding yet; encourage them to."
            + mem_block
        )

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
    return "\n".join(parts) + mem_block
```

- [ ] **Step 4: Run to verify all prompt tests pass**

Run: `uv run pytest tests/test_prompts.py -v`
Expected: PASS (all — original 3 + new 3). The `_BASE` change adds memory guidance without altering the substrings the original tests assert.

- [ ] **Step 5: Commit**

```bash
git add src/collagent/prompts.py tests/test_prompts.py
git commit -m "feat: inject agent memories into the chat system prompt

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Wire memory into the chat route

**Files:**
- Modify: `src/collagent/api/routes/chat.py`

- [ ] **Step 1: Update the chat route**

In `src/collagent/api/routes/chat.py`, add the import alongside the other tool factories (after line 13):

```python
from collagent.memory_tools import make_memory_tools
```

Then in the `chat` handler, load memories and bind the tools. Replace the body up to the `config = ...` line:

```python
@router.post("")
def chat(req: ChatRequest, user_id: str = Depends(get_current_user_id)):
    profile = db.get_profile(user_id)
    courses = db.get_major_map_courses(user_id)
    memories = db.get_memories(user_id)
    agent = create_graph(
        checkpointer=_CHECKPOINTER,
        system_prompt=build_system_prompt(profile, courses, memories),
        extra_tools=(
            tuple(make_profile_tools(user_id))
            + tuple(make_event_tools(user_id))
            + tuple(make_people_tools(user_id))
            + tuple(make_memory_tools(user_id))
        ),
    )
    config = {"configurable": {"thread_id": f"{user_id}:{req.thread_id}"}}
```

(The `gen()` closure and `return StreamingResponse(...)` below are unchanged.)

- [ ] **Step 2: Verify nothing regressed in the chat-stream test**

Run: `uv run pytest tests/test_chat_stream.py -v`
Expected: PASS. If `test_chat_stream.py` monkeypatches `db` calls, ensure `db.get_memories` is stubbed there too; if it instead stubs `create_graph`/`stream_events`, no change is needed. Read the test first and adjust its monkeypatches minimally if it touches real `db`.

- [ ] **Step 3: Commit**

```bash
git add src/collagent/api/routes/chat.py tests/test_chat_stream.py
git commit -m "feat: load + bind agent memory in the chat route

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

(If `test_chat_stream.py` needed no edit, drop it from the `git add`.)

---

## Task 8: Memory API route (read + delete for the Profile panel)

**Files:**
- Create: `src/collagent/api/routes/memory.py`
- Modify: `src/collagent/api/main.py`
- Create: `tests/test_api_memory.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_api_memory.py` (mirrors `tests/test_api_people.py`; the `client` fixture lives in `tests/conftest.py`):

```python
# tests/test_api_memory.py
from collagent.api.routes import memory as memory_routes
from collagent.models import Memory

MEM = Memory(id="m1", user_id="00000000-0000-0000-0000-000000000001",
             content="Prefers FPGA research", kind="fact")


def test_list_memory(client, monkeypatch):
    monkeypatch.setattr(memory_routes.db, "get_memories", lambda uid: [MEM])
    res = client.get("/api/memory")
    assert res.status_code == 200
    assert res.json()[0]["content"] == "Prefers FPGA research"


def test_delete_memory(client, monkeypatch):
    captured = {}
    monkeypatch.setattr(memory_routes.db, "delete_memory",
                        lambda uid, mid: captured.update(uid=uid, mid=mid))
    res = client.delete("/api/memory/m1")
    assert res.status_code == 204
    assert captured["mid"] == "m1"
    assert captured["uid"] == "00000000-0000-0000-0000-000000000001"  # scoped to caller


def test_memory_unauthenticated_401():
    from fastapi.testclient import TestClient

    from collagent.api.main import app

    assert TestClient(app).get("/api/memory").status_code == 401
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_api_memory.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'collagent.api.routes.memory'`.

- [ ] **Step 3: Implement the route**

Create `src/collagent/api/routes/memory.py`:

```python
from fastapi import APIRouter, Depends, Response

from collagent import db
from collagent.api.auth import get_current_user_id
from collagent.models import Memory

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("", response_model=list[Memory])
def list_memories(user_id: str = Depends(get_current_user_id)):
    return db.get_memories(user_id)


@router.delete("/{memory_id}", status_code=204)
def delete_memory(memory_id: str, user_id: str = Depends(get_current_user_id)):
    db.delete_memory(user_id, memory_id)
    return Response(status_code=204)
```

- [ ] **Step 4: Register the router**

In `src/collagent/api/main.py`, add `memory` to the routes import and include it. Change the import line:

```python
from collagent.api.routes import chat, events, majormap, memory, people, profile, programs
```

and add after `app.include_router(people.router)`:

```python
app.include_router(memory.router)
```

- [ ] **Step 5: Run to verify they pass**

Run: `uv run pytest tests/test_api_memory.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add src/collagent/api/routes/memory.py src/collagent/api/main.py tests/test_api_memory.py
git commit -m "feat: memory API route (GET list, DELETE one)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 9: Frontend — "What Collagent remembers" panel

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/app/profile/page.tsx`

> **Frontend caveat (from `frontend/AGENTS.md`):** this is Next.js 16 with breaking changes. This task only touches a client component, a types file, and a fetch helper (no config/font/server code), so no `node_modules/next/dist/docs/` lookup is needed — but do not introduce new Next APIs.

- [ ] **Step 1: Add the `Memory` type**

Append to `frontend/lib/types.ts`:

```typescript
export interface Memory {
  id: string;
  content: string;
  kind: string;
  created_at: string | null;
  updated_at: string | null;
}
```

- [ ] **Step 2: Add a `del` helper**

In `frontend/lib/api.ts`, add a `del` method to the exported `api` object (DELETE returns 204 with no body, so it resolves the `Response`, not JSON):

```typescript
export const api = {
  get: (path: string) => apiFetch(path).then((r) => r.json()),
  put: (path: string, body: unknown) =>
    apiFetch(path, { method: "PUT", body: JSON.stringify(body) }).then((r) => r.json()),
  post: (path: string, body: unknown) =>
    apiFetch(path, { method: "POST", body: JSON.stringify(body) }).then((r) => r.json()),
  del: (path: string) => apiFetch(path, { method: "DELETE" }),
};
```

- [ ] **Step 3: Add the memory panel to the Profile page**

In `frontend/app/profile/page.tsx`:

(a) extend the imports:

```tsx
import type { CourseStatus, MajorMapCourse, Memory, Profile } from "@/lib/types";
```

(b) add state inside `ProfilePage` (next to the other `useState` calls):

```tsx
  const [memories, setMemories] = useState<Memory[]>([]);
```

(c) load memories in the existing mount `useEffect` (add one line):

```tsx
    api.get("/api/memory").then(setMemories);
```

(d) add a delete handler (next to `toggle`):

```tsx
  async function forget(id: string) {
    setMemories((ms) => ms.filter((m) => m.id !== id));
    await api.del(`/api/memory/${id}`);
  }
```

(e) render the panel as a new `<section>` just before the closing `</main>` (after the Major map section):

```tsx
      <section>
        <h2 className="mb-3 font-display text-xl text-ink">What Collagent remembers</h2>
        {memories.length === 0 ? (
          <p className="text-sm text-muted">
            Nothing yet. As you chat, Collagent will remember durable details about you here.
          </p>
        ) : (
          <ul className="space-y-2">
            {memories.map((m) => (
              <li
                key={m.id}
                className="flex items-start justify-between gap-3 rounded-lg border border-line bg-surface px-4 py-2.5"
              >
                <span className="text-sm text-ink">{m.content}</span>
                <button
                  onClick={() => forget(m.id)}
                  className="shrink-0 text-xs font-medium text-muted hover:text-orange"
                >
                  Forget
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
```

- [ ] **Step 4: Build + lint to verify**

Run (from `frontend/`): `npm run build`
Expected: clean build, all routes compile (no type error on `Memory`, `api.del`, or the new JSX). Then `npm run lint` — expected: no new errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/api.ts frontend/app/profile/page.tsx
git commit -m "feat: visible 'What Collagent remembers' panel on Profile

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 10: Full verification + finish branch

**Files:** none (verification only).

- [ ] **Step 1: Run the full backend suite**

Run: `uv run pytest -q`
Expected: all tests pass (the prior 80 + the new memory/model/prompt tests). If any fail, fix before proceeding — do not claim completion with red tests.

- [ ] **Step 2: Live smoke (manual, requires `.env` with a working model profile + Supabase)**

Start the API (`uv run uvicorn collagent.api.main:app --reload`) and the frontend (`npm run dev`). Then:
1. Open Chat and say: *"Remember that I'm focused on FPGA research and graduating Spring 2027."* — confirm the agent calls `remember` (a tool pill appears) and acknowledges.
2. Open Profile → "What Collagent remembers" shows the two facts.
3. Click **Forget** on one → it disappears; reload → it stays gone.
4. Start a new chat thread and ask *"What do you know about my focus?"* — the agent answers from the injected memory.

Record the outcome of each step in the task notes.

- [ ] **Step 3: Confirm no stray files staged**

Run: `git status`
Expected: clean working tree; `canvas-mcp/` still untracked and **not** staged; no `.env` changes.

- [ ] **Step 4: Finish the branch**

Use the **superpowers:finishing-a-development-branch** skill to present merge/PR options for `feat/v2-daily-brief`. (Do not auto-merge — the branch also carries later v2 plans; the human chooses when to integrate.)

---

## Self-Review

**Spec coverage (§ of the design doc → task):**
- §4 `user_memories` table → Task 1 ✓ ; `news_items` / `calendar_items` / `dashboard_snapshots` schema-ahead → Task 1 ✓ (code wired in later plans, as the spec sequences).
- §6 CRUD tools → Task 5 ✓ ; system-prompt injection → Tasks 6–7 ✓ ; visible/deletable Profile panel → Tasks 8–9 ✓ ; research agent reads same store → satisfied by `db.get_memories` (consumed in the Orchestrator plan).
- §7 Groq/ASU swappable model config → Task 2 ✓.
- §4 "all DB tools scoped to authenticated user_id" → enforced in every `db` memory fn (`.eq("user_id", ...)`) and asserted in Tasks 4 & 8.

**Placeholder scan:** none — every code/test step contains complete content; no "TBD"/"handle errors"/"similar to".

**Type consistency:** `Memory` fields (`id, user_id, content, kind, created_at, updated_at`) are identical across the model (Task 3), the migration columns (Task 1), `db` functions (Task 4), tools (Task 5), the API model (Task 8), and the TS interface (Task 9). Function names are stable: `get_memories` / `create_memory` / `update_memory` / `delete_memory` (db), `make_memory_tools` (factory), `build_system_prompt(profile, courses, memories=None)` (prompt). `api.del` is the one new frontend helper, used only in Task 9.

**Scope:** single shippable slice — a working, tested memory system on the v2 foundation. News/calendar/orchestrator are explicitly out and sequenced into later plans.
