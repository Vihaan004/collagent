# Collagent v2 — Publish Runbook (#7)

> **For the operator (Vihaan):** This is a deploy runbook, not a code-TDD plan. It documents the repo files to add, the accounts/keys to obtain, the exact env vars, and the smoke test. Code prep (Dockerfile, `frontend/.env.example`, README) is called out as a follow-up slice ("Prep the repo for deploy") — this plan does not touch accounts and assumes that prep is done when noted.

**Goal:** Put the built v2 app on free infrastructure with real ASU users: frontend on Vercel, backend on a Docker host, Supabase/Tavily/Groq as managed services.

**Topology:**
```
Browser ──> Vercel (Next.js frontend)
                │  NEXT_PUBLIC_API_URL
                ▼
        Backend (FastAPI, Docker)  ──> Supabase (DB + Auth/JWT)
          OpenAI-compatible LLM ──> Groq          ──> Tavily (news)
          Playwright/Chromium (onboarding major-map extraction)
```

---

## 0. Major-map extraction is DISABLED for this deploy

`src/collagent/asu/majormap.py` launches **headless Chromium** (`sync_playwright().chromium.launch()`) during onboarding to extract a student's major map. Chromium needs ~500MB–1GB RAM to launch, which is too heavy for Render's 512MB free tier. Everything else (events/people/news/calendar) is plain `httpx` and lightweight.

**For this demo we disable major-map extraction via a feature flag**, so Chromium never launches and the backend stays RAM-light. This makes **Render free the clean primary host**.

- Backend: `MAJOR_MAP_ENABLED=false` → `/api/major-map/generate` returns **503**; `build_major_map` (and Playwright) is never called.
- Frontend: `NEXT_PUBLIC_MAJOR_MAP_ENABLED=false` → onboarding finishes right after "About you" (no "Build map" / course-editor steps).
- The Playwright dependency and all extraction code stay in place — **re-enable later by flipping both env vars to `true`** on a host with enough RAM (e.g. Hugging Face Spaces Docker, up to 16GB free) and ensuring the browser is installed (`playwright install chromium`).

**Recommendation:** backend on **Render free (Docker or native Python)**; because extraction is off, the host needs neither Chromium nor the Playwright base image. Revisit HF Spaces + the Playwright image when major-map extraction is turned back on (a future improvement, see §11).

---

## 1. Accounts & keys to obtain (free tiers)

| Service | What you need | Notes |
|---|---|---|
| **GitHub** | a repo to push `main` to | required by both Vercel and HF/Render for git deploys |
| **Groq** | `GROQ` API key | console.groq.com → API Keys. Prod LLM. |
| **Tavily** | `TAVILY` API key | app.tavily.com. News ingestion. |
| **Supabase** | already provisioned (project `collagent`, ref `qepwzwitwjhklxscrugr`) | grab the **service-role key**, **JWT secret**, **anon key**, project URL |
| **Hugging Face** (or Render) | account | backend host |
| **Vercel** | account (log in with GitHub) | frontend host |

Pick the current Groq tool-calling model when you create the key — `llama-3.3-70b-versatile` is the design-doc default; verify it's still listed and supports tools + structured output (the orchestrator needs both).

---

## 2. Push `main` to GitHub (prerequisite)

`main` is local-only. From the repo root:

```bash
# create the repo on GitHub first (gh or web), then:
git remote add origin https://github.com/<you>/collagent.git
git push -u origin main
```

Confirm `.gitignore` excludes `.env`, `.env.local`, `.next/`, `__pycache__/`, `.venv/`, and that **`canvas-mcp/` stays untracked** (it currently is). Double-check no secret ever entered git history before the repo goes public — if unsure, make the repo **private** for the demo.

---

## 3. Repo prep required before deploy (the "Prep" slice)

These files don't exist yet; add them in the prep slice (not in this runbook's scope, but specified here so the deploy is unblocked):

**`Dockerfile`** (repo root) — slim Python image + uv. Because major-map extraction is disabled (§0), **no Chromium / Playwright base image is needed**; the `playwright` pip package installs fine without browsers.
```dockerfile
FROM python:3.12-slim

WORKDIR /app
# uv for fast, lockfile-faithful installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --frozen || uv sync --no-dev
COPY src ./src
COPY README.md ./

ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uv run uvicorn collagent.api.main:app --host 0.0.0.0 --port ${PORT}"]
```
> `${PORT}` indirection covers hosts that inject their own port. When you re-enable major-map extraction (§11), switch the base to `mcr.microsoft.com/playwright/python:v1.50.0-noble` and add `RUN uv run playwright install chromium`.

**`frontend/.env.example`** — the public vars the frontend reads:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://YOUR-REF.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
# Set to false to skip the major-map onboarding steps (pair with backend MAJOR_MAP_ENABLED=false)
NEXT_PUBLIC_MAJOR_MAP_ENABLED=true
```

**`README.md`** — add a "Deploy" section pointing at this runbook.

Verify the build locally before pushing: `docker build -t collagent-api . && docker run -p 8000:8000 --env-file .env collagent-api`, then hit `http://localhost:8000/api/health`.

---

## 4. Backend → Render (free Web Service)

1. New → **Web Service** → connect the GitHub repo → **Docker** runtime (builds from the root `Dockerfile`). Health Check Path: `/api/health`. Free instance type.
2. **Environment** (Render dashboard → Environment) — these map to `Settings` (`config.py`) and the model env (`graph.py`):

   | Env var | Value | Source |
   |---|---|---|
   | `SUPABASE_URL` | `https://qepwzwitwjhklxscrugr.supabase.co` | Supabase |
   | `SUPABASE_SERVICE_ROLE_KEY` | service-role key | Supabase → API (⚠️ secret) |
   | `SUPABASE_JWT_SECRET` | JWT secret | Supabase → API → JWT |
   | `OPENAI_API_KEY` | Groq API key | Groq |
   | `OPENAI_BASE_URL` | `https://api.groq.com/openai/v1` | — |
   | `MODEL_NAME` | `llama-3.3-70b-versatile` | Groq (verify current) |
   | `TAVILY_API_KEY` | Tavily key | Tavily |
   | `FRONTEND_ORIGIN` | *(set in §6 after Vercel URL exists)* | Vercel |
   | `MAJOR_MAP_ENABLED` | `false` | disables Playwright/Chromium for the demo (§0) |
   | `TEMPERATURE` | `0.2` | optional |

   Do **not** set `CANVAS_*` (Canvas is unused by the web app). Leave `OPENAI_BASE_URL`/`MODEL_NAME` at Groq values — the ASU defaults in `graph.py` are dev-only. `MAJOR_MAP_ENABLED=false` is what keeps this within Render's 512MB (§0).
3. Wait for the build; confirm the service URL responds at `/api/health` → `{"status":"ok"}`.

---

## 5. Frontend → Vercel

1. New Project → import the GitHub repo → **Root Directory: `frontend`**. Framework auto-detects Next.js 16.
2. **Environment Variables:**

   | Env var | Value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | the backend URL from §4 (e.g. `https://collagent-api.onrender.com`) |
   | `NEXT_PUBLIC_SUPABASE_URL` | `https://qepwzwitwjhklxscrugr.supabase.co` |
   | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon (publishable) key |
   | `NEXT_PUBLIC_MAJOR_MAP_ENABLED` | `false` — skips the major-map onboarding steps (§0) |

   These are `NEXT_PUBLIC_*` → compiled into the client bundle at build time; a value change requires a redeploy. The anon key is safe to expose (RLS-gated); the **service-role key must never** appear in the frontend.
3. Deploy. Note the production URL (e.g. `https://collagent.vercel.app`).

---

## 6. Close the loop: CORS + the URL handshake

There's a chicken-and-egg: each side needs the other's URL.

1. After Vercel gives you the prod URL, set the backend's **`FRONTEND_ORIGIN`** to it (exact scheme+host, no trailing slash) and restart the backend. `main.py` allows exactly this one origin.
2. Confirm `NEXT_PUBLIC_API_URL` on Vercel points at the live backend; redeploy the frontend if you changed it.
3. **Supabase Auth redirect:** add the Vercel domain to Supabase → Authentication → URL Configuration (Site URL + redirect allow-list), so the OAuth callback (`app/auth/callback`) returns to prod, not localhost.

**Preview deploys caveat:** Vercel preview URLs are per-commit and won't match the single `FRONTEND_ORIGIN` → their API calls will be CORS-blocked. Fine for the demo (use the prod URL). If you need previews, a follow-up makes `FRONTEND_ORIGIN` a comma-list or regex in `main.py`.

**Playwright:** N/A for this deploy — major-map extraction is disabled (§0), so nothing launches Chromium. See §11 to re-enable.

---

## 7. Secrets checklist (never commit any of these)

- [ ] `SUPABASE_SERVICE_ROLE_KEY` — backend host env only (bypasses RLS; the keystone secret)
- [ ] `SUPABASE_JWT_SECRET` — backend host env only
- [ ] `OPENAI_API_KEY` (Groq) — backend host env only
- [ ] `TAVILY_API_KEY` — backend host env only
- [ ] `NEXT_PUBLIC_SUPABASE_ANON_KEY` — Vercel (public by design, RLS-gated)
- [ ] No secret in git history; `.env`/`.env.local` gitignored; repo private if any doubt

---

## 8. Production smoke test

With both deploys live, in a clean browser:

1. **Health:** `GET <backend>/api/health` → `{"status":"ok"}`.
2. **Auth:** sign up/in on the Vercel site; confirm redirect returns to the prod domain (not localhost).
3. **Onboarding:** complete the "About you" step; confirm it finishes straight to Home with no major-map step (extraction disabled, §0). The backend should never log a `chromium.launch()`.
4. **Dashboard:** Home loads, `GET /api/dashboard` returns; click **Refresh my dashboard** → progress streams (events → people → news → calendar → brief), feed re-renders. First hit may be slow if the backend cold-started.
5. **Chat:** ask something; confirm SSE tokens stream and memory persists across a reload.
6. **Network/CORS:** no CORS errors in the console; API calls hit the Render origin with `Authorization: Bearer`.

---

## 9. Known free-tier rough edges (say these out loud in the pitch)

- **Cold starts:** free backends sleep when idle (~30–50s first hit). A full agent refresh is ~30–90s; the progress stream makes the wait legible. Honest "scales later" footnote.
- **Groq rate limits:** the orchestrator's bounded tool calls keep within free limits; a burst of refreshes could 429.
- **Data training on free tiers:** acceptable for public events/news/calendar; a hard gate before any personal-data feature (per design §7 caveat).
- **Single CORS origin:** prod only; preview deploys excluded (see §6).
- **No major map in the demo:** onboarding skips it (§0); a known, intentional limitation to mention, with the re-enable path ready (§11).

---

## 10. Execution order (checklist)

- [ ] Run the **Prep** slice (Dockerfile, `frontend/.env.example`, README, local `docker build` smoke)
- [ ] §2 Push `main` to GitHub
- [ ] §1 Obtain Groq + Tavily keys; gather Supabase keys
- [ ] §4 Deploy backend (Render Docker), set env incl. `MAJOR_MAP_ENABLED=false`, verify `/api/health`
- [ ] §5 Deploy frontend (Vercel), set `NEXT_PUBLIC_*` incl. `NEXT_PUBLIC_MAJOR_MAP_ENABLED=false`
- [ ] §6 Set `FRONTEND_ORIGIN`, Supabase redirect URLs; redeploy as needed
- [ ] §8 Production smoke test
- [ ] Re-run backend suite when the ASU endpoint is healthy (the major-map live test); deploy uses Groq regardless

---

## 11. Future: re-enable major-map extraction

The feature is flag-gated, not removed — the Playwright dependency and all of `asu/majormap.py` + the onboarding steps stay in the codebase. To turn it back on:

1. Host the backend where Chromium fits in RAM (Hugging Face Spaces Docker, up to 16GB free, is the natural target).
2. Switch the `Dockerfile` base to `mcr.microsoft.com/playwright/python:v1.50.0-noble` and add `RUN uv run playwright install chromium`.
3. Set `MAJOR_MAP_ENABLED=true` (backend) and `NEXT_PUBLIC_MAJOR_MAP_ENABLED=true` (frontend); redeploy both.

Improvement ideas for that pass: cache/pre-seed extracted maps in Supabase so each onboarding doesn't relaunch a browser; or replace Playwright with a lighter fetch if the roadmap page exposes a JSON/API endpoint.
