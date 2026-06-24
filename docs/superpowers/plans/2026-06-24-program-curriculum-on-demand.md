# Program Curriculum (On-Demand) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the agent and the profile page read a student's official ASU degree curriculum on demand — no Playwright, no DB table, no structured schema.

**Architecture:** Enrich the existing `data/asu_programs.json` once with a discovered `checksheet_url` per program. A new `checksheet.py` fetches a checksheet URL and renders the requirement tables to clean markdown, behind an in-memory cache. A `read_curriculum` agent tool and a `GET /api/curriculum` route both resolve the signed-in user's `acad_plan_code` → URL → cached markdown. The profile page swaps its dead per-user major-map editor for a read-only curriculum view.

**Tech Stack:** Python 3.12, FastAPI, LangGraph, httpx, BeautifulSoup; Next.js 16 (App Router), react-markdown.

**Spec:** `docs/superpowers/specs/2026-06-24-program-curriculum-on-demand-design.md`

**Branch:** Do all work on `feat/program-curriculum` (branch off `main`). `main` auto-deploys, so it stays clean until review. The Dockerfile fix (`296f7de`) and the spec are already on `main` and are prerequisites — do not redo them.

---

## File Structure

- `tests/fixtures/checksheet_baaccbs.html` — captured checksheet HTML (test asset).
- `src/collagent/asu/checksheet.py` (create) — `render_checksheet_markdown`, `fetch_curriculum` (cached), `prewarm`.
- `src/collagent/asu/programs.py` (modify) — add `get_checksheet_url`.
- `src/collagent/curriculum_tools.py` (create) — `make_curriculum_tools(user_id)` → `read_curriculum`.
- `src/collagent/api/routes/chat.py` (modify) — wire the new tool.
- `src/collagent/api/routes/curriculum.py` (create) — `GET /api/curriculum`.
- `src/collagent/api/main.py` (modify) — register the curriculum router.
- `scripts/enrich_program_links.py` (create) — one-time offline JSON enrichment.
- `data/asu_programs.json` (modify, via the script) — gains `checksheet_url`.
- `frontend/lib/types.ts` (modify) — `CurriculumView` type.
- `frontend/app/profile/page.tsx` (modify) — remove major-map editor, add curriculum view.

---

### Task 1: Capture the checksheet test fixture

**Files:**
- Create: `tests/fixtures/checksheet_baaccbs.html`

- [ ] **Step 1: Fetch the Accountancy checksheet into the fixtures dir**

Run (from repo root):
```bash
mkdir -p tests/fixtures && uv run python -c "import httpx; open('tests/fixtures/checksheet_baaccbs.html','w',encoding='utf-8').write(httpx.get('https://degrees.apps.asu.edu/checksheet/2026/CBA/BAACCBS/null', headers={'User-Agent':'Mozilla/5.0'}, timeout=30, follow_redirects=True).text)"
```
Expected: file created, ~190 KB.

- [ ] **Step 2: Sanity-check it contains the checksheet markup**

Run: `grep -c "checksheet-requirement" tests/fixtures/checksheet_baaccbs.html`
Expected: a number ≥ 30.

- [ ] **Step 3: Commit**

```bash
git add tests/fixtures/checksheet_baaccbs.html
git commit -m "test: capture ASU Accountancy checksheet fixture"
```

---

### Task 2: Checksheet rendering + cached fetch

**Files:**
- Create: `src/collagent/asu/checksheet.py`
- Test: `tests/test_checksheet.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_checksheet.py
from pathlib import Path

import httpx

from collagent.asu import checksheet

FIXTURE = Path(__file__).parent / "fixtures" / "checksheet_baaccbs.html"


def test_render_extracts_sections_and_requirements():
    md = checksheet.render_checksheet_markdown(FIXTURE.read_text(encoding="utf-8"))
    assert "## Business Core" in md          # subsection header
    assert "FIN 300" in md and "OR FIN 303" in md  # OR-group kept as text
    assert "Expand all" not in md            # page chrome dropped
    assert "Credit Hours Minimum" not in md  # per-row boilerplate stripped


def test_fetch_curriculum_caches(monkeypatch):
    checksheet._CACHE.clear()
    calls = {"n": 0}

    def fake_get(url, **kw):
        calls["n"] += 1
        html = "<tr class='checksheet-requirement'><td>X 100 Foo</td><td>C</td><td>3</td></tr>"
        return httpx.Response(200, text=html, request=httpx.Request("GET", url))

    monkeypatch.setattr(checksheet.httpx, "get", fake_get)
    first = checksheet.fetch_curriculum("http://example/cs")
    second = checksheet.fetch_curriculum("http://example/cs")
    assert calls["n"] == 1          # second call served from cache
    assert first == second
    assert "X 100 Foo" in first
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_checksheet.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'collagent.asu.checksheet'`.

- [ ] **Step 3: Implement `checksheet.py`**

```python
# src/collagent/asu/checksheet.py
"""Fetch an ASU checksheet URL and render its requirement tables to clean
markdown, cached in-memory. No Playwright, no structured schema — the page's
own text is the source of truth (see the 2026-06-24 spec)."""
from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
# "3 Credit Hours Minimum Grade:C" trails every requirement label — drop it.
_CREDIT_TAIL = re.compile(r"\s*\d+(?:\.\d+)?\s*Credit Hours.*$", re.IGNORECASE | re.DOTALL)
_WS = re.compile(r"\s+")
_CACHE: dict[str, str] = {}


def _clean(text: str) -> str:
    return _WS.sub(" ", text.replace("\xa0", " ")).strip()


def render_checksheet_markdown(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    lines: list[str] = []
    for tr in soup.find_all("tr"):
        sub = tr.find("td", class_="subsection-name")
        if sub is not None:
            lines.append(f"\n## {_clean(sub.get_text())}")
            continue
        if "checksheet-requirement" not in (tr.get("class") or []):
            continue
        tds = tr.find_all("td", recursive=False)
        if not tds:
            continue
        label = _clean(_CREDIT_TAIL.sub("", tds[0].get_text()))
        if not label:
            continue
        credits = _clean(tds[2].get_text()) if len(tds) > 2 else ""
        lines.append(f"- {label}" + (f" — {credits} cr" if credits else ""))
    return "\n".join(lines).strip()


def fetch_curriculum(url: str) -> str:
    if url not in _CACHE:
        resp = httpx.get(url, headers=UA, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        _CACHE[url] = render_checksheet_markdown(resp.text)
    return _CACHE[url]


def prewarm(urls: list[str]) -> None:
    """Optional: fetch a set of checksheets ahead of a demo. Best-effort."""
    for u in urls:
        try:
            fetch_curriculum(u)
        except Exception:
            pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_checksheet.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/collagent/asu/checksheet.py tests/test_checksheet.py
git commit -m "feat: checksheet markdown rendering + cached fetch"
```

---

### Task 3: Look up a program's checksheet URL

**Files:**
- Modify: `src/collagent/asu/programs.py`
- Test: `tests/test_programs.py`

- [ ] **Step 1: Write the failing test (append to `tests/test_programs.py`)**

```python
def test_get_checksheet_url(tmp_path, monkeypatch):
    data = [
        {"code": "BAACCBS", "slug": "accountancy", "name": "Accountancy,BS",
         "checksheet_url": "https://degrees.apps.asu.edu/checksheet/2026/CBA/BAACCBS/null"},
        {"code": "ZZZ", "slug": "z", "name": "Z"},  # no checksheet_url
    ]
    path = tmp_path / "programs.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(programs, "DATA_PATH", path)
    programs._load_programs_cached.cache_clear()

    assert programs.get_checksheet_url("BAACCBS").endswith("/BAACCBS/null")
    assert programs.get_checksheet_url("ZZZ") is None    # present, no link
    assert programs.get_checksheet_url("NOPE") is None    # absent
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_programs.py::test_get_checksheet_url -v`
Expected: FAIL with `AttributeError: module ... has no attribute 'get_checksheet_url'`.

- [ ] **Step 3: Add `get_checksheet_url` to `programs.py`** (append after `search_programs`)

```python
def get_checksheet_url(code: str) -> str | None:
    for p in load_programs():
        if p.get("code") == code:
            return p.get("checksheet_url")
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_programs.py -v`
Expected: PASS (all program tests pass).

- [ ] **Step 5: Commit**

```bash
git add src/collagent/asu/programs.py tests/test_programs.py
git commit -m "feat: get_checksheet_url lookup by program code"
```

---

### Task 4: `read_curriculum` agent tool

**Files:**
- Create: `src/collagent/curriculum_tools.py`
- Test: `tests/test_curriculum_tools.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_curriculum_tools.py
import types

from collagent import curriculum_tools


def _tools(uid="u1"):
    return {t.name: t for t in curriculum_tools.make_curriculum_tools(uid)}


def test_read_curriculum_uses_profile_major(monkeypatch):
    monkeypatch.setattr(curriculum_tools, "get_checksheet_url", lambda code: f"http://x/{code}")
    monkeypatch.setattr(curriculum_tools, "fetch_curriculum", lambda url: f"CURRIC {url}")
    monkeypatch.setattr(
        curriculum_tools.db, "get_profile",
        lambda uid: types.SimpleNamespace(acad_plan_code="BAACCBS"),
    )
    out = _tools()["read_curriculum"].invoke({})
    assert "CURRIC http://x/BAACCBS" in out


def test_read_curriculum_explicit_code(monkeypatch):
    monkeypatch.setattr(curriculum_tools, "get_checksheet_url", lambda code: f"http://x/{code}")
    monkeypatch.setattr(curriculum_tools, "fetch_curriculum", lambda url: "OK")
    out = _tools()["read_curriculum"].invoke({"program_code": "ESCSEBS"})
    assert out == "OK"


def test_read_curriculum_no_major(monkeypatch):
    monkeypatch.setattr(
        curriculum_tools.db, "get_profile",
        lambda uid: types.SimpleNamespace(acad_plan_code=None),
    )
    out = _tools()["read_curriculum"].invoke({})
    assert "no major" in out.lower()


def test_read_curriculum_no_url(monkeypatch):
    monkeypatch.setattr(curriculum_tools, "get_checksheet_url", lambda code: None)
    out = _tools()["read_curriculum"].invoke({"program_code": "ZZZ"})
    assert "no published curriculum" in out.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_curriculum_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'collagent.curriculum_tools'`.

- [ ] **Step 3: Implement `curriculum_tools.py`**

```python
# src/collagent/curriculum_tools.py
"""Per-user tool: read an ASU program's official curriculum on demand."""
from langchain.tools import tool

from collagent import db
from collagent.asu.checksheet import fetch_curriculum
from collagent.asu.programs import get_checksheet_url


def make_curriculum_tools(user_id: str) -> list:
    @tool("read_curriculum")
    def read_curriculum(program_code: str | None = None) -> str:
        """Read an ASU bachelor's program's official course requirements
        (the degree checksheet) as text. Omit program_code to use the student's
        own major; pass a program_code (e.g. 'ESCSEBS') to inspect another
        program. To turn a program name into a code, use the program search tool."""
        code = program_code
        if code is None:
            profile = db.get_profile(user_id)
            code = profile.acad_plan_code if profile else None
            if not code:
                return ("No major on file yet — ask the student which program "
                        "they're in, then look up its code with program search.")
        url = get_checksheet_url(code)
        if not url:
            return f"No published curriculum found for program '{code}'."
        try:
            return fetch_curriculum(url)
        except Exception:
            return ("Couldn't load that curriculum right now (the ASU page was "
                    "unavailable). Try again in a moment.")

    return [read_curriculum]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_curriculum_tools.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/collagent/curriculum_tools.py tests/test_curriculum_tools.py
git commit -m "feat: read_curriculum agent tool"
```

---

### Task 5: Wire the tool into the chat agent

**Files:**
- Modify: `src/collagent/api/routes/chat.py`

- [ ] **Step 1: Add the import** (with the other `make_*_tools` imports, ~line 11–15)

```python
from collagent.curriculum_tools import make_curriculum_tools
```

- [ ] **Step 2: Add the tool to `extra_tools`** (inside `create_graph(...)`, in the `extra_tools=(...)` tuple)

```python
        extra_tools=(
            tuple(make_profile_tools(user_id))
            + tuple(make_event_tools(user_id))
            + tuple(make_people_tools(user_id))
            + tuple(make_memory_tools(user_id))
            + tuple(make_dashboard_tools(user_id))
            + tuple(make_curriculum_tools(user_id))
        ),
```

- [ ] **Step 3: Verify the app imports and the tool is registered**

Run:
```bash
uv run python -c "from collagent.curriculum_tools import make_curriculum_tools; print([t.name for t in make_curriculum_tools('u1')])"
```
Expected: `['read_curriculum']`

Run: `uv run python -c "import collagent.api.main"`
Expected: no error.

- [ ] **Step 4: Commit**

```bash
git add src/collagent/api/routes/chat.py
git commit -m "feat: register read_curriculum in the chat agent"
```

---

### Task 6: `GET /api/curriculum` route

**Files:**
- Create: `src/collagent/api/routes/curriculum.py`
- Modify: `src/collagent/api/main.py`
- Test: `tests/test_api_curriculum.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_api_curriculum.py
import types

from collagent.api.routes import curriculum as cur_routes


def test_curriculum_returns_markdown(client, monkeypatch):
    monkeypatch.setattr(
        cur_routes.db, "get_profile",
        lambda uid: types.SimpleNamespace(acad_plan_code="BAACCBS", major_name="Accountancy,BS"),
    )
    monkeypatch.setattr(cur_routes, "get_checksheet_url", lambda code: "http://x/BAACCBS")
    monkeypatch.setattr(cur_routes, "fetch_curriculum", lambda url: "## Core\n- ACC 231")
    res = client.get("/api/curriculum")
    assert res.status_code == 200
    body = res.json()
    assert body["program_name"] == "Accountancy,BS"
    assert body["markdown"].startswith("## Core")


def test_curriculum_empty_when_no_major(client, monkeypatch):
    monkeypatch.setattr(
        cur_routes.db, "get_profile",
        lambda uid: types.SimpleNamespace(acad_plan_code=None, major_name=None),
    )
    monkeypatch.setattr(cur_routes, "get_checksheet_url", lambda code: None)
    res = client.get("/api/curriculum")
    assert res.status_code == 200
    assert res.json()["markdown"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api_curriculum.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'collagent.api.routes.curriculum'`.

- [ ] **Step 3: Implement the route**

```python
# src/collagent/api/routes/curriculum.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from collagent import db
from collagent.api.auth import get_current_user_id
from collagent.asu.checksheet import fetch_curriculum
from collagent.asu.programs import get_checksheet_url

router = APIRouter(prefix="/api/curriculum", tags=["curriculum"])


class CurriculumView(BaseModel):
    program_name: str | None
    checksheet_url: str | None
    markdown: str | None


@router.get("", response_model=CurriculumView)
def read_curriculum(user_id: str = Depends(get_current_user_id)):
    profile = db.get_profile(user_id)
    code = profile.acad_plan_code if profile else None
    name = profile.major_name if profile else None
    url = get_checksheet_url(code) if code else None
    markdown = None
    if url:
        try:
            markdown = fetch_curriculum(url)
        except Exception:
            markdown = None  # surface as empty state, never 500
    return CurriculumView(program_name=name, checksheet_url=url, markdown=markdown)
```

- [ ] **Step 4: Register the router in `main.py`**

Add `curriculum` to the import tuple (with the other route modules):
```python
from collagent.api.routes import (
    calendar,
    chat,
    curriculum,
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
Add the include (next to the others):
```python
app.include_router(curriculum.router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_api_curriculum.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add src/collagent/api/routes/curriculum.py src/collagent/api/main.py tests/test_api_curriculum.py
git commit -m "feat: GET /api/curriculum"
```

---

### Task 7: One-time program-link enrichment script

**Files:**
- Create: `scripts/enrich_program_links.py`
- Modify: `data/asu_programs.json` (produced by running the script)

- [ ] **Step 1: Create the script**

```python
# scripts/enrich_program_links.py
"""One-time, offline: add `checksheet_url` to each program in
data/asu_programs.json by discovering it from the program's detail page.
Re-run when ASU publishes a new catalog year.

Run: uv run python scripts/enrich_program_links.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

DATA = Path(__file__).resolve().parents[1] / "data" / "asu_programs.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
DETAIL = "https://degrees.apps.asu.edu/bachelors/major/ASU00/{code}/{slug}"
CHECKSHEET_HREF = re.compile(r"/checksheet/\d{4}/[A-Z]+/[A-Z0-9]+/\w+")


def discover(client: httpx.Client, code: str, slug: str) -> str | None:
    r = client.get(DETAIL.format(code=code, slug=slug))
    if r.status_code != 200:
        return None
    m = CHECKSHEET_HREF.search(r.text)
    return f"https://degrees.apps.asu.edu{m.group(0)}" if m else None


def main() -> None:
    programs = json.loads(DATA.read_text(encoding="utf-8"))
    ok, failures = 0, []
    with httpx.Client(headers=UA, timeout=30, follow_redirects=True) as client:
        for p in programs:
            url = discover(client, p["code"], p["slug"])
            if url:
                p["checksheet_url"] = url
                ok += 1
            else:
                failures.append(p["code"])
            print(f"{p['code']:<12} {'OK' if url else 'FAIL'}")
    DATA.write_text(json.dumps(programs, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\n{ok}/{len(programs)} linked. failures: {failures}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it once** (network; ~441 requests, a few minutes)

Run: `uv run python scripts/enrich_program_links.py`
Expected: a per-program OK/FAIL log, then a summary like `4xx/441 linked. failures: [...]`. Most should be OK; note any failures (they simply won't get a curriculum link).

- [ ] **Step 3: Verify a known entry got its link**

Run: `uv run python -c "from collagent.asu.programs import get_checksheet_url; print(get_checksheet_url('BAACCBS'))"`
Expected: `https://degrees.apps.asu.edu/checksheet/2026/CBA/BAACCBS/null`

- [ ] **Step 4: Commit the script and the enriched data**

```bash
git add scripts/enrich_program_links.py data/asu_programs.json
git commit -m "feat: enrich program directory with checksheet URLs"
```

---

### Task 8: Profile page — replace major-map editor with curriculum view

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/app/profile/page.tsx`

- [ ] **Step 1: Add the `CurriculumView` type** (append to `frontend/lib/types.ts`)

```ts
export interface CurriculumView {
  program_name: string | null;
  checksheet_url: string | null;
  markdown: string | null;
}
```

- [ ] **Step 2: Replace `frontend/app/profile/page.tsx` with the curriculum version**

```tsx
"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CurriculumView, Memory, Profile } from "@/lib/types";
import Markdown from "@/components/ui/Markdown";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { Spinner } from "@/components/ui/States";

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [interests, setInterests] = useState("");
  const [clubs, setClubs] = useState("");
  const [goals, setGoals] = useState("");
  const [saved, setSaved] = useState(false);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [curriculum, setCurriculum] = useState<CurriculumView | null>(null);
  const [curriculumLoading, setCurriculumLoading] = useState(true);

  useEffect(() => {
    api.get("/api/profile").then((p: Profile) => {
      setProfile(p);
      setInterests(p.interests.join(", "));
      setClubs(p.clubs.join(", "));
      setGoals(p.goals ?? "");
    });
    api.get("/api/memory").then(setMemories);
    api
      .get("/api/curriculum")
      .then(setCurriculum)
      .catch(() => setCurriculum(null))
      .finally(() => setCurriculumLoading(false));
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

  async function forget(id: string) {
    setMemories((ms) => ms.filter((m) => m.id !== id));
    await api.del(`/api/memory/${id}`);
  }

  if (!profile) return <main className="p-6"><Spinner /></main>;

  return (
    <main className="mx-auto max-w-2xl space-y-8 p-6">
      <header>
        <h1 className="font-display text-3xl leading-tight text-ink">
          {profile.full_name ?? profile.email}
        </h1>
        <p className="mt-1 text-sm text-muted">
          {profile.major_name} · {profile.academic_year}
        </p>
      </header>

      <Card>
        <form onSubmit={save} className="space-y-4">
          <Field label="Interests">
            <Input value={interests} onChange={(e) => setInterests(e.target.value)} />
          </Field>
          <Field label="Clubs">
            <Input value={clubs} onChange={(e) => setClubs(e.target.value)} />
          </Field>
          <Field label="Goals">
            <Textarea value={goals} onChange={(e) => setGoals(e.target.value)} rows={2} />
          </Field>
          <Button type="submit" variant={saved ? "accent" : "primary"}>
            {saved ? "Saved ✓" : "Save"}
          </Button>
        </form>
      </Card>

      <section>
        <h2 className="mb-3 font-display text-xl text-ink">Your curriculum</h2>
        {curriculumLoading ? (
          <Spinner />
        ) : curriculum?.markdown ? (
          <Card>
            <Markdown>{curriculum.markdown}</Markdown>
            {curriculum.checksheet_url && (
              <a
                href={curriculum.checksheet_url}
                target="_blank"
                rel="noreferrer"
                className="mt-4 inline-block text-xs text-muted underline hover:text-ink"
              >
                View official ASU checksheet
              </a>
            )}
          </Card>
        ) : (
          <p className="text-sm text-muted">
            No curriculum on file for your program yet.
          </p>
        )}
      </section>

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
    </main>
  );
}
```

- [ ] **Step 3: Typecheck, lint, build**

Run (from `frontend/`):
```bash
npx tsc --noEmit && npm run lint && npm run build
```
Expected: no type errors, no lint errors, successful build. (No remaining references to `MajorMapEditor`, `MajorMapCourse`, `CourseStatus`, or `/api/major-map` in `profile/page.tsx`.)

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/types.ts frontend/app/profile/page.tsx
git commit -m "feat: profile curriculum view, drop dead major-map editor"
```

---

### Task 9: Full verification + cleanup + finish

**Files:**
- Delete: `scratch/` (throwaway probe)

- [ ] **Step 1: Run the full backend test suite**

Run: `uv run pytest --deselect "tests/test_majormap.py::test_extraction_on_real_fixture" -q`
Expected: all pass. (That one deselected test is a live ASU+LLM integration test, slow/unreliable, unrelated to this work.)

- [ ] **Step 2: Confirm the frontend gate is green**

Run (from `frontend/`): `npx tsc --noEmit && npm run lint && npm run build`
Expected: clean.

- [ ] **Step 3: Live smoke (manual)**

With backend (`uv run uvicorn collagent.api.main:app --reload`) and frontend (`npm run dev`) running and signed in:
- Profile page shows a "Your curriculum" section with the student's requirements rendered as markdown, plus the "View official ASU checksheet" link.
- In chat, ask "what classes does my major require?" — the agent calls `read_curriculum` and answers from the checksheet text.

- [ ] **Step 4: Delete the throwaway probe**

```bash
git rm -r --cached scratch 2>/dev/null; rm -rf scratch
```
(`scratch/` was never committed; this just removes the local working copy.)

- [ ] **Step 5: Finish the branch**

Use **superpowers:finishing-a-development-branch** to merge `feat/program-curriculum` into `main` (which auto-deploys to Render/Vercel). Reminder: `MAJOR_MAP_ENABLED` stays `false`; this feature does not depend on it.

---

## Notes / Risks

- **Catalog year** is baked into each stored `checksheet_url` (`2026`). Re-run `scripts/enrich_program_links.py` when ASU publishes a new year.
- **Cache is in-memory** and shared by the tool and the route; it resets on each Render restart (first curriculum read after a deploy re-fetches). Fine for the demo.
- **Enrichment failures** (programs with no discoverable checksheet) simply have no `checksheet_url`; the tool and route degrade to a clean empty state.
- **`set_course_status`** in `profile_tools.py` still references the dormant major map and will always say "not found" now. Left untouched (out of scope; keeps `majormap-enabled` parity). Remove later if it confuses the agent.
