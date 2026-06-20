# Collagent v2 — "The Daily Brief" Design & Pitch Doc

**Status:** Approved design (brainstorm output). Doubles as the pitch artifact for ASU.
**Date:** 2026-06-19
**Scope:** The retention layer — turning v1's curated data into a daily-habit dashboard, plus agent memory and a public launch. One vision/design doc; implementation is decomposed into sequential plans (see §10).

---

## 1. Thesis: from curated directory → daily operating layer

v1 proved the wedge — **aggregation × personalization** — with two live curated surfaces: **Events** and **People**. It works, but it's *pull*: the student has to come look.

v2 is the **retention layer**. It collapses everything into one personalized **dashboard** the student opens like a morning feed: a generated **Brief**, **ASU happenings** (open-web news), their **top events**, and their **top people** — all on the home page. Plus a **persistent memory** that makes chat feel like it knows them, and a **public launch** so this runs for real ASU users.

> Pitch line: *"Collagent went from a curated campus directory to a daily operating layer students open every morning — and it's live, with real users, on free infrastructure."*

## 2. Scope

**In (v2):**
- Dashboard consolidation (Home becomes the feed; nav = Home + Chat)
- News ingestion via **Tavily** web search + light per-student curation
- **Deep-research dashboard agent** (approach C — pipeline spine + agentic web research)
- **Agent memory system** (CRUD tools + system-prompt injection + visible panel)
- **Model provider config** (Groq free tier for prod, ASU endpoint for dev)
- **Publish** on free hosting (Vercel + Render/HF Spaces + Supabase + Tavily + Groq)

**Out (deferred to v2.1+):**
- Gmail read-only / email digest, calendar (Google integration — heavy OAuth + privacy; not needed now)
- True per-user scheduling (manual refresh stays; scheduler is a drop-in upgrade later)
- Push/email nudges to drive the daily habit

## 3. Surfaces & navigation (§ Surface design)

Nav collapses to **Home + Chat**. `/events` and `/people` cease to be destinations; their content renders inline on Home. **Profile** remains reachable (account menu) and gains the memory panel.

**Dashboard (Home), top to bottom:**
1. **The Brief** — short AI-generated brief: lightweight, informative, suggestive. Synthesizes everything below.
2. **ASU Happenings** — curated open-web news cards (general ASU news, lightly tuned to the student).
3. **Recommended Events** — **top 5**, full cards inline (not a preview link), each with its why-note and "discuss in chat" hand-off.
4. **People to Connect** — **top 5**, full cards inline, same treatment.

One **"Refresh my dashboard"** button regenerates the whole snapshot (reuses the existing events/people async-refresh pattern). The dashboard always renders the last stored snapshot instantly.

## 4. Data model (additions only)

- **`news_items`** — global article cache. `source, source_key, title, url, summary, published_at, fetched_at, raw`. Upsert on `(source, source_key)`, identical pattern to `events` / `people`.
- **`dashboard_snapshots`** — one row per user. `user_id, brief_md, news (jsonb: curated items + why-note + url), generated_at`. **Events and people are read live from the existing `event_recommendations` / `person_recommendations` tables — never copied** — so the research agent never re-discovers already-curated data.
- **`user_memories`** — `id, user_id, content, kind, created_at, updated_at`. The memory store; CRUD by the chat agent, read by the research agent, listed/deletable on Profile.

No changes to existing tables.

## 5. Deep-research workflow (approach C)

Runs on **"Refresh my dashboard."** A deterministic pipeline spine with a single genuinely-agentic step. The guiding rule (the user's): **prioritize web search coupled with pre-ingested data; never re-discover events/people.**

1. **Ensure curated data** — confirm top-5 event recs + top-5 person recs exist; reuse existing curation pipelines if missing. (Read, don't re-discover.)
2. **Agentic news research** — *the agentic part.* The agent uses **Tavily web search**, seeded by the student's interests + **memories**, to find current ASU happenings (general, lightly tuned). Results upsert into `news_items`; a structured-output pass selects + ranks the most relevant with why-notes.
3. **Synthesis** — one LLM call reads `{student summary + memories, top-5 events, top-5 people, curated news}` and writes **The Brief**.
4. **Persist** the `dashboard_snapshot`. The dashboard reads it instantly on next load.

Deterministic where curated data already exists; real open-web research only where it adds value (news); bounded calls keep it cheap and reliable on a free model tier. This is a faithful "deep research agent" — it genuinely researches the open web — without unbounded agent loops.

## 6. Agent memory system

- **CRUD tools on the chat agent:** `remember`, `update_memory`, `list_memories`, `forget`. The agent decides what's worth keeping (ChatGPT/Claude-style).
- **Injection:** on every new chat conversation, all of the user's memories load into the system prompt.
- **Shared store:** the research agent reads the same memories to target news search and personalize the Brief. One store, two consumers.
- **Visible panel (transparency):** the **Profile page** gains a "What Collagent remembers" section listing each memory with a delete control. Reinforces the *student's-advocate* principle — the student owns and can prune their context.

## 7. Model provider config

`get_model()` is already env-driven over an OpenAI-compatible base URL, so this is configuration, not a rewrite. Named profiles via env:

- **dev** → ASU endpoint (`https://openai.rc.asu.edu/v1`, current default) — free for the developer, VPN/account-gated.
- **prod** → **Groq** (`https://api.groq.com/openai/v1`, e.g. `llama-3.3-70b-versatile`) — free tier, OpenAI-compatible, tool-calling + structured output, publicly reachable with no VPN/per-user key.

Switch by changing `OPENAI_BASE_URL` / `OPENAI_API_KEY` / `MODEL_NAME` only. (A separate cheaper model for curation passes is possible later; start with one model.) "Model is swappable by config" is itself an engineering-maturity point for the pitch.

**Caveats filed for later:** free tiers have rate limits (fine for a demo) and often train on submitted data (acceptable for public events/news; revisit if/when personal email enters in v2.1).

## 8. Publish / deploy (all free tiers)

- **Frontend → Vercel** (free, native Next.js).
- **Backend (FastAPI) → Render free** (Hugging Face Spaces Docker as backup). Caveat: free backends cold-start after idle (~30–50s first hit) and a refresh pass takes ~30–60s — acceptable for a demo; an honest "scales later" footnote.
- **DB / Auth → Supabase** (already free tier). **News → Tavily** free tier. **Model → Groq** free tier.
- **Secrets** (Supabase service-role key, Tavily key, Groq key) live in host env vars — never committed.

## 9. Pitch arc

Problem (campus information is fragmented; students never find what they're entitled to) → **wedge** (aggregation × personalization — neither Google nor an official bot occupies it) → **v1 proof** (Events + People curated and live) → **v2 = retention** (one personalized Daily Brief students open each morning) → **live with real ASU users on free infrastructure** (proof it works, not a mockup) → **the ask** (*let me build this inside ASU, with real data access and SSO*).

## 10. Build sequence (implementation decomposition)

This design spans multiple subsystems; implementation is split into sequential plans, each independently shippable:

1. **Foundation** — `user_memories` + `news_items` + `dashboard_snapshots` migrations; model-provider config (Groq + ASU profiles). *Cheap, unblocks everything.*
2. **Memory system** — CRUD tools, system-prompt injection, Profile panel.
3. **Dashboard spine** — frontend consolidation (Home feed, nav → Home + Chat, top-5 inline events/people), reading existing recs.
4. **News + research agent** — Tavily ingestion, news curation, the approach-C workflow, the Brief, snapshot persistence, refresh wiring.
5. **Publish** — Vercel + Render + env/secrets, smoke test with real users.

Recommended first plan: **Foundation + Memory** (1+2) — small, self-contained, and it's the substrate both chat and the research agent depend on.

## 11. Decisions log

- **MVP boundary:** lean demo-first — ship the dashboard + memory on free infra; Gmail + scheduling are fast-follows. *(Fastest to a live, shareable demo.)*
- **Refresh model:** manual "Refresh my dashboard" button (reuses existing async refresh); no scheduler.
- **Prod model:** Groq free tier; ASU endpoint retained for dev; swappable by env.
- **Research agent:** approach C — deterministic spine + agentic web research for news only.
- **News slant:** general ASU happenings, lightly tuned to the student.
- **Memory UX:** agent-managed CRUD **plus** a visible/deletable panel on Profile.
- **Dropped from v2:** Gmail/email digest, calendar, scheduler.

## 12. Risks & open questions

- **Free-tier limits** — Groq rate limits and Render cold starts are fine for a demo but are the first things to outgrow; the manual-refresh latency is user-visible.
- **News quality/recency** — open-web search can surface stale or off-topic items; the curation pass and ASU-scoped queries mitigate, but news is the least deterministic surface.
- **Data-training on free tiers** — acceptable for public data now; a hard gate before any personal-email feature.
- **Memory accuracy** — agent-written memories can drift or capture noise; the visible/deletable panel is the safety valve.
- **Scraping/ToS posture** — unchanged from v1; Tavily abstracts direct scraping for news, which is a plus.
