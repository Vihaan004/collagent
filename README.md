# Collagent

A proactive, personalized interface between a student and their university. ASU-first.
Vision and specs: `docs/superpowers/specs/`.

**Current state (PoC milestone 1):** web app with Supabase auth, profile +
agent-built ASU major map onboarding, and a profile-aware chat agent with
Canvas tools. CLI still available via `collagent run`.

## Stack

Next.js 16 (`frontend/`) · FastAPI + LangGraph (`src/collagent/`) · Supabase (auth + Postgres) · Playwright (ASU data)

## Dev setup

Backend (repo root):

```sh
uv venv
uv sync --group dev
uv run playwright install chromium
cp .env.example .env   # fill in Supabase + LLM + Canvas keys
uv run uvicorn collagent.api.main:app --reload --port 8000
```

Supabase (one-time): create a project at supabase.com, run
`supabase/migrations/0001_init.sql` in the SQL Editor, and copy the project URL,
service-role key, and legacy JWT secret into `.env`.

Frontend:

```sh
cd frontend
npm install
cp .env.example .env.local   # fill in Supabase URL + anon key
npm run dev
```

> **Major-map onboarding is disabled by default** (`MAJOR_MAP_ENABLED` / `NEXT_PUBLIC_MAJOR_MAP_ENABLED`)
> so the demo runs on RAM-light hosts without Playwright/Chromium. Set both to `true` in your
> env to develop with it on. The `feat/majormap-enabled` branch keeps the enabled-by-default version.

One-time data seed (already committed, rerun to refresh):

```sh
uv run python scripts/seed_programs.py
```

Note: major maps are generated from ASU's public 2024–25 catalog (`catalog_year=2024`);
the 2025 maps are behind ASU CAS login.

Tests: `uv run pytest` (backend) · `npm run build` (frontend typecheck)

## End-to-end smoke checklist (run before shipping a milestone)

Fresh browser profile, both servers up:

1. Visit `/` logged out → redirected to `/login`.
2. Magic-link sign-in with a fresh email → lands on `/` → redirected to `/onboarding` (profile row auto-created by trigger).
3. Onboarding step 1: search "computer", select program, fill fields, continue.
4. Step 2: build major map (~1 min) → step 3 shows terms with courses.
5. Toggle 2-3 courses to taken → Finish → dashboard greets by first name.
6. `/chat`: "what classes do I have left?" → answer reflects the major map.
7. `/chat`: "I joined the robotics club" → `/profile` shows robotics club after reload (typed tool wrote it).
8. `uv run pytest` → all pass. `cd frontend && npm run build` → clean.

Record any failures as issues; do not ship the milestone with a failing item.

## Deploy

Frontend → Vercel, backend → Render (Docker, free tier), DB/Auth → Supabase,
news → Tavily, model → Groq. The backend `Dockerfile` and `render.yaml` are in the repo;
push `main` and connect both hosts for CI/CD. Full step-by-step runbook (env vars, CORS,
secrets, smoke test): [`docs/superpowers/plans/2026-06-21-collagent-v2-publish.md`](docs/superpowers/plans/2026-06-21-collagent-v2-publish.md).
