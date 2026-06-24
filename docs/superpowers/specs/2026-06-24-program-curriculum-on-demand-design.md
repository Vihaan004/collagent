# Program Curriculum (On-Demand) — Design

**Status:** Approved direction, pending spec review
**Date:** 2026-06-24
**Supersedes:** the disabled per-user Playwright major-map extraction (kept dormant on `main`, alive on `majormap-enabled`).

## Goal

Give the agent access to a student's official ASU degree curriculum **without Playwright, without a new DB table, and without a brittle structured schema** — by storing a link to each program's checksheet and fetching+cleaning it on demand at chat time, with a cache for demo resilience.

## Background / why this shape

- Onboarding's major **search** reads a static `data/asu_programs.json` (441 bachelor's programs) — it never used Playwright. It broke in deploy only because the Dockerfile didn't ship `data/`. **That is already fixed** (`296f7de`, `COPY data ./data`).
- The disabled feature was per-user, live **major-map roadmap** extraction (`webapp4.asu.edu`, JS-rendered → needed Chromium). We are **not** restoring that.
- ASU's `degrees.apps.asu.edu/checksheet/...` pages are **server-rendered** (plain HTML), so curriculum is reachable with `httpx` + `BeautifulSoup`.
- A throwaway probe (`scratch/`) confirmed end-to-end extraction across 5 colleges (Business, Engineering ×2, Liberal Arts, Integrative Sciences). It also confirmed that a **strict** structured schema is the wrong call: core course lists parse cleanly, but **AND/OR nesting** and **elective pools** (≈150 options for one requirement) do not reduce to clean fields without lossy guessing. A wrong structured field misleads the agent more than honest messy text. So we keep the page's own text, lightly cleaned — no schema.

## Approach

1. **No DB table, no migration, no curriculum schema.** Keep `data/asu_programs.json` as the only program store.
2. **Enrich the JSON once** with a `checksheet_url` per program — the URL is *discovered* from each program's detail page (the college segment cannot be constructed; it differs from the program code, e.g. `ESCSEBS` → college `CES`).
3. **`read_curriculum` agent tool** fetches the checksheet on demand, extracts just the checksheet tables, returns **clean markdown/text** (section headers + requirement lines with codes / OR-groups / credits). No structured parsing.
4. **In-memory write-through cache** keyed by URL so repeats are instant and ASU is hit at most once per program per process. Optional pre-warm for a demo.

## Tech stack

Python 3.12, FastAPI, LangGraph (existing chat/tool wiring), `httpx`, `beautifulsoup4`. No Playwright, no new infra, no DB changes.

## Components / files

### 1. `data/asu_programs.json` (modify, via one-time script)
Each entry gains an optional `checksheet_url`:
```json
{ "code": "BAACCBS", "slug": "accountancy", "name": "Accountancy,BS",
  "checksheet_url": "https://degrees.apps.asu.edu/checksheet/2026/CBA/BAACCBS/null" }
```
Programs whose checksheet can't be discovered keep no `checksheet_url`; the tool degrades gracefully for them.

### 2. `scripts/enrich_program_links.py` (create — offline, manual, throwaway-grade)
- For each program in the JSON: GET `https://degrees.apps.asu.edu/bachelors/major/ASU00/{code}/{slug}`, find the `/checksheet/{year}/{college}/{code}/...` href, write it back.
- Idempotent; re-runnable when the catalog year rolls over.
- Prints a pass/fail summary (`N/441 linked, failures: [...]`) so stragglers are visible.
- Run once by hand; not part of the app runtime.

### 3. `src/collagent/asu/checksheet.py` (create)
Single responsibility: turn a checksheet URL into clean curriculum text.
- `render_checksheet_markdown(html: str) -> str` — pure function. Selects `td.subsection-name` (section headers) and `tr.checksheet-requirement` rows from the checksheet tables; emits lines like:
  - `## Business Core`
  - `- FIN 300 Fundamentals of Finance OR FIN 303 Honors Finance — 3 cr`
  Drops page chrome (nav, "Expand all", duplicate decorative lists). This is the probe's printer logic, minus the rigid JSON.
- `fetch_curriculum(url: str) -> str` — `httpx` GET (UA header, follow redirects, timeout) → `render_checksheet_markdown`. Wrapped in an in-memory cache (`functools.lru_cache` or a module dict keyed by URL). Write-through: first call fetches, later calls return cached text.
- `prewarm(urls: list[str]) -> None` — optional; fetch a small set ahead of a demo. Not called automatically.

### 4. `src/collagent/asu/programs.py` (modify)
- Add `get_checksheet_url(code: str) -> str | None` — look up a program's `checksheet_url` from the loaded JSON by `code`.

### 5. Agent tool — `read_curriculum` (wire into the existing tool set)
- Signature: `read_curriculum(program_code: str | None = None)` — **code only**.
  - Default (`None`): resolve the signed-in user's `profile.acad_plan_code`.
  - Explicit code: let the agent inspect *another* program ("what does the CS degree require?"). Name→code resolution is the agent's job via the existing program-search tool; this tool does not take names.
- Body: code → `get_checksheet_url` → `fetch_curriculum` → return markdown.
- Graceful failures: no profile major → "No major on file yet"; no `checksheet_url` → "No published curriculum for that program"; fetch error → short apology, no crash.
- Registered alongside the other agent tools; same auth/user-context plumbing the existing tools use.

### 6. API — `GET /api/curriculum` (create)
Authenticated route so the browser (profile page) can show curriculum without going through the agent.
- Resolves the signed-in user's `profile.acad_plan_code` → `get_checksheet_url` → `fetch_curriculum` (shared cache with the tool).
- Returns `{ program_name, checksheet_url, markdown }`; or `{ program_name, checksheet_url: null, markdown: null }` when there's no major/url (frontend shows an empty-state message instead of erroring).

### 7. Frontend — profile page (`frontend/app/profile/page.tsx`, modify)
- **Remove** the now-defunct per-user major-map: the `/api/major-map` fetch (line 27), the `toggle` handler + `/api/major-map/statuses` call, the `MajorMapEditor` import, and the `courses`/`MajorMapCourse`/`CourseStatus` state.
- **Replace** the "Major map" `<section>` with a **read-only "Your curriculum"** section that fetches `GET /api/curriculum` and renders `markdown` with `react-markdown` + `remark-gfm` (already used by the dashboard brief). It loads independently with its own loading/empty state so a slow first fetch doesn't block the rest of the page.
- `MajorMapEditor.tsx` stays in the repo (still imported by onboarding for the `majormap-enabled` branch) — just no longer used by the profile page on `main`.

## Data flow

```
chat: "what classes do I still need?"
  -> orchestrator calls read_curriculum()
     -> profile.acad_plan_code = "BAACCBS"
     -> get_checksheet_url -> https://.../checksheet/2026/CBA/BAACCBS/null
     -> fetch_curriculum (cache miss) -> httpx GET -> render_checksheet_markdown -> cache + return
  -> model reads the markdown and answers
(next curriculum question that session -> cache hit, no network)
```

## Testing

- `render_checksheet_markdown`: TDD against a captured fixture. Promote one probe HTML (e.g. `BAACCBS.html`) into `tests/fixtures/`; assert the output contains expected section headers and requirement lines, and excludes chrome ("Expand all"). Add a second fixture (an engineering program) for the OR-group / pool case.
- `fetch_curriculum` cache: monkeypatch the HTTP client; assert a second call does not re-fetch.
- `read_curriculum` tool: assert code→url resolution and graceful messages when major/url missing. No live network in tests.
- `GET /api/curriculum`: assert it returns markdown for a user with a linked program and a null-markdown empty state otherwise (mock `fetch_curriculum`).
- Gate: `pytest` (mocked) for backend; `tsc --noEmit` / lint / build for the profile-page change.

## Out of scope / deliberately avoided

- Programs DB table, migration, curriculum JSONB, structured AND/OR modeling, elective-pool modeling.
- Pre-extraction batch pipeline (we fetch on demand instead).
- Graduate programs (the masters-phd list); bachelor's only this round.
- Per-user course-status tracking and the old `major_map_courses` table / `/api/major-map/*` routes — left dormant, untouched. (`MajorMapEditor.tsx` stays for the `majormap-enabled` branch; the profile page just stops using it.)
- Disk-persistent cache (in-memory is enough for a single-instance demo; trivial to upgrade later).

## Risks / notes

- **Catalog year** is embedded in the stored URL (`2026`). Re-run `enrich_program_links.py` when ASU publishes a new year.
- **In-memory cache resets** on Render redeploy / cold start; first curriculum question after a restart re-fetches. Acceptable for demo; pre-warm or disk cache if it ever matters.
- **Discovery coverage**: probe got 5/5 bachelor's; the enrichment summary will reveal any program whose checksheet link isn't found, to fix or accept case-by-case.
- **Cleanup**: the `scratch/` probe is throwaway — delete it after promoting one or two fixtures into `tests/fixtures/`.

## Prerequisite already done

`296f7de` — Dockerfile copies `data/` so program search works on Render (the original onboarding bug). Independent of this feature.
