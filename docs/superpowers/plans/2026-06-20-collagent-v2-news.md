# Collagent v2 — News Ingestion (Tavily) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest current ASU happenings from the open web via the Tavily Search API into the global `news_items` cache, exposed via a read API + a refresh endpoint — the `refresh_news` source the orchestrator will call and the dashboard's "ASU Happenings" section will read.

**Architecture:** A pure parser over Tavily's JSON + a resilient network `fetch_news()` (httpx POST, no new dependency) → `db` upsert/read over `news_items` (already migrated in `0004_foundation.sql`) → FastAPI `GET /api/news` + `POST /api/news/refresh`. Deterministic global ingestion; **per-student tuning happens later in the orchestrator** (it selects the relevant subset into `dashboard_snapshots.news`). No LLM here.

**Tech Stack:** Python 3.12, httpx, FastAPI, Supabase (via `db.py`), pytest (`uv run pytest`). Tavily Search API.

**Source of truth:** `docs/superpowers/specs/2026-06-19-collagent-v2-dashboard-design.md` — §3 (ASU Happenings), §4 (`news_items`, news has no per-user table), §5 (`refresh_news` does Tavily research), §7/§12 (free-tier + data-training caveats).

**Constraints (carry through every task):**
- **Supabase MCP only** for DB; project ref `qepwzwitwjhklxscrugr`. (No new migration — `news_items` exists.)
- **Never touch or commit `.env` / `.env.local`; never print secrets.** A `TAVILY_API_KEY` placeholder already exists in `.env.example`.
- **Do NOT stage or touch the untracked `canvas-mcp/` directory.**
- Backend via `uv` (`uv run pytest`). Commit messages end with:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- Branch: `feat/v2-news` (already checked out).

---

## Tavily Search API (verified 2026-06-20)

- **POST** `https://api.tavily.com/search`
- Auth: header `Authorization: Bearer tvly-...`
- Request JSON: `{"query": str, "topic": "news", "time_range": "week", "max_results": int}` (max_results 0–20).
- Response JSON: `{"results": [{"title", "url", "content", "score", "published_date"?}], "response_time", ...}`. `published_date` is best-effort (not guaranteed; RFC-2822-ish when present).

---

## File Structure

**Created:**
- `src/collagent/asu/news.py` — `parse_news_results()`, `fetch_news()`, default ASU queries.
- `src/collagent/api/routes/news.py` — `GET /api/news`, `POST /api/news/refresh`.
- `tests/test_news_parse.py`, `tests/test_db_news.py`, `tests/test_api_news.py`.

**Modified:**
- `src/collagent/config.py` — add `tavily_api_key`.
- `src/collagent/models.py` — add `NewsItem`.
- `src/collagent/db.py` — add `upsert_news_items`, `get_recent_news`.
- `src/collagent/api/main.py` — register the news router.

---

## Task 1: Config key + `NewsItem` model

**Files:** Modify `src/collagent/config.py`, `src/collagent/models.py`; add tests to `tests/test_config.py` and `tests/test_models.py`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_models.py`:

```python
def test_news_item_defaults_and_extra_ignored():
    from collagent.models import NewsItem
    n = NewsItem(id="n1", title="ASU lands grant", url="https://asu.edu/x")
    assert n.source == "tavily" and n.summary is None and n.published_at is None
    full = NewsItem(id="n1", title="X", url="u", source="tavily", source_key="u",
                    summary="snippet", published_at="2026-06-17T00:00:00Z",
                    fetched_at="2026-06-20T00:00:00Z", extra="ignored")
    assert full.summary == "snippet"
```

Add to `tests/test_config.py`:

```python
def test_settings_has_tavily_key_default_empty():
    from collagent.config import Settings
    s = Settings(_env_file=None)
    assert s.tavily_api_key == ""
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_models.py::test_news_item_defaults_and_extra_ignored tests/test_config.py::test_settings_has_tavily_key_default_empty -v`
Expected: FAIL — `cannot import name 'NewsItem'`; `Settings` has no `tavily_api_key`.

- [ ] **Step 3: Add the field + model**

In `src/collagent/config.py`, add the field to `Settings` (after `frontend_origin`):

```python
    tavily_api_key: str = ""
```

Append to `src/collagent/models.py`:

```python
class NewsItem(BaseModel):
    """A cached open-web news article (Tavily). Global, not per-user. Mirrors a news_items row."""

    model_config = {"extra": "ignore"}

    id: str
    source: str = "tavily"
    source_key: str | None = None
    title: str
    url: str
    summary: str | None = None
    published_at: str | None = None
    fetched_at: str | None = None
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/test_models.py::test_news_item_defaults_and_extra_ignored tests/test_config.py::test_settings_has_tavily_key_default_empty -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/collagent/config.py src/collagent/models.py tests/test_models.py tests/test_config.py
git commit -m "feat: add NewsItem model + TAVILY_API_KEY setting

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Tavily parser + `fetch_news`

**Files:** Create `src/collagent/asu/news.py`; create `tests/test_news_parse.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_news_parse.py`:

```python
# tests/test_news_parse.py
from collagent.asu import news

SAMPLE = {
    "results": [
        {"title": "ASU lands $10M chip grant", "url": "https://news.asu.edu/chip",
         "content": "ASU secured funding for...", "score": 0.96,
         "published_date": "Tue, 17 Jun 2026 00:00:00 GMT"},
        {"title": "Advent Lab researchers honored", "url": "https://news.asu.edu/advent",
         "content": "Two researchers...", "score": 0.91},
        {"title": "", "url": "https://x/empty"},          # missing title -> dropped
        {"title": "No URL", "url": ""},                    # missing url -> dropped
    ]
}


def test_parse_news_maps_and_drops_incomplete():
    rows = news.parse_news_results(SAMPLE)
    assert len(rows) == 2
    first = rows[0]
    assert first["source"] == "tavily"
    assert first["source_key"] == "https://news.asu.edu/chip"
    assert first["title"] == "ASU lands $10M chip grant"
    assert first["summary"] == "ASU secured funding for..."
    assert first["published_at"] == "2026-06-17T00:00:00+00:00"  # RFC-2822 -> ISO
    assert first["raw"]["score"] == 0.96
    # missing published_date tolerated
    assert rows[1]["published_at"] is None


def test_fetch_news_dedupes_by_url(monkeypatch):
    class _Resp:
        status_code = 200
        def json(self):
            return {"results": [
                {"title": "Dup", "url": "https://news.asu.edu/dup", "content": "a"},
            ]}

    class _Client:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, *a, **k): return _Resp()

    monkeypatch.setattr(news.httpx, "Client", _Client)
    rows = news.fetch_news(queries=["q1", "q2"], api_key="tvly-test")
    assert len(rows) == 1  # same url across both queries collapses
    assert rows[0]["url"] == "https://news.asu.edu/dup"


def test_fetch_news_no_key_returns_empty(monkeypatch):
    # No key -> graceful no-op (Tavily not configured yet)
    rows = news.fetch_news(queries=["q"], api_key="")
    assert rows == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_news_parse.py -v`
Expected: FAIL — `No module named 'collagent.asu.news'`.

- [ ] **Step 3: Implement the module**

Create `src/collagent/asu/news.py`:

```python
# src/collagent/asu/news.py
"""Open-web ASU news ingestion via the Tavily Search API. Global cache (news_items);
per-student tuning happens later in the orchestrator. Pure parser + resilient fetch."""
from datetime import datetime
from email.utils import parsedate_to_datetime

import httpx

from collagent.config import settings

SEARCH_URL = "https://api.tavily.com/search"
DEFAULT_QUERIES = [
    "Arizona State University news",
    "ASU research announcement",
    "ASU student opportunities",
]


def _parse_published(value: str | None) -> str | None:
    """Best-effort: ISO or RFC-2822 -> ISO string; None if absent/unparseable."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(value).isoformat()
    except (ValueError, TypeError):
        return None


def parse_news_results(data: dict) -> list[dict]:
    """Map a Tavily response into news_items rows. Drops results missing title/url."""
    rows: list[dict] = []
    for r in data.get("results", []):
        url = r.get("url")
        title = r.get("title")
        if not url or not title:
            continue
        rows.append({
            "source": "tavily",
            "source_key": url,
            "title": title,
            "url": url,
            "summary": r.get("content"),
            "published_at": _parse_published(r.get("published_date")),
            "raw": r,
        })
    return rows


def fetch_news(
    queries: list[str] | None = None,
    max_results: int = 5,
    api_key: str | None = None,
) -> list[dict]:
    """Query Tavily for recent ASU news across `queries`, dedupe by URL. Returns []
    when no API key is configured or on HTTP error (graceful, never raises)."""
    api_key = api_key if api_key is not None else settings.tavily_api_key
    if not api_key:
        return []
    queries = queries or DEFAULT_QUERIES
    by_url: dict[str, dict] = {}
    try:
        with httpx.Client(timeout=20) as client:
            for q in queries:
                resp = client.post(
                    SEARCH_URL,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"query": q, "topic": "news", "time_range": "week",
                          "max_results": max_results},
                )
                if resp.status_code != 200:
                    continue
                for row in parse_news_results(resp.json()):
                    by_url[row["source_key"]] = row
    except httpx.HTTPError:
        return list(by_url.values())
    return list(by_url.values())
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/test_news_parse.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/collagent/asu/news.py tests/test_news_parse.py
git commit -m "feat: Tavily news parser + resilient fetch_news

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: DB repository (upsert + recent read)

**Files:** Modify `src/collagent/db.py`; create `tests/test_db_news.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_db_news.py`:

```python
# tests/test_db_news.py
from unittest.mock import MagicMock

from collagent import db

ROW = {"id": "n1", "source": "tavily", "source_key": "https://news.asu.edu/chip",
       "title": "ASU lands grant", "url": "https://news.asu.edu/chip",
       "summary": "snippet", "published_at": None, "fetched_at": "2026-06-20T00:00:00Z"}


def _client():
    client = MagicMock()
    client.table.return_value.upsert.return_value.execute.return_value.data = [ROW]
    client.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value.data = [ROW]
    return client


def test_upsert_news_items_uses_conflict_target(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    db.upsert_news_items([ROW])
    _, kwargs = client.table.return_value.upsert.call_args
    assert kwargs.get("on_conflict") == "source,source_key"


def test_upsert_news_items_empty_noop(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    assert db.upsert_news_items([]) == []
    client.table.return_value.upsert.assert_not_called()


def test_get_recent_news_orders_by_fetched_and_limits(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    rows = db.get_recent_news(limit=12)
    assert rows[0].title == "ASU lands grant"
    client.table.return_value.select.return_value.order.assert_called_once_with("fetched_at", desc=True)
    client.table.return_value.select.return_value.order.return_value.limit.assert_called_once_with(12)
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_db_news.py -v`
Expected: FAIL — `module 'collagent.db' has no attribute 'upsert_news_items'`.

- [ ] **Step 3: Add the repository functions**

Add `NewsItem` to the `from collagent.models import (...)` block in `src/collagent/db.py`, then append:

```python
def upsert_news_items(rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    res = (
        get_client().table("news_items")
        .upsert(rows, on_conflict="source,source_key")
        .execute()
    )
    return res.data


def get_recent_news(limit: int = 12) -> list[NewsItem]:
    res = (
        get_client().table("news_items").select("*")
        .order("fetched_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [NewsItem(**row) for row in res.data]
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/test_db_news.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/collagent/db.py tests/test_db_news.py
git commit -m "feat: news_items repository (upsert + recent read)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: API routes (read + refresh)

**Files:** Create `src/collagent/api/routes/news.py`; modify `src/collagent/api/main.py`; create `tests/test_api_news.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_api_news.py`:

```python
# tests/test_api_news.py
from collagent.api.routes import news as news_routes
from collagent.models import NewsItem

ITEM = NewsItem(id="n1", title="ASU lands grant", url="https://news.asu.edu/chip",
                summary="snippet")


def test_get_news(client, monkeypatch):
    monkeypatch.setattr(news_routes.db, "get_recent_news", lambda **k: [ITEM])
    res = client.get("/api/news")
    assert res.status_code == 200
    assert res.json()[0]["title"] == "ASU lands grant"


def test_refresh_news_fetches_then_upserts(client, monkeypatch):
    calls = []
    monkeypatch.setattr(news_routes, "fetch_news",
                        lambda: calls.append("fetch") or [{"source": "tavily",
                        "source_key": "https://news.asu.edu/chip", "title": "ASU lands grant",
                        "url": "https://news.asu.edu/chip", "summary": "snippet",
                        "published_at": None, "raw": {}}])
    monkeypatch.setattr(news_routes.db, "upsert_news_items", lambda rows: calls.append("upsert"))
    monkeypatch.setattr(news_routes.db, "get_recent_news", lambda **k: [ITEM])
    res = client.post("/api/news/refresh", json={})
    assert res.status_code == 200
    assert calls == ["fetch", "upsert"]
    assert res.json()[0]["title"] == "ASU lands grant"


def test_news_unauthenticated_401():
    from fastapi.testclient import TestClient

    from collagent.api.main import app

    assert TestClient(app).get("/api/news").status_code == 401
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_api_news.py -v`
Expected: FAIL — `No module named 'collagent.api.routes.news'`.

- [ ] **Step 3: Implement the route**

Create `src/collagent/api/routes/news.py`:

```python
from fastapi import APIRouter, Depends

from collagent import db
from collagent.api.auth import get_current_user_id
from collagent.asu.news import fetch_news
from collagent.models import NewsItem

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("", response_model=list[NewsItem])
def read_news(_user_id: str = Depends(get_current_user_id)):
    """Recent cached ASU news (shared global cache, newest first)."""
    return db.get_recent_news()


@router.post("/refresh", response_model=list[NewsItem])
def refresh_news(_user_id: str = Depends(get_current_user_id)):
    """Re-ingest ASU news from Tavily, then return the recent cache. No-ops if the
    Tavily key is unset (returns whatever is already cached)."""
    rows = fetch_news()
    if rows:
        db.upsert_news_items(rows)
    return db.get_recent_news()
```

- [ ] **Step 4: Register the router**

In `src/collagent/api/main.py`, add `news` to the routes import (keep alphabetical) and include it after the calendar router:

```python
from collagent.api.routes import (
    calendar,
    chat,
    events,
    majormap,
    memory,
    news,
    people,
    profile,
    programs,
)
```

and:

```python
app.include_router(news.router)
```

- [ ] **Step 5: Run to verify they pass**

Run: `uv run pytest tests/test_api_news.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add src/collagent/api/routes/news.py src/collagent/api/main.py tests/test_api_news.py
git commit -m "feat: news API routes (GET recent, POST refresh)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Full verification + (optional live smoke) + finish

**Files:** none (verification only).

- [ ] **Step 1: Run the full backend suite**

Run: `uv run pytest -q`
Expected: all pass (the 115 from prior slices + the new news tests). Fix any red before continuing.

- [ ] **Step 2: Live ingestion smoke — ONLY if a Tavily key is set**

If `.env` has a real `TAVILY_API_KEY`, run from repo root:

```bash
uv run python -c "
from collagent.asu.news import fetch_news
rows = fetch_news()
print('items:', len(rows))
for r in rows[:5]:
    print(' -', r['title'], '|', r['url'])
"
```

Expected: several ASU news rows with titles + URLs. If no key is set, `fetch_news()` returns `[]` by design — note "skipped: Tavily key not configured" in the task and rely on the mocked unit tests (which fully cover parsing/dedupe/no-op).

- [ ] **Step 3: Confirm clean tree**

Run: `git status`
Expected: clean; `canvas-mcp/` still untracked and unstaged; no `.env` changes.

- [ ] **Step 4: Finish the branch**

Use **superpowers:finishing-a-development-branch** to present merge/PR options for `feat/v2-news`.

---

## Self-Review

**Spec coverage:**
- §4 `news_items` (source, source_key, title, url, summary, published_at, fetched_at, raw) → `NewsItem` model (T1) + upsert on `source,source_key` (T3); `raw` passed through in ingestion rows ✓. News has no per-user table — confirmed; per-user tuning deferred to the orchestrator ✓.
- §5 `refresh_news` does Tavily research → `fetch_news` (T2) + `POST /api/news/refresh` (T4) ✓. The orchestrator will call `fetch_news`/`upsert_news_items` and select the per-student subset into `dashboard_snapshots.news` (next plan).
- §3 ASU Happenings data → `GET /api/news` (T4); the visible cards are built in the dashboard plan (#5) ✓.
- §7/§12 free-tier + unset-key resilience → `fetch_news` no-ops without a key (T2) ✓.

**Placeholder scan:** none — every step has complete code/commands.

**Type consistency:** `NewsItem` fields match the `news_items` columns and the ingestion row keys (`source, source_key, title, url, summary, published_at` + `raw` for upsert). Upsert conflict target `source,source_key` matches the table's `unique (source, source_key)`. Functions defined before use: `parse_news_results`, `_parse_published`, `fetch_news` (T2); `upsert_news_items`, `get_recent_news` (T3).

**Scope:** global ingestion + API only — a self-contained, testable news surface mirroring events/calendar. Per-user tuning (orchestrator #4) and the visible section (dashboard #5) consume it later; out of scope here.
