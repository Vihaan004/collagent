# Collagent v2 — "The Daily Brief" Design & Pitch Doc

**Status:** Approved design (brainstorm output). Doubles as the pitch artifact for ASU.
**Date:** 2026-06-19 · **Revised:** 2026-06-20 (single-orchestrator architecture + academic calendar)
**Scope:** The retention layer — turning v1's curated data into a daily-habit dashboard, managed by one agent, plus agent memory and a public launch. One vision/design doc; implementation is decomposed into sequential plans (see §10).

---

## 1. Thesis: from curated directory → agent-managed daily operating layer

v1 proved the wedge — **aggregation × personalization** — with two live curated surfaces: **Events** and **People**. It works, but it's *pull*: the student has to come look.

v2 is the **retention layer**, and it makes a second leap: **the platform is managed by a single agent.** It collapses everything into one personalized **dashboard** the student opens like a morning feed — a generated **Brief**, **ASU happenings** (open-web news), **academic deadlines** (the ASU calendar), their **top events**, and their **top people**. The same agent runs chat *and* maintains the dashboard, so a student can converse with the thing that builds their feed.

> Pitch line: *"Collagent went from a curated campus directory to an agent-managed daily operating layer — one agent maintains your dashboard and talks to you, it's live with real ASU students, and it runs on free infrastructure."*

## 2. Scope

**In (v2):**
- Dashboard consolidation (Home becomes the feed; nav = Home + Chat)
- **Academic calendar** ingestion (ASU registrar, current term only, deterministic — no curation)
- News ingestion via **Tavily** web search + light per-student curation
- **Single orchestrator agent** for chat + dashboard, using **deterministic pipeline tools** + DB tools
- **Agent memory system** (CRUD tools + system-prompt injection + visible panel)
- **Model provider config** (Groq free tier for prod, ASU endpoint for dev)
- **Publish** on free hosting (Vercel + Render/HF Spaces + Supabase + Tavily + Groq)

**Out (deferred to v2.1+):**
- Gmail read-only / email digest, calendar *sync* (Google integration — heavy OAuth + privacy)
- True nested LLM sub-agents (this iteration uses deterministic pipeline tools; nested agents are a later "flex")
- True per-user scheduling (manual refresh stays; scheduler is a drop-in upgrade later)
- Push/email nudges to drive the daily habit

## 3. Surfaces & navigation

Nav collapses to **Home + Chat**. `/events` and `/people` cease to be destinations; their content renders inline on Home. **Profile** remains reachable (account menu) and gains the memory panel.

**Dashboard (Home), top to bottom:**
1. **The Brief** — short agent-generated brief: lightweight, informative, suggestive. Synthesizes everything below, and may surface an imminent **deadline** from the calendar.
2. **Upcoming Deadlines** — academic-calendar items for the current term (registration windows, drop dates, deadlines, breaks), filtered to what's upcoming.
3. **ASU Happenings** — curated open-web news cards (general ASU news, lightly tuned to the student).
4. **Recommended Events** — **top 5**, full cards inline, each with its why-note and "discuss in chat" hand-off.
5. **People to Connect** — **top 5**, full cards inline, same treatment.

The **"Refresh my dashboard"** button is a *prompt to the orchestrator agent* (see §5), streamed over the existing chat SSE transport so the student watches progress ("refreshing events… fetching news… updating the calendar… writing your brief…"). The dashboard always renders the last stored state instantly.

## 4. Data model (additions only)

- **`calendar_items`** — current-term academic calendar. `term, session (A/B/C/whole-term), title, date_start, date_end, category, fetched_at`. Upsert on a natural key (`term, session, title`). Deterministic ingestion; **read-only to the agent.**
- **`news_items`** — global article cache. `source, source_key, title, url, summary, published_at, fetched_at, raw`. Upsert on `(source, source_key)`. News has **no** per-user recommendation table (it's general); its light per-student tuning lives in the snapshot below.
- **`dashboard_snapshots`** — one row per user. `user_id, brief_md, news (jsonb: the lightly-tuned subset of `news_items` chosen for this student + why-note), generated_at`. **Events, people, and calendar are read live** from their own tables (no duplication, no re-discovery); news is the one surface curated per-user into the snapshot.
- **`user_memories`** — `id, user_id, content, kind, created_at, updated_at`. CRUD by the agent, listed/deletable on Profile.

No changes to existing tables. The agent gets DB tools over a **whitelist**: `event_recommendations`, `person_recommendations`, `news_items` (read + CRUD), `calendar_items` (read-only), `user_memories` (read + CRUD) — all **scoped to the authenticated `user_id`**.

## 5. Single orchestrator agent (chat + dashboard)

One agent powers both surfaces. It replaces the earlier "separate approach-C research workflow" — same philosophy (deterministic where data is already curated, agentic web research only for news), now unified under one orchestrator with full DB context.

**Tools the orchestrator has:**
- `refresh_events` / `refresh_people` / `refresh_news` — **deterministic pipeline tools.** Each runs the existing curation/ingestion pipeline and writes results to the DB. (The "sub-agent workflows," built as cheap deterministic tools — not nested LLM agents.) `refresh_news` internally does the Tavily web research.
- `update_calendar` — deterministic tool: fetch the registrar page, extract the current term, upsert `calendar_items`.
- **DB read tools** — read current recommendations / news / calendar / memories for the user.
- **CRUD tools** — remove a recommendation the student dislikes, manage `news_items`, and `remember/update_memory/forget` (memory).

**Full-refresh flow (button or "refresh my dashboard" in chat):**
1. Orchestrator calls `refresh_events`, `refresh_people`, `refresh_news`, `update_calendar`. Each writes to DB; **none return findings to the orchestrator** — the DB is the source of truth, and the UI already reflects the updates.
2. Orchestrator reads the freshly-updated `event_recommendations`, `person_recommendations`, `news_items`, `calendar_items` (+ the student's `user_memories`).
3. Orchestrator writes the **all-inclusive Brief** and persists the `dashboard_snapshot`.

**Conversational control (same agent, in chat):** the student can ask to refresh *one* section, remove someone from recommendations ("I don't want to see X" → CRUD delete + `remember` the preference), or go deep on any item. Because one agent owns both the DB tools and the conversation, the UI is genuinely **agent-managed**.

**Guardrails:** every tool is scoped to the authenticated `user_id` (the agent never passes arbitrary IDs); `calendar_items` is read-only to the agent; full refresh runs **async** so it never blocks; tool calls are bounded to keep cost/latency sane on the free tier.

## 6. Agent memory system

- **CRUD tools:** `remember`, `update_memory`, `list_memories`, `forget`. The agent decides what's worth keeping (ChatGPT/Claude-style).
- **Injection:** on every new chat conversation, all of the user's memories load into the system prompt. The orchestrator also reads them during refresh to target news search and personalize the Brief.
- **Visible panel (transparency):** the **Profile page** gains a "What Collagent remembers" section listing each memory with a delete control. Reinforces the *student's-advocate* principle — the student owns and can prune their context.

## 7. Model provider config

`get_model()` is already env-driven over an OpenAI-compatible base URL, so this is configuration, not a rewrite. Named profiles via env:

- **dev** → ASU endpoint (`https://openai.rc.asu.edu/v1`, current default) — free for the developer, VPN/account-gated.
- **prod** → **Groq** (`https://api.groq.com/openai/v1`, e.g. `llama-3.3-70b-versatile`) — free tier, OpenAI-compatible, tool-calling + structured output, publicly reachable with no VPN/per-user key.

Switch by changing `OPENAI_BASE_URL` / `OPENAI_API_KEY` / `MODEL_NAME` only. "Model is swappable by config" is itself an engineering-maturity point for the pitch.

**Caveats filed for later:** free tiers have rate limits (the orchestrator's bounded tool calls keep us within them) and often train on submitted data (acceptable for public events/news/calendar; revisit if/when personal data like email enters in v2.1).

## 8. Publish / deploy (all free tiers)

- **Frontend → Vercel** (free, native Next.js).
- **Backend (FastAPI) → Render free** (Hugging Face Spaces Docker as backup). Caveat: free backends cold-start after idle (~30–50s first hit) and a full agent refresh takes ~30–90s — acceptable for a demo, surfaced live via the progress stream; an honest "scales later" footnote.
- **DB / Auth → Supabase** (already free tier). **News → Tavily** free tier. **Model → Groq** free tier.
- **Secrets** (Supabase service-role key, Tavily key, Groq key) live in host env vars — never committed.

## 9. Pitch arc

Problem (campus information is fragmented; students never find what they're entitled to) → **wedge** (aggregation × personalization — neither Google nor an official bot occupies it) → **v1 proof** (Events + People curated and live) → **v2 = retention + agent-managed platform** (one agent maintains a personalized Daily Brief — events, people, news, deadlines — and you can talk to it) → **live with real ASU users on free infrastructure** → **the ask** (*let me build this inside ASU, with real data access and SSO*).

## 10. Build sequence (implementation decomposition)

Each plan is independently shippable:

1. **Foundation** — `user_memories`, `news_items`, `calendar_items`, `dashboard_snapshots` migrations; model-provider config (Groq + ASU profiles). *Cheap, unblocks everything.*
2. **Memory system** — CRUD tools, system-prompt injection, Profile panel.
3. **Academic calendar** — registrar fetch + current-term/session extraction, `update_calendar` tool, dashboard Deadlines section. *(First build step: fetch the live page and confirm DOM + term/session structure.)*
4. **Orchestrator agent** — wrap existing pipelines as deterministic tools (`refresh_events/people/news`), add DB read/CRUD tools (user-scoped), the refresh prompt, and the Brief synthesis; route the refresh button through the chat SSE stream.
5. **Dashboard spine (frontend)** — Home feed consolidation (nav → Home + Chat, top-5 inline events/people, news, deadlines, Brief), reading from DB; live refresh progress.
6. **News research** — Tavily ingestion inside `refresh_news` + light curation.
7. **Publish** — Vercel + Render + env/secrets, smoke test with real users.

Recommended first plan: **Foundation + Memory** (1+2) — small, self-contained substrate that both chat and the orchestrator depend on.

## 11. Decisions log

- **MVP boundary:** lean demo-first — ship the agent-managed dashboard + memory on free infra; Gmail + scheduling are fast-follows.
- **Refresh model:** manual "Refresh my dashboard" button = a prompt to the orchestrator, streamed over chat SSE; no scheduler.
- **Architecture:** **single orchestrator agent** for chat + dashboard, with **deterministic pipeline tools** for section refreshes (not nested LLM sub-agents).
- **DB access:** agent gets user-scoped tools over a whitelist (`event_recommendations`, `person_recommendations`, `news_items` read+CRUD; `calendar_items` read-only; `user_memories` read+CRUD).
- **Academic calendar:** ASU registrar, current term only, deterministic extraction (Session A/B/C aware), no curation; the Brief reads it to highlight deadlines.
- **Prod model:** Groq free tier; ASU endpoint retained for dev; swappable by env.
- **News slant:** general ASU happenings, lightly tuned to the student.
- **Memory UX:** agent-managed CRUD **plus** a visible/deletable panel on Profile.
- **Dropped from v2:** Gmail/email digest, calendar sync, scheduler, nested sub-agents.

## 12. Risks & open questions

- **Calendar extraction** — the registrar page spans multiple future terms with Session A/B/C ranges; current-term detection + session parsing is the fiddly bit. Validate against the live DOM as step one of the calendar plan.
- **Free-tier limits & latency** — Groq rate limits, Render cold starts, and a multi-tool full refresh (~30–90s) are the user-visible rough edges; the progress stream makes the wait legible. Bounded tool calls keep cost in check.
- **Agent DB writes** — powerful but a security surface; mitigated by user-scoped, whitelisted tools and read-only calendar.
- **News quality/recency** — open-web search can surface stale/off-topic items; ASU-scoped queries + the curation pass mitigate.
- **Memory accuracy** — agent-written memories can drift; the visible/deletable panel is the safety valve.
- **Data-training on free tiers** — acceptable for public data now; a hard gate before any personal-data feature.
