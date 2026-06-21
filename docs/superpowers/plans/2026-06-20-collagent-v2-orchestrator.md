# Collagent v2 — Orchestrator Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing chat agent into the single **orchestrator** that maintains the student's dashboard ("The Daily Brief") — it refreshes each section through deterministic pipeline tools, reads the fresh data, writes a synthesized Brief + tuned news subset to `dashboard_snapshots`, and serves it all through one aggregated read endpoint.

**Architecture:** One LangGraph agent powers chat *and* the dashboard (spec §5). New per-user tool factory `make_dashboard_tools(user_id)` exposes: four **deterministic pipeline tools** (`refresh_events` / `refresh_people` / `refresh_news` / `update_calendar`) that wrap the curation/ingestion sequences already proven in the route handlers; two **read tools** (`get_news` / `get_deadlines`) the agent needs to synthesize the Brief (event/people read tools already exist); two user-scoped **CRUD tools** (`remove_event_recommendation` / `remove_person_recommendation`); and one **persistence tool** (`save_dashboard_brief`) that writes the snapshot. The orchestrator's behavior (full-refresh flow + conversational control) lives in the system prompt. The "Refresh my dashboard" button is just a canned chat message over the existing SSE transport — no new endpoint for refresh. A new `GET /api/dashboard` aggregates the last stored state (Brief + tuned news from the snapshot; top-5 events, top-5 people, upcoming deadlines read live from their own tables) so the frontend renders instantly in one call.

**Tech Stack:** Python 3.12, FastAPI, LangChain `@tool` factories, LangGraph react agent, Supabase (Postgres) via supabase-py, pydantic, pytest via `uv run pytest`. No new dependencies. No migration (all tables exist from `0004_foundation.sql`).

---

## Design decisions (locked)

- **No findings returned from refresh tools.** Per spec §5 step 1, refresh tools write to the DB and return only a terse status string (a count) — not the data. The agent then reads the fresh data via read tools (step 2) before writing the Brief (step 3). This keeps token use and hallucination risk down; the DB is the source of truth.
- **News picks resolved server-side.** `save_dashboard_brief` takes `news` as a list of `{id, why_note}`; it resolves each `id` against `news_items` (dropping unknown ids) so the stored title/url/summary are authoritative and never hallucinated. Mirrors the "copy the id exactly, resolve server-side" pattern in `curation/events.py` and `curation/people.py`.
- **Aggregating read endpoint.** `GET /api/dashboard` returns one `DashboardView` (Brief + tuned news from the snapshot, plus top-5 events / top-5 people / upcoming deadlines live). Events/people/calendar are **not** duplicated into the snapshot table (spec §4) — they're read live and sliced in the endpoint.
- **Orchestrator guidance is always present.** Since one agent serves both surfaces, the orchestrator block is appended to every system prompt (kept tight, ~12 lines).
- **`calendar_items` stays read-only to the agent** (spec guardrail): the agent gets `update_calendar` (deterministic re-ingest) and `get_deadlines` (read) — no calendar CRUD tool.

## File structure

- **Create** `src/collagent/dashboard_tools.py` — `make_dashboard_tools(user_id)`: the 9 orchestrator tools.
- **Create** `src/collagent/api/routes/dashboard.py` — `GET /api/dashboard` aggregator.
- **Modify** `src/collagent/models.py` — add `DashboardNewsPick`, `DashboardSnapshot`, `DashboardView`.
- **Modify** `src/collagent/db.py` — add `get_dashboard_snapshot`, `upsert_dashboard_snapshot`, `delete_event_recommendation`, `delete_person_recommendation`.
- **Modify** `src/collagent/prompts.py` — add `_ORCHESTRATOR` block to `build_system_prompt`.
- **Modify** `src/collagent/api/routes/chat.py` — add `make_dashboard_tools(user_id)` to `extra_tools`.
- **Modify** `src/collagent/api/main.py` — register the dashboard router.
- **Create tests:** `tests/test_db_dashboard.py`, `tests/test_dashboard_tools.py`, `tests/test_api_dashboard.py`; extend `tests/test_models.py`, `tests/test_prompts.py`.

---

### Task O-T1: Dashboard models

**Files:**
- Modify: `src/collagent/models.py` (append after `NewsItem`, end of file)
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_models.py`:

```python
def test_dashboard_snapshot_parses_and_ignores_extra():
    from collagent.models import DashboardSnapshot
    snap = DashboardSnapshot(
        brief_md="# Today",
        news=[{"id": "n1", "title": "T", "url": "https://x", "why_note": "w", "junk": "drop"}],
    )
    assert snap.brief_md == "# Today"
    assert snap.news[0].title == "T" and snap.news[0].why_note == "w"


def test_dashboard_view_defaults_empty():
    from collagent.models import DashboardView
    view = DashboardView()
    assert view.brief_md == "" and view.events == [] and view.deadlines == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py -q`
Expected: FAIL (`ImportError: cannot import name 'DashboardSnapshot'`).

- [ ] **Step 3: Implement the models**

Append to the end of `src/collagent/models.py`:

```python
class DashboardNewsPick(BaseModel):
    """A news article chosen for this student's dashboard, with a per-student why-note.
    Stored in dashboard_snapshots.news (jsonb)."""

    model_config = {"extra": "ignore"}

    id: str | None = None
    title: str
    url: str
    summary: str | None = None
    published_at: str | None = None
    why_note: str | None = None


class DashboardSnapshot(BaseModel):
    """The agent-written Brief + tuned news subset for one student. Mirrors a
    dashboard_snapshots row."""

    model_config = {"extra": "ignore"}

    brief_md: str = ""
    news: list[DashboardNewsPick] = []
    generated_at: str | None = None


class DashboardView(BaseModel):
    """Aggregated last-stored dashboard the Home feed renders in one call: the snapshot's
    Brief + tuned news, plus top recommendations and deadlines read live."""

    model_config = {"extra": "ignore"}

    brief_md: str = ""
    generated_at: str | None = None
    news: list[DashboardNewsPick] = []
    events: list[EventRecommendation] = []
    people: list[PersonRecommendation] = []
    deadlines: list[CalendarItem] = []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/collagent/models.py tests/test_models.py
git commit -m "$(cat <<'EOF'
feat: dashboard snapshot + view models

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task O-T2: Dashboard DB repository

**Files:**
- Modify: `src/collagent/db.py` (imports + new functions near the other repo functions)
- Test: `tests/test_db_dashboard.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_db_dashboard.py`:

```python
# tests/test_db_dashboard.py
from unittest.mock import MagicMock

from collagent import db

SNAP = {"id": "d1", "user_id": "u1", "brief_md": "# Hi", "news": [],
        "generated_at": "2026-06-20T00:00:00Z"}


def _client():
    client = MagicMock()
    client.table.return_value.upsert.return_value.execute.return_value.data = [SNAP]
    client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [SNAP]
    client.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
    return client


def test_upsert_dashboard_snapshot_uses_user_conflict(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    snap = db.upsert_dashboard_snapshot("u1", "# Hi", [])
    payload, kwargs = client.table.return_value.upsert.call_args
    assert kwargs.get("on_conflict") == "user_id"
    assert payload[0]["user_id"] == "u1" and payload[0]["brief_md"] == "# Hi"
    assert snap.brief_md == "# Hi"


def test_get_dashboard_snapshot_scopes_to_user(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    snap = db.get_dashboard_snapshot("u1")
    client.table.return_value.select.return_value.eq.assert_called_once_with("user_id", "u1")
    assert snap.brief_md == "# Hi"


def test_get_dashboard_snapshot_none_when_missing(monkeypatch):
    client = _client()
    client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    monkeypatch.setattr(db, "get_client", lambda: client)
    assert db.get_dashboard_snapshot("u1") is None


def test_delete_event_recommendation_scopes_to_id_and_user(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    db.delete_event_recommendation("u1", "r1")
    eq_chain = client.table.return_value.delete.return_value.eq
    eq_chain.assert_called_once_with("id", "r1")
    eq_chain.return_value.eq.assert_called_once_with("user_id", "u1")


def test_delete_person_recommendation_scopes_to_id_and_user(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    db.delete_person_recommendation("u1", "r2")
    eq_chain = client.table.return_value.delete.return_value.eq
    eq_chain.assert_called_once_with("id", "r2")
    eq_chain.return_value.eq.assert_called_once_with("user_id", "u1")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_db_dashboard.py -q`
Expected: FAIL (`AttributeError: module 'collagent.db' has no attribute 'upsert_dashboard_snapshot'`).

- [ ] **Step 3: Implement the repo functions**

In `src/collagent/db.py`, add `DashboardSnapshot` to the model import block (keep alphabetical):

```python
from collagent.models import (
    CalendarItem,
    CourseStatus,
    DashboardSnapshot,
    EventRecommendation,
    MajorMapCourse,
    Memory,
    NewsItem,
    PersonRecommendation,
    Profile,
    ProfileUpdate,
)
```

Append these functions to the end of `src/collagent/db.py`:

```python
def get_dashboard_snapshot(user_id: str) -> DashboardSnapshot | None:
    res = (
        get_client().table("dashboard_snapshots").select("*")
        .eq("user_id", user_id)
        .execute()
    )
    if not res.data:
        return None
    return DashboardSnapshot(**res.data[0])


def upsert_dashboard_snapshot(
    user_id: str, brief_md: str, news: list[dict]
) -> DashboardSnapshot:
    res = (
        get_client().table("dashboard_snapshots")
        .upsert(
            {
                "user_id": user_id,
                "brief_md": brief_md,
                "news": news,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="user_id",
        )
        .execute()
    )
    return DashboardSnapshot(**res.data[0])


def delete_event_recommendation(user_id: str, recommendation_id: str) -> None:
    (
        get_client().table("event_recommendations").delete()
        .eq("id", recommendation_id).eq("user_id", user_id)
        .execute()
    )


def delete_person_recommendation(user_id: str, recommendation_id: str) -> None:
    (
        get_client().table("person_recommendations").delete()
        .eq("id", recommendation_id).eq("user_id", user_id)
        .execute()
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_db_dashboard.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/collagent/db.py tests/test_db_dashboard.py
git commit -m "$(cat <<'EOF'
feat: dashboard snapshot repo + recommendation deletes

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task O-T3: Deterministic pipeline refresh tools

**Files:**
- Create: `src/collagent/dashboard_tools.py`
- Test: `tests/test_dashboard_tools.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_dashboard_tools.py`:

```python
# tests/test_dashboard_tools.py
from collagent import dashboard_tools


def _tools():
    return {t.name: t for t in dashboard_tools.make_dashboard_tools("u1")}


def test_refresh_events_runs_pipeline_user_scoped(monkeypatch):
    calls = []
    monkeypatch.setattr(dashboard_tools, "fetch_upcoming_events", lambda: [{"id": "e1"}])
    monkeypatch.setattr(dashboard_tools.db, "upsert_events", lambda rows: calls.append("upsert"))
    monkeypatch.setattr(dashboard_tools, "curate_events", lambda uid: calls.append(uid) or [1, 2])
    out = _tools()["refresh_events"].invoke({})
    assert calls == ["upsert", "u1"]
    assert "2" in out


def test_refresh_people_runs_pipeline_user_scoped(monkeypatch):
    calls = []
    monkeypatch.setattr(dashboard_tools.db, "get_profile", lambda uid: None)
    monkeypatch.setattr(dashboard_tools, "query_terms", lambda p: ["x"])
    monkeypatch.setattr(dashboard_tools, "fetch_faculty", lambda terms: [{"id": "p1"}])
    monkeypatch.setattr(dashboard_tools.db, "upsert_people", lambda rows: calls.append("upsert"))
    monkeypatch.setattr(dashboard_tools, "curate_people", lambda uid: calls.append(uid) or [1])
    out = _tools()["refresh_people"].invoke({})
    assert calls == ["upsert", "u1"]
    assert "1" in out


def test_refresh_news_fetches_then_upserts(monkeypatch):
    calls = []
    monkeypatch.setattr(dashboard_tools, "fetch_news", lambda: [{"url": "u"}])
    monkeypatch.setattr(dashboard_tools.db, "upsert_news_items", lambda rows: calls.append("upsert"))
    out = _tools()["refresh_news"].invoke({})
    assert calls == ["upsert"] and "1" in out


def test_refresh_news_noop_without_results(monkeypatch):
    def boom(rows):
        raise AssertionError("should not upsert on empty fetch")
    monkeypatch.setattr(dashboard_tools, "fetch_news", lambda: [])
    monkeypatch.setattr(dashboard_tools.db, "upsert_news_items", boom)
    out = _tools()["refresh_news"].invoke({})
    assert "0" in out


def test_update_calendar_fetches_then_upserts(monkeypatch):
    calls = []
    monkeypatch.setattr(dashboard_tools, "fetch_calendar", lambda: [{"title": "x"}])
    monkeypatch.setattr(dashboard_tools.db, "upsert_calendar_items", lambda rows: calls.append("upsert"))
    out = _tools()["update_calendar"].invoke({})
    assert calls == ["upsert"] and "1" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_dashboard_tools.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'collagent.dashboard_tools'`).

- [ ] **Step 3: Implement the refresh tools**

Create `src/collagent/dashboard_tools.py`:

```python
# src/collagent/dashboard_tools.py
"""The orchestrator's dashboard tools. One agent (chat + dashboard) uses these to
maintain "The Daily Brief": deterministic pipeline tools that re-run the existing
curation/ingestion sequences, read tools the agent uses to synthesize the Brief,
user-scoped CRUD over recommendations, and a tool that persists the snapshot.
Every tool is scoped to user_id (spec §5 guardrail). calendar_items stays read-only:
the agent may re-ingest (update_calendar) and read (get_deadlines) but not edit it."""
from langchain.tools import tool

from collagent import db
from collagent.asu.calendar import fetch_calendar
from collagent.asu.events import fetch_upcoming_events
from collagent.asu.news import fetch_news
from collagent.asu.people import fetch_faculty, query_terms
from collagent.curation.events import curate_events
from collagent.curation.people import curate_people


def make_dashboard_tools(user_id: str) -> list:
    # ---- deterministic pipeline tools (write to DB, return only a status) ----
    @tool("refresh_events")
    def refresh_events() -> str:
        """Re-ingest upcoming ASU events and regenerate this student's ranked event
        recommendations. Writes to the database (the dashboard's Events section reflects
        it). Returns a short status, not the data."""
        db.upsert_events(fetch_upcoming_events())
        recs = curate_events(user_id)
        return f"Events refreshed: {len(recs)} recommendations."

    @tool("refresh_people")
    def refresh_people() -> str:
        """Re-ingest ASU faculty/staff matched to this student and regenerate ranked
        people-to-contact recommendations. Writes to the database. Returns a short
        status, not the data."""
        profile = db.get_profile(user_id)
        db.upsert_people(fetch_faculty(query_terms(profile)))
        recs = curate_people(user_id)
        return f"People refreshed: {len(recs)} recommendations."

    @tool("refresh_news")
    def refresh_news() -> str:
        """Re-ingest open-web ASU news via web search and update the shared news cache.
        Returns a short status. No-ops if the news provider key is unset."""
        rows = fetch_news()
        if rows:
            db.upsert_news_items(rows)
        return f"News refreshed: {len(rows)} articles fetched."

    @tool("update_calendar")
    def update_calendar() -> str:
        """Re-ingest the current term's ASU academic calendar (deadlines, breaks,
        registration windows) from the registrar. Read-only afterward. Returns a short
        status."""
        rows = fetch_calendar()
        if rows:
            db.upsert_calendar_items(rows)
        return f"Calendar updated: {len(rows)} items."

    return [refresh_events, refresh_people, refresh_news, update_calendar]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_dashboard_tools.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/collagent/dashboard_tools.py tests/test_dashboard_tools.py
git commit -m "$(cat <<'EOF'
feat: deterministic dashboard refresh tools

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task O-T4: Read, CRUD, and brief-persistence tools

**Files:**
- Modify: `src/collagent/dashboard_tools.py` (add tools before the `return`, extend the returned list)
- Test: `tests/test_dashboard_tools.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_dashboard_tools.py`:

```python
from collagent.models import CalendarItem, NewsItem


def test_get_news_lists_ids_and_titles(monkeypatch):
    item = NewsItem(id="n1", title="ASU grant", url="https://x", summary="big news")
    monkeypatch.setattr(dashboard_tools.db, "get_recent_news", lambda **k: [item])
    out = _tools()["get_news"].invoke({})
    assert "n1" in out and "ASU grant" in out


def test_get_news_empty(monkeypatch):
    monkeypatch.setattr(dashboard_tools.db, "get_recent_news", lambda **k: [])
    out = _tools()["get_news"].invoke({})
    assert "refresh_news" in out


def test_get_deadlines_lists_items(monkeypatch):
    c = CalendarItem(id="c1", term="Summer 2026", title="Drop deadline",
                     date_start="2026-07-01", category="deadline")
    monkeypatch.setattr(dashboard_tools.db, "get_upcoming_calendar_items", lambda: [c])
    out = _tools()["get_deadlines"].invoke({})
    assert "Drop deadline" in out


def test_remove_event_recommendation_scopes_to_user(monkeypatch):
    captured = {}
    monkeypatch.setattr(dashboard_tools.db, "delete_event_recommendation",
                        lambda uid, rid: captured.update(uid=uid, rid=rid))
    out = _tools()["remove_event_recommendation"].invoke({"recommendation_id": "r1"})
    assert captured == {"uid": "u1", "rid": "r1"} and "r1" in out


def test_remove_person_recommendation_scopes_to_user(monkeypatch):
    captured = {}
    monkeypatch.setattr(dashboard_tools.db, "delete_person_recommendation",
                        lambda uid, rid: captured.update(uid=uid, rid=rid))
    out = _tools()["remove_person_recommendation"].invoke({"recommendation_id": "r2"})
    assert captured == {"uid": "u1", "rid": "r2"}


def test_save_dashboard_brief_resolves_news_and_persists(monkeypatch):
    item = NewsItem(id="n1", title="ASU grant", url="https://x", summary="s")
    monkeypatch.setattr(dashboard_tools.db, "get_recent_news", lambda **k: [item])
    captured = {}
    monkeypatch.setattr(dashboard_tools.db, "upsert_dashboard_snapshot",
                        lambda uid, brief, news: captured.update(uid=uid, brief=brief, news=news))
    out = _tools()["save_dashboard_brief"].invoke({
        "brief_md": "# Today",
        "news": [{"id": "n1", "why_note": "relevant"}, {"id": "ghost", "why_note": "x"}],
    })
    assert captured["uid"] == "u1" and captured["brief"] == "# Today"
    assert len(captured["news"]) == 1  # unknown id dropped
    assert captured["news"][0]["url"] == "https://x"
    assert captured["news"][0]["why_note"] == "relevant"
    assert "1" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_dashboard_tools.py -q`
Expected: FAIL (`KeyError: 'get_news'`).

- [ ] **Step 3: Implement the read/CRUD/brief tools**

In `src/collagent/dashboard_tools.py`, insert these tools after `update_calendar` and **before** the `return`, then replace the return list:

```python
    # ---- read tools the agent uses to synthesize the Brief ----
    @tool("get_news")
    def get_news() -> str:
        """List recent ASU news from the shared cache, each with its id, title, summary,
        and link. Use the ids when calling save_dashboard_brief."""
        items = db.get_recent_news()
        if not items:
            return "No news cached yet. Run refresh_news first."
        return "\n\n".join(
            f"- [{n.id}] {n.title}\n  {(n.summary or '')[:200]}\n  Link: {n.url}"
            for n in items
        )

    @tool("get_deadlines")
    def get_deadlines() -> str:
        """List upcoming academic-calendar items for the current term (deadlines, breaks,
        registration windows). Read-only."""
        items = db.get_upcoming_calendar_items()
        if not items:
            return "No calendar items yet. Run update_calendar first."
        return "\n".join(
            f"- {c.date_start or 'TBD'}: {c.title}"
            + (f" ({c.category})" if c.category else "")
            for c in items
        )

    # ---- user-scoped CRUD over recommendations ----
    @tool("remove_event_recommendation")
    def remove_event_recommendation(recommendation_id: str) -> str:
        """Remove one event from this student's recommendations (e.g. they said they're
        not interested). Pass the recommendation id. Consider also remembering the
        preference with your memory tools."""
        db.delete_event_recommendation(user_id, recommendation_id)
        return f"Removed event recommendation {recommendation_id}."

    @tool("remove_person_recommendation")
    def remove_person_recommendation(recommendation_id: str) -> str:
        """Remove one person from this student's recommendations. Pass the recommendation
        id. Consider also remembering the preference with your memory tools."""
        db.delete_person_recommendation(user_id, recommendation_id)
        return f"Removed person recommendation {recommendation_id}."

    # ---- persist the synthesized Brief + tuned news subset ----
    @tool("save_dashboard_brief")
    def save_dashboard_brief(brief_md: str, news: list[dict]) -> str:
        """Persist this student's dashboard Brief and tuned news subset. `brief_md` is a
        concise markdown Brief (lightweight, informative, suggestive — surface any
        imminent deadline). `news` is a list of picks, each
        {"id": <a news id from get_news>, "why_note": <one line on why it matters to
        them>}; choose about 5. Ids are resolved server-side, so copy them exactly;
        unknown ids are ignored."""
        by_id = {n.id: n for n in db.get_recent_news(limit=50)}
        picks: list[dict] = []
        for item in news:
            n = by_id.get(item.get("id"))
            if not n:
                continue
            picks.append({
                "id": n.id,
                "title": n.title,
                "url": n.url,
                "summary": n.summary,
                "published_at": n.published_at,
                "why_note": item.get("why_note", ""),
            })
        db.upsert_dashboard_snapshot(user_id, brief_md, picks)
        return f"Saved dashboard brief with {len(picks)} news picks."

    return [
        refresh_events, refresh_people, refresh_news, update_calendar,
        get_news, get_deadlines,
        remove_event_recommendation, remove_person_recommendation,
        save_dashboard_brief,
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_dashboard_tools.py -q`
Expected: PASS (11 passed).

- [ ] **Step 5: Commit**

```bash
git add src/collagent/dashboard_tools.py tests/test_dashboard_tools.py
git commit -m "$(cat <<'EOF'
feat: dashboard read, remove, and brief-save tools

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task O-T5: Orchestrator system prompt

**Files:**
- Modify: `src/collagent/prompts.py`
- Test: `tests/test_prompts.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_prompts.py`:

```python
def test_prompt_includes_orchestrator_full_refresh_flow():
    from collagent.prompts import build_system_prompt
    out = build_system_prompt(None, [])
    low = out.lower()
    assert "dashboard" in low and "refresh" in low
    assert "save_dashboard_brief" in out  # names the persistence step
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_prompts.py -q`
Expected: FAIL (assertion error — orchestrator guidance not present).

- [ ] **Step 3: Implement the prompt block**

In `src/collagent/prompts.py`, add the constant after `_BASE`:

```python
_ORCHESTRATOR = """
You also maintain this student's dashboard, "The Daily Brief": a short Brief, ASU
Happenings (news), upcoming Deadlines (academic calendar), and their top Events and People.
When the student asks to refresh their dashboard (e.g. "refresh my dashboard"), run a FULL
refresh in order:
1. Call refresh_events, refresh_people, refresh_news, and update_calendar.
2. Read the fresh data with get_event_recommendations, get_person_recommendations,
   get_news, and get_deadlines.
3. Call save_dashboard_brief with a concise markdown Brief tying together what matters most
   to THIS student (surface any imminent deadline) plus about 5 tuned news picks (each a
   news id from get_news with a one-line why_note).
To refresh a single section, call just that one tool. If the student dislikes a
recommendation, remove it (remove_event_recommendation / remove_person_recommendation) and
remember the preference. Keep the Brief lightweight, informative, and suggestive — never a
wall of text.
"""
```

Then change `build_system_prompt` so both return paths include it. Replace the body of `build_system_prompt` (keep the signature) so the head string is `_BASE + _ORCHESTRATOR`:

```python
def build_system_prompt(
    profile: Profile | None,
    courses: list[MajorMapCourse],
    memories: list[Memory] | None = None,
) -> str:
    mem_block = _format_memories(memories)
    head = _BASE + _ORCHESTRATOR
    if profile is None or (not profile.onboarded and not profile.major_name):
        return (
            head
            + "\nThe student has not completed onboarding yet; encourage them to."
            + mem_block
        )

    parts = [head, "Student context:"]
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

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_prompts.py -q`
Expected: PASS (all prompt tests, including the existing ones, pass).

- [ ] **Step 5: Commit**

```bash
git add src/collagent/prompts.py tests/test_prompts.py
git commit -m "$(cat <<'EOF'
feat: orchestrator full-refresh guidance in system prompt

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task O-T6: Dashboard API route + wire tools into chat

**Files:**
- Create: `src/collagent/api/routes/dashboard.py`
- Modify: `src/collagent/api/main.py` (import + include_router)
- Modify: `src/collagent/api/routes/chat.py` (add dashboard tools to extra_tools)
- Test: `tests/test_api_dashboard.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_api_dashboard.py`:

```python
# tests/test_api_dashboard.py
from collagent.api.routes import dashboard as dash_routes
from collagent.models import (
    CalendarItem,
    DashboardSnapshot,
    EventRecommendation,
    PersonRecommendation,
)


def test_get_dashboard_aggregates_snapshot_and_live(client, monkeypatch):
    monkeypatch.setattr(dash_routes.db, "get_dashboard_snapshot",
                        lambda uid: DashboardSnapshot(brief_md="# Hi", news=[],
                                                      generated_at="2026-06-20T00:00:00Z"))
    monkeypatch.setattr(dash_routes.db, "get_event_recommendations",
                        lambda uid: [EventRecommendation(id="e1", event_id="ev1", title="Talk",
                                                         url="https://e", why_note="w", rank=0)])
    monkeypatch.setattr(dash_routes.db, "get_person_recommendations",
                        lambda uid: [PersonRecommendation(id="p1", person_id="pe1", name="Dr X",
                                                          profile_url="https://p", why_note="w", rank=0)])
    monkeypatch.setattr(dash_routes.db, "get_upcoming_calendar_items",
                        lambda: [CalendarItem(id="c1", term="Summer 2026", title="Drop deadline")])
    res = client.get("/api/dashboard")
    assert res.status_code == 200
    body = res.json()
    assert body["brief_md"] == "# Hi"
    assert body["events"][0]["title"] == "Talk"
    assert body["people"][0]["name"] == "Dr X"
    assert body["deadlines"][0]["title"] == "Drop deadline"


def test_get_dashboard_top5_slicing(client, monkeypatch):
    many_events = [
        EventRecommendation(id=f"e{i}", event_id=f"ev{i}", title=f"T{i}",
                            url="https://e", why_note="w", rank=i)
        for i in range(8)
    ]
    monkeypatch.setattr(dash_routes.db, "get_dashboard_snapshot", lambda uid: None)
    monkeypatch.setattr(dash_routes.db, "get_event_recommendations", lambda uid: many_events)
    monkeypatch.setattr(dash_routes.db, "get_person_recommendations", lambda uid: [])
    monkeypatch.setattr(dash_routes.db, "get_upcoming_calendar_items", lambda: [])
    body = client.get("/api/dashboard").json()
    assert body["brief_md"] == "" and len(body["events"]) == 5


def test_dashboard_unauthenticated_401():
    from fastapi.testclient import TestClient

    from collagent.api.main import app

    assert TestClient(app).get("/api/dashboard").status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api_dashboard.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'collagent.api.routes.dashboard'`).

- [ ] **Step 3: Implement the route, register it, and wire the tools**

Create `src/collagent/api/routes/dashboard.py`:

```python
# src/collagent/api/routes/dashboard.py
from fastapi import APIRouter, Depends

from collagent import db
from collagent.api.auth import get_current_user_id
from collagent.models import DashboardView

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardView)
def read_dashboard(user_id: str = Depends(get_current_user_id)):
    """The last stored dashboard, aggregated for the Home feed: the agent-written Brief +
    tuned news (from the snapshot), plus top-5 events, top-5 people, and upcoming deadlines
    read live from their own tables. The agent maintains it via the chat SSE refresh."""
    snap = db.get_dashboard_snapshot(user_id)
    return DashboardView(
        brief_md=snap.brief_md if snap else "",
        generated_at=snap.generated_at if snap else None,
        news=snap.news if snap else [],
        events=db.get_event_recommendations(user_id)[:5],
        people=db.get_person_recommendations(user_id)[:5],
        deadlines=db.get_upcoming_calendar_items(),
    )
```

In `src/collagent/api/main.py`, add `dashboard` to the routes import block (keep alphabetical) and include the router:

```python
from collagent.api.routes import (
    calendar,
    chat,
    dashboard,
    events,
    majormap,
    memory,
    news,
    people,
    profile,
    programs,
)
```

Add after `app.include_router(chat.router)`:

```python
app.include_router(dashboard.router)
```

In `src/collagent/api/routes/chat.py`, import the factory:

```python
from collagent.dashboard_tools import make_dashboard_tools
```

and extend `extra_tools` in the `create_graph(...)` call:

```python
        extra_tools=(
            tuple(make_profile_tools(user_id))
            + tuple(make_event_tools(user_id))
            + tuple(make_people_tools(user_id))
            + tuple(make_memory_tools(user_id))
            + tuple(make_dashboard_tools(user_id))
        ),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_api_dashboard.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/collagent/api/routes/dashboard.py src/collagent/api/main.py src/collagent/api/routes/chat.py tests/test_api_dashboard.py
git commit -m "$(cat <<'EOF'
feat: dashboard read endpoint + orchestrator tools in chat

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task O-T7: Verify, review, finish

**Files:** none (verification + review)

- [ ] **Step 1: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS — the prior 126 plus the new dashboard tests (≈21 new), no regressions. (Run pytest separately from any commit so a failure can't be masked by a pipeline exit code.)

- [ ] **Step 2: Confirm a clean tree**

Run: `git status -s`
Expected: only `?? canvas-mcp/` (never staged/committed).

- [ ] **Step 3: Smoke-check imports + tool wiring**

Run:
```bash
uv run python -c "from collagent.dashboard_tools import make_dashboard_tools; print(sorted(t.name for t in make_dashboard_tools('u1')))"
```
Expected: the 9 tool names print, e.g. `['get_deadlines', 'get_news', 'refresh_events', 'refresh_news', 'refresh_people', 'remove_event_recommendation', 'remove_person_recommendation', 'save_dashboard_brief', 'update_calendar']`.

Run:
```bash
uv run python -c "from collagent.api.main import app; print([r.path for r in app.routes if 'dashboard' in r.path])"
```
Expected: `['/api/dashboard']`.

- [ ] **Step 4: Combined spec + quality review**

Dispatch one review subagent (superpowers:code-reviewer) over `git diff main..HEAD`, checking: spec §4–§6 compliance (single agent, deterministic pipeline tools, user-scoped whitelist, calendar read-only, snapshot = Brief + tuned news only), TDD coverage, no secret leakage, no scope creep, conventions match the existing tool/db/route patterns.

- [ ] **Step 5: Finish the branch**

Use superpowers:finishing-a-development-branch. Present the 4 options for `feat/v2-orchestrator`; recommend Option 1 (merge to main locally) for consistency with the prior slices. Next slice after merge: **Dashboard spine (frontend, #5)**.

---

## Self-review (against the spec)

**Spec coverage:**
- §5 single orchestrator agent → O-T3/O-T4 (tools), O-T5 (full-refresh flow in prompt), O-T6 (tools wired into the one chat agent). ✓
- §5 deterministic pipeline tools (`refresh_events/people/news`, `update_calendar`) → O-T3. ✓
- §5 DB read + CRUD tools, user-scoped whitelist; calendar read-only → O-T4 (`get_news`/`get_deadlines` read, `remove_*` CRUD, no calendar CRUD) + O-T2 (user-scoped deletes). ✓
- §5 step 3 Brief synthesis → snapshot persisted via `save_dashboard_brief` + O-T2 `upsert_dashboard_snapshot`. ✓
- §4 `dashboard_snapshots` = Brief + tuned news only; events/people/calendar read live → O-T6 aggregator slices live, snapshot holds only brief+news. ✓
- §3 refresh button = prompt over chat SSE → no new transport; O-T5 makes the agent handle "refresh my dashboard"; the button (frontend slice) posts that message. ✓
- §3 Home renders last stored state instantly → `GET /api/dashboard` one-call aggregate. ✓

**Placeholder scan:** none — every step has full code and an exact command with expected output.

**Type consistency:** `DashboardNewsPick`/`DashboardSnapshot`/`DashboardView` defined in O-T1 and used identically in O-T2 (repo), O-T4 (tool builds the same pick dict keys), O-T6 (route). `save_dashboard_brief(brief_md, news)` ↔ `db.upsert_dashboard_snapshot(user_id, brief_md, news)` signatures match. Tool names referenced in the O-T5 prompt (`get_event_recommendations`, `get_person_recommendations`, `get_news`, `get_deadlines`, `save_dashboard_brief`, `remove_*`) all exist (first two in the existing event/people factories; the rest in O-T3/O-T4). ✓

**Out of scope (deferred):** the frontend Home feed consolidation (slice #5), the refresh button UI, and any scheduler. This slice is backend-only and independently testable.
