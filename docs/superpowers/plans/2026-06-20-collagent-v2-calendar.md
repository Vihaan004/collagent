# Collagent v2 — Academic Calendar Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest the ASU academic calendar for the **current term only** into `calendar_items`, exposed via a read API + a refresh endpoint — the reusable core the orchestrator's `update_calendar` tool and the dashboard's Deadlines section will consume.

**Architecture:** Pure parsers over the registrar HTML (BeautifulSoup `html.parser`, the established `asu/events.py` pattern) → a resilient network `fetch_calendar()` that selects the current term and returns item dicts → `db` upsert/read functions → FastAPI `GET /api/calendar` + `POST /api/calendar/refresh`. Deterministic; no curation, no LLM. The `calendar_items` table already exists (migration `0004_foundation.sql`).

**Tech Stack:** Python 3.12, httpx, BeautifulSoup4 (`bs4`), FastAPI, Supabase (via `db.py`), pytest (`uv run pytest`).

**Source of truth:** `docs/superpowers/specs/2026-06-19-collagent-v2-dashboard-design.md` — §3 (Deadlines section), §4 (`calendar_items`), §5 (`update_calendar`, read-only to agent), §12 (calendar-extraction risk).

**Constraints (carry through every task):**
- **Supabase MCP only** for DB; project ref `qepwzwitwjhklxscrugr`. (No new migration needed — table exists.)
- **Never touch or commit `.env` / `.env.local`; never print secrets.**
- **Do NOT stage or touch the untracked `canvas-mcp/` directory.**
- Backend via `uv` (`uv run pytest`). Commit messages end with:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- Branch: `feat/v2-calendar` (already checked out).

---

## Real DOM (verified against the live page on 2026-06-20)

- Source: `https://registrar.asu.edu/academic-calendar`. Lists 5 terms (currently Summer 2026 → Fall 2027). **Decode UTF-8** (`resp.encoding = "utf-8"`) — the charset header is missing and en-dashes mangle otherwise.
- Each term: `<h2 class="calhd"><a id="summer2026" …></a> Summer 2026</h2>`.
- Immediately after the h2: a session-summary div, e.g.
  `<div style="font-size:14px;"><strong>Session A:</strong> Monday, 5/18/2026 – Friday, 6/26/2026<br><span><strong>Session B:</strong></span> Wednesday, 7/1/2026 – Tuesday, 8/11/2026<br>…Session C:… 5/18/2026 – 7/10/2026</div>`
  (dates in `m/d/yyyy`). Used only for **current-term detection**, not stored as items.
- Then `<table class="table acad footable">` of `<tr>` rows. Two row shapes:
  - **Single-date:** `<th class="…calitem" scope="row">Schedule of Classes Available</th><td colspan="4">…February 5, 2026…</td>`
  - **Per-session:** `<th …calitem>Classes Begin</th>` followed by three `<td class="…three-cols…">` cells each containing `Session A` + a date (`<div>Session A</div><div>May 18, 2026</div>`), then a trailing empty `<td>&nbsp;</td>`.
- Dates inside rows are full `Month D, YYYY` (e.g. `May 18, 2026`). ~25–35 rows/term.

---

## File Structure

**Created:**
- `src/collagent/asu/calendar.py` — pure parsers + `fetch_calendar()`.
- `src/collagent/api/routes/calendar.py` — `GET /api/calendar`, `POST /api/calendar/refresh`.
- `tests/fixtures/registrar_calendar.html` — captured real HTML (trimmed to the first two terms).
- `tests/test_calendar_parse.py`, `tests/test_db_calendar.py`, `tests/test_api_calendar.py`.

**Modified:**
- `src/collagent/models.py` — add `CalendarItem`.
- `src/collagent/db.py` — add `upsert_calendar_items`, `get_upcoming_calendar_items`.
- `src/collagent/api/main.py` — register the calendar router.

---

## Task 1: `CalendarItem` model

**Files:** Modify `src/collagent/models.py`; add a test to `tests/test_models.py`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_models.py`:

```python
def test_calendar_item_defaults_and_extra_ignored():
    from collagent.models import CalendarItem
    c = CalendarItem(id="c1", term="Summer 2026", session="A", title="Classes Begin",
                     date_start="2026-05-18")
    assert c.session == "A" and c.date_end is None and c.category is None
    full = CalendarItem(id="c1", term="Summer 2026", session="whole", title="X",
                        date_start="2026-05-18", date_end="2026-05-19", category="deadline",
                        fetched_at="2026-06-20T00:00:00Z", extra="ignored")
    assert full.category == "deadline" and full.date_end == "2026-05-19"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_models.py::test_calendar_item_defaults_and_extra_ignored -v`
Expected: FAIL — `cannot import name 'CalendarItem'`.

- [ ] **Step 3: Add the model**

Append to `src/collagent/models.py`:

```python
class CalendarItem(BaseModel):
    """A single academic-calendar entry for the current term. Mirrors a calendar_items row."""

    model_config = {"extra": "ignore"}

    id: str
    term: str
    session: str = "whole"
    title: str
    date_start: str | None = None
    date_end: str | None = None
    category: str | None = None
    fetched_at: str | None = None
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_models.py::test_calendar_item_defaults_and_extra_ignored -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/collagent/models.py tests/test_models.py
git commit -m "feat: add CalendarItem model

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Capture the HTML fixture

**Files:** Create `tests/fixtures/registrar_calendar.html`.

- [ ] **Step 1: Capture the live page, trimmed to the first two terms**

Run this from the repo root (writes a trimmed fixture — first two `<h2 class="calhd">` terms, enough to test current-term selection + both row shapes):

```bash
uv run python -c "
import re, httpx, pathlib
ua = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
r = httpx.get('https://registrar.asu.edu/academic-calendar', headers=ua, timeout=20, follow_redirects=True)
r.encoding = 'utf-8'
html = r.text
# Keep from the first calhd h2 up to the THIRD one (=> first two full term sections).
hs = [m.start() for m in re.finditer(r'<h2 class=\"calhd\">', html)]
seg = html[hs[0]:hs[2]] if len(hs) >= 3 else html[hs[0]:]
pathlib.Path('tests/fixtures').mkdir(parents=True, exist_ok=True)
pathlib.Path('tests/fixtures/registrar_calendar.html').write_text(seg, encoding='utf-8')
print('wrote', len(seg), 'chars;', len(hs), 'terms on page')
"
```

Expected: prints a positive char count and `5 terms on page` (or similar). The fixture now contains the first two term sections (Summer 2026 + Fall 2026).

- [ ] **Step 2: Sanity-check the fixture contents**

Run: `uv run python -c "t=open('tests/fixtures/registrar_calendar.html',encoding='utf-8').read(); print('Summer 2026' in t, 'Session A:' in t, 'Classes Begin' in t, 'three-cols' in t)"`
Expected: `True True True True`.

- [ ] **Step 3: Commit**

```bash
git add tests/fixtures/registrar_calendar.html
git commit -m "test: capture trimmed ASU registrar calendar fixture

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Date + category helpers

**Files:** Create `src/collagent/asu/calendar.py` (helpers only this task); create `tests/test_calendar_parse.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_calendar_parse.py`:

```python
# tests/test_calendar_parse.py
from collagent.asu import calendar as cal


def test_parse_date_full_month():
    assert cal.parse_date("February 5, 2026") == "2026-02-05"
    assert cal.parse_date("  May 18, 2026 ") == "2026-05-18"
    assert cal.parse_date("TBD") is None


def test_cell_dates_single_and_range():
    assert cal.cell_dates("Session A May 18, 2026") == ("2026-05-18", None)
    assert cal.cell_dates("March 8, 2027 – March 14, 2027") == ("2027-03-08", "2027-03-14")
    assert cal.cell_dates("\xa0") == (None, None)  # &nbsp;


def test_categorize():
    assert cal.categorize("Drop Deadline") == "deadline"
    assert cal.categorize("Last day to add") == "deadline"
    assert cal.categorize("Memorial Day Observed") == "holiday"
    assert cal.categorize("Spring Break") == "holiday"
    assert cal.categorize("Registration Dates Begin") == "registration"
    assert cal.categorize("Classes Begin") == "academic"
    assert cal.categorize("Schedule of Classes Available") == "registration"
    assert cal.categorize("Some random note") == "other"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_calendar_parse.py -v`
Expected: FAIL — `No module named 'collagent.asu.calendar'`.

- [ ] **Step 3: Create the module with helpers**

Create `src/collagent/asu/calendar.py`:

```python
# src/collagent/asu/calendar.py
"""ASU academic-calendar ingestion: current term only, deterministic (no LLM).
Pure parsers over the registrar HTML + a resilient network fetch. Mirrors the
BeautifulSoup pattern in asu/events.py."""
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

URL = "https://registrar.asu.edu/academic-calendar"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

_FULL_DATE = re.compile(r"[A-Z][a-z]+ \d{1,2}, \d{4}")
_MDY = re.compile(r"\d{1,2}/\d{1,2}/\d{4}")
_SESSION = re.compile(r"Session ([ABC])")
_SESSION_SPAN = re.compile(r"Session ([ABC]):\D*?(\d{1,2}/\d{1,2}/\d{4})\D+?(\d{1,2}/\d{1,2}/\d{4})")


def parse_date(text: str) -> str | None:
    """'February 5, 2026' -> '2026-02-05'. Returns None if not a full month-day-year date."""
    m = _FULL_DATE.search(text or "")
    if not m:
        return None
    try:
        return datetime.strptime(m.group(0), "%B %d, %Y").date().isoformat()
    except ValueError:
        return None


def cell_dates(text: str) -> tuple[str | None, str | None]:
    """Extract (start, end) from a table-cell's text. End is None unless the cell
    contains a second full date (a range like 'March 8, 2027 – March 14, 2027')."""
    found = _FULL_DATE.findall(text or "")
    if not found:
        return (None, None)
    start = parse_date(found[0])
    end = parse_date(found[1]) if len(found) > 1 else None
    return (start, end)


def categorize(title: str) -> str:
    t = (title or "").lower()
    if any(w in t for w in ("deadline", "last day", "due")):
        return "deadline"
    if any(w in t for w in ("holiday", "observed", "no classes", "break", "recess")):
        return "holiday"
    if any(w in t for w in ("registration", "enroll", "schedule of classes")):
        return "registration"
    if any(w in t for w in ("classes begin", "classes end", "commencement", "final exam", "convocation")):
        return "academic"
    return "other"
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_calendar_parse.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/collagent/asu/calendar.py tests/test_calendar_parse.py
git commit -m "feat: calendar date + category parsing helpers

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Term parsing + current-term selection

**Files:** Modify `src/collagent/asu/calendar.py`; add tests to `tests/test_calendar_parse.py`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_calendar_parse.py`:

```python
import pathlib

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "registrar_calendar.html"


def test_parse_session_spans():
    spans = cal.parse_session_spans(
        "Session A: Monday, 5/18/2026 – Friday, 6/26/2026  "
        "Session B: 7/1/2026 – 8/11/2026  Session C: 5/18/2026 – 7/10/2026"
    )
    assert spans["A"] == ("2026-05-18", "2026-06-26")
    assert spans["B"] == ("2026-07-01", "2026-08-11")
    assert spans["C"] == ("2026-05-18", "2026-07-10")


def test_parse_terms_from_fixture():
    terms = cal.parse_terms(FIXTURE.read_text(encoding="utf-8"))
    names = [t["term"] for t in terms]
    assert "Summer 2026" in names
    summer = next(t for t in terms if t["term"] == "Summer 2026")
    # span = earliest session start .. latest session end
    assert summer["span"][0] == "2026-05-18"
    assert summer["span"][1] >= "2026-08-11"


def test_select_current_term_in_session():
    spans = {"Summer 2026": ("2026-05-18", "2026-08-11"),
             "Fall 2026": ("2026-08-20", "2026-12-18")}
    assert cal.select_current_term(spans, "2026-06-20") == "Summer 2026"


def test_select_current_term_between_picks_next():
    spans = {"Summer 2026": ("2026-05-18", "2026-08-11"),
             "Fall 2026": ("2026-08-20", "2026-12-18")}
    assert cal.select_current_term(spans, "2026-08-15") == "Fall 2026"


def test_select_current_term_after_all_picks_last():
    spans = {"Summer 2026": ("2026-05-18", "2026-08-11")}
    assert cal.select_current_term(spans, "2027-01-01") == "Summer 2026"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_calendar_parse.py -k "session_spans or terms_from_fixture or current_term" -v`
Expected: FAIL — `module 'collagent.asu.calendar' has no attribute 'parse_session_spans'`.

- [ ] **Step 3: Add term parsing + selection**

Append to `src/collagent/asu/calendar.py`:

```python
def _mdy(text: str) -> str:
    return datetime.strptime(text, "%m/%d/%Y").date().isoformat()


def parse_session_spans(text: str) -> dict[str, tuple[str, str]]:
    """From a term's session-summary text, map 'A'/'B'/'C' -> (start_iso, end_iso)."""
    out: dict[str, tuple[str, str]] = {}
    for sess, start, end in _SESSION_SPAN.findall(text or ""):
        out[sess] = (_mdy(start), _mdy(end))
    return out


def parse_terms(html: str) -> list[dict]:
    """Each term -> {term, term_id, span (start_iso, end_iso), table (bs4 Tag|None)}.
    `span` is the earliest session start .. latest session end (used to pick the
    current term). Terms with no parseable session dates get span (None, None)."""
    soup = BeautifulSoup(html, "html.parser")
    terms: list[dict] = []
    for h2 in soup.select("h2.calhd"):
        anchor = h2.find("a")
        term_id = anchor.get("id") if anchor else None
        term_name = h2.get_text(" ", strip=True)
        # Walk forward siblings until the next term heading; grab the session div + table.
        sessions_text = ""
        table = None
        for sib in h2.next_siblings:
            name = getattr(sib, "name", None)
            if name == "h2" and "calhd" in (sib.get("class") or []):
                break
            if name == "div" and "Session" in sib.get_text():
                sessions_text += " " + sib.get_text(" ", strip=True)
            if name == "table" and "acad" in (sib.get("class") or []):
                table = sib
                break
        spans = parse_session_spans(sessions_text)
        if spans:
            starts = [s for s, _ in spans.values()]
            ends = [e for _, e in spans.values()]
            span = (min(starts), max(ends))
        else:
            span = (None, None)
        terms.append({"term": term_name, "term_id": term_id, "span": span, "table": table})
    return terms


def select_current_term(spans: dict[str, tuple[str, str]], today: str) -> str:
    """Pick the term whose span contains `today`; else the earliest upcoming term;
    else the last listed term. `spans` preserves page order."""
    for term, (start, end) in spans.items():
        if start and end and start <= today <= end:
            return term
    upcoming = sorted((start, term) for term, (start, _e) in spans.items() if start and start > today)
    if upcoming:
        return upcoming[0][1]
    return list(spans)[-1]
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_calendar_parse.py -v`
Expected: PASS (all parse tests so far).

- [ ] **Step 5: Commit**

```bash
git add src/collagent/asu/calendar.py tests/test_calendar_parse.py
git commit -m "feat: parse calendar terms + current-term selection

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Row parsing (single-date + per-session) + `fetch_calendar`

**Files:** Modify `src/collagent/asu/calendar.py`; add tests to `tests/test_calendar_parse.py`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_calendar_parse.py`:

```python
def test_parse_term_items_from_fixture():
    terms = cal.parse_terms(FIXTURE.read_text(encoding="utf-8"))
    summer = next(t for t in terms if t["term"] == "Summer 2026")
    items = cal.parse_term_items(summer)
    by_title = {}
    for it in items:
        by_title.setdefault(it["title"], []).append(it)

    # single-date row -> one 'whole' item
    sched = by_title["Schedule of Classes Available"]
    assert len(sched) == 1
    assert sched[0]["session"] == "whole" and sched[0]["date_start"] == "2026-02-05"

    # per-session row -> one item per session with its own date
    begins = {it["session"]: it["date_start"] for it in by_title["Classes Begin"]}
    assert begins["A"] == "2026-05-18"
    assert begins["B"] == "2026-07-01"
    assert begins["C"] == "2026-05-18"

    # every item carries term + a category
    assert all(it["term"] == "Summer 2026" for it in items)
    assert all(it["category"] for it in items)


def test_fetch_calendar_assembles_current_term(monkeypatch):
    html = FIXTURE.read_text(encoding="utf-8")

    class _Resp:
        status_code = 200
        text = html
        encoding = "utf-8"

    class _Client:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, *a, **k): return _Resp()

    monkeypatch.setattr(cal.httpx, "Client", _Client)
    rows = cal.fetch_calendar(today="2026-06-20")
    assert rows, "should return current-term items"
    assert {r["term"] for r in rows} == {"Summer 2026"}  # only the current term
    titles = {r["title"] for r in rows}
    assert "Classes Begin" in titles
    assert all("session" in r and "title" in r and "category" in r for r in rows)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_calendar_parse.py -k "term_items or fetch_calendar" -v`
Expected: FAIL — `no attribute 'parse_term_items'`.

- [ ] **Step 3: Add row parsing + fetch**

Append to `src/collagent/asu/calendar.py`:

```python
def parse_term_items(term: dict) -> list[dict]:
    """Turn a term's table into item dicts. Single-date rows -> one 'whole' item;
    per-session rows -> one item per Session A/B/C cell. Skips rows with no date."""
    table = term.get("table")
    if table is None:
        return []
    items: list[dict] = []
    for tr in table.select("tr"):
        th = tr.find("th")
        if th is None:
            continue
        title = re.sub(r"\s+", " ", th.get_text(" ", strip=True)).strip()
        if not title:
            continue
        tds = tr.find_all("td")
        session_cells = [td for td in tds if "three-cols" in (td.get("class") or [])]
        if session_cells:
            for td in session_cells:
                txt = td.get_text(" ", strip=True)
                start, end = cell_dates(txt)
                if not start:
                    continue
                sess = _SESSION.search(txt)
                items.append({
                    "term": term["term"],
                    "session": sess.group(1) if sess else "whole",
                    "title": title,
                    "date_start": start,
                    "date_end": end,
                    "category": categorize(title),
                })
        else:
            txt = " ".join(td.get_text(" ", strip=True) for td in tds)
            start, end = cell_dates(txt)
            if not start:
                continue
            items.append({
                "term": term["term"],
                "session": "whole",
                "title": title,
                "date_start": start,
                "date_end": end,
                "category": categorize(title),
            })
    return items


def fetch_calendar(today: str | None = None) -> list[dict]:
    """Fetch the registrar page, select the current term, return its item dicts.
    Network-bound; resilient — returns [] on HTTP error. `today` is an ISO date
    string (defaults to the real current date)."""
    from datetime import date

    today = today or date.today().isoformat()
    try:
        with httpx.Client(headers=UA, timeout=20, follow_redirects=True) as client:
            resp = client.get(URL)
            if resp.status_code != 200:
                return []
            resp.encoding = "utf-8"
            html = resp.text
    except httpx.HTTPError:
        return []

    terms = parse_terms(html)
    if not terms:
        return []
    spans = {t["term"]: t["span"] for t in terms}
    current_name = select_current_term(spans, today)
    current = next((t for t in terms if t["term"] == current_name), None)
    return parse_term_items(current) if current else []
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_calendar_parse.py -v`
Expected: PASS (all calendar-parse tests).

- [ ] **Step 5: Commit**

```bash
git add src/collagent/asu/calendar.py tests/test_calendar_parse.py
git commit -m "feat: parse calendar rows + assemble current-term fetch

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: DB repository (upsert + upcoming read)

**Files:** Modify `src/collagent/db.py`; create `tests/test_db_calendar.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_db_calendar.py` (mirrors `tests/test_db_people.py`):

```python
# tests/test_db_calendar.py
from unittest.mock import MagicMock

from collagent import db

ROW = {"id": "c1", "term": "Summer 2026", "session": "A", "title": "Classes Begin",
       "date_start": "2026-05-18", "date_end": None, "category": "academic",
       "fetched_at": "2026-06-20T00:00:00Z"}


def _client():
    client = MagicMock()
    client.table.return_value.upsert.return_value.execute.return_value.data = [ROW]
    client.table.return_value.select.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value.data = [ROW]
    return client


def test_upsert_calendar_items_uses_conflict_target(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    db.upsert_calendar_items([ROW])
    _, kwargs = client.table.return_value.upsert.call_args
    assert kwargs.get("on_conflict") == "term,session,title"


def test_upsert_calendar_items_empty_noop(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    assert db.upsert_calendar_items([]) == []
    client.table.return_value.upsert.assert_not_called()


def test_get_upcoming_calendar_items_filters_and_orders(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    rows = db.get_upcoming_calendar_items(since="2026-06-20", limit=10)
    assert rows[0].title == "Classes Begin"
    client.table.return_value.select.return_value.gte.assert_called_once_with("date_start", "2026-06-20")
    client.table.return_value.select.return_value.gte.return_value.order.assert_called_once_with("date_start")
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_db_calendar.py -v`
Expected: FAIL — `module 'collagent.db' has no attribute 'upsert_calendar_items'`.

- [ ] **Step 3: Add the repository functions**

Add `CalendarItem` to the `from collagent.models import (...)` block in `src/collagent/db.py`, then append:

```python
def upsert_calendar_items(rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    res = (
        get_client().table("calendar_items")
        .upsert(rows, on_conflict="term,session,title")
        .execute()
    )
    return res.data


def get_upcoming_calendar_items(
    since: str | None = None, limit: int = 50
) -> list[CalendarItem]:
    since = since or datetime.now(timezone.utc).date().isoformat()
    res = (
        get_client().table("calendar_items").select("*")
        .gte("date_start", since)
        .order("date_start")
        .limit(limit)
        .execute()
    )
    return [CalendarItem(**row) for row in res.data]
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_db_calendar.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/collagent/db.py tests/test_db_calendar.py
git commit -m "feat: calendar_items repository (upsert + upcoming read)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: API routes (read + refresh)

**Files:** Create `src/collagent/api/routes/calendar.py`; modify `src/collagent/api/main.py`; create `tests/test_api_calendar.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_api_calendar.py` (mirrors `tests/test_api_people.py`; `client` fixture from `conftest.py`):

```python
# tests/test_api_calendar.py
from collagent.api.routes import calendar as cal_routes
from collagent.models import CalendarItem

ITEM = CalendarItem(id="c1", term="Summer 2026", session="A", title="Classes Begin",
                    date_start="2026-05-18", category="academic")


def test_get_calendar(client, monkeypatch):
    monkeypatch.setattr(cal_routes.db, "get_upcoming_calendar_items", lambda **k: [ITEM])
    res = client.get("/api/calendar")
    assert res.status_code == 200
    assert res.json()[0]["title"] == "Classes Begin"
    assert res.json()[0]["session"] == "A"


def test_refresh_calendar_fetches_then_upserts(client, monkeypatch):
    calls = []
    monkeypatch.setattr(cal_routes, "fetch_calendar",
                        lambda: calls.append("fetch") or [{"term": "Summer 2026", "session": "A",
                        "title": "Classes Begin", "date_start": "2026-05-18", "date_end": None,
                        "category": "academic"}])
    monkeypatch.setattr(cal_routes.db, "upsert_calendar_items",
                        lambda rows: calls.append("upsert"))
    monkeypatch.setattr(cal_routes.db, "get_upcoming_calendar_items", lambda **k: [ITEM])
    res = client.post("/api/calendar/refresh", json={})
    assert res.status_code == 200
    assert calls == ["fetch", "upsert"]  # fetch before upsert
    assert res.json()[0]["title"] == "Classes Begin"


def test_calendar_unauthenticated_401():
    from fastapi.testclient import TestClient

    from collagent.api.main import app

    assert TestClient(app).get("/api/calendar").status_code == 401
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_api_calendar.py -v`
Expected: FAIL — `No module named 'collagent.api.routes.calendar'`.

- [ ] **Step 3: Implement the route**

Create `src/collagent/api/routes/calendar.py`:

```python
from fastapi import APIRouter, Depends

from collagent import db
from collagent.api.auth import get_current_user_id
from collagent.asu.calendar import fetch_calendar
from collagent.models import CalendarItem

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("", response_model=list[CalendarItem])
def read_calendar(_user_id: str = Depends(get_current_user_id)):
    """Upcoming current-term academic-calendar items (shared, not per-user)."""
    return db.get_upcoming_calendar_items()


@router.post("/refresh", response_model=list[CalendarItem])
def refresh_calendar(_user_id: str = Depends(get_current_user_id)):
    """Re-ingest the current term from the ASU registrar, then return upcoming items."""
    rows = fetch_calendar()
    if rows:
        db.upsert_calendar_items(rows)
    return db.get_upcoming_calendar_items()
```

- [ ] **Step 4: Register the router**

In `src/collagent/api/main.py`, add `calendar` to the routes import and include it after the memory router:

```python
from collagent.api.routes import calendar, chat, events, majormap, memory, people, profile, programs
```

and:

```python
app.include_router(calendar.router)
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/test_api_calendar.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add src/collagent/api/routes/calendar.py src/collagent/api/main.py tests/test_api_calendar.py
git commit -m "feat: calendar API routes (GET upcoming, POST refresh)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: Full verification + live smoke + finish

**Files:** none (verification only).

- [ ] **Step 1: Run the full backend suite**

Run: `uv run pytest -q`
Expected: all pass (the 98 from prior slices + the new calendar tests). Fix any red before continuing.

- [ ] **Step 2: Live ingestion smoke (network)**

Run from repo root:

```bash
uv run python -c "
from collagent.asu.calendar import fetch_calendar
rows = fetch_calendar()
print('items:', len(rows))
terms = {r['term'] for r in rows}
print('term(s):', terms)
for r in rows[:8]:
    print(' ', r['session'], r['date_start'], '-', r['title'], f\"({r['category']})\")
"
```

Expected: a single current term, a non-trivial item count (~20–35), dates look correct, and a mix of categories. Record the printed output in the task notes. (If the registrar markup has shifted since 2026-06-20 and counts look wrong, re-capture the fixture in Task 2 and adjust the parser — do not claim success on a broken parse.)

- [ ] **Step 3: Confirm clean tree**

Run: `git status`
Expected: clean; `canvas-mcp/` still untracked and unstaged; no `.env` changes.

- [ ] **Step 4: Finish the branch**

Use **superpowers:finishing-a-development-branch** to present merge/PR options for `feat/v2-calendar`.

---

## Self-Review

**Spec coverage:**
- §4 `calendar_items` (term, session, title, date_start, date_end, category) → `CalendarItem` (T1) + upsert on `term,session,title` (T6) ✓.
- §5 deterministic ingestion, current term only, read-only to agent → pure parsers + `fetch_calendar` (T3–T5), no LLM, no per-user data; agent write path not added (it'll call `fetch_calendar`/`upsert_calendar_items` read-only-to-students via the orchestrator) ✓.
- §3 Deadlines section data → `GET /api/calendar` returns upcoming items (T7); the visible section is built in the dashboard plan (#5), as scoped ✓.
- §12 calendar-extraction risk (current-term + Session A/B/C) → `select_current_term` (T4) + per-session row parsing (T5), tested against a real captured fixture (T2) ✓.

**Placeholder scan:** none — every step has complete code/commands.

**Type consistency:** `CalendarItem` fields match the migration columns and the parser item dict keys (`term, session, title, date_start, date_end, category`). Functions referenced before definition are all defined: `parse_date`, `cell_dates`, `categorize` (T3); `parse_session_spans`, `parse_terms`, `select_current_term` (T4); `parse_term_items`, `fetch_calendar` (T5); `upsert_calendar_items`, `get_upcoming_calendar_items` (T6). Upsert conflict target `term,session,title` matches the table's `unique (term, session, title)`.

**Scope:** backend ingestion + API only — a self-contained, testable calendar surface. UI (dashboard #5) and the orchestrator `update_calendar` tool (#4) consume it later, explicitly out of scope here.
