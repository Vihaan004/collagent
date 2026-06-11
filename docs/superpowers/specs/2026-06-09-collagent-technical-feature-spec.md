# Collagent — Technical & Feature Spec

**Status:** Living working document. Churns as features are added, refined, and removed. Filled in feature by feature through brainstorming, then implemented.

**Date started:** 2026-06-09
**Companion to:** `2026-06-09-collagent-vision-design.md` (north star — read for *why*; this doc covers *how*). This spec references the vision's principles rather than restating them.

> **How to read this doc:** Sections marked **[established]** are settled. Sections marked **[in progress]** are scaffolds we are actively filling in. Nothing here is frozen until implemented.

> **Development philosophy (decided 2026-06): PoC speed over robustness.** The near-term goal is a working, publishable web app with a UI — fast — to showcase to ASU stakeholders and gather real student users. Prefer simple workarounds over deep technical solutions; defer edge-case engineering. The data-ingestion layer (scrapers) is **deliberately the disposable layer**: if ASU ever grants official data access, only Tier 1–3 ingestion gets replaced — the personal data store, matching workflows, curated surfaces, UI, and agents are data-source-agnostic and survive.

---

## 1. System Architecture **[established]**

Collagent has **two pipelines over one shared data layer**.

```
                 ┌─────────────────────────────────────────┐
                 │              DATA LAYER                   │
                 │                                           │
                 │  Personal Data Store   University         │
                 │  (per student)         Knowledge Layer    │
                 │  - onboarding          (per institution)  │
                 │  - major map           - fetched pages    │
                 │  - Canvas              - indexed content  │
                 │  - email/calendar      - structured data  │
                 └───────────▲───────────────────▲───────────┘
                             │                    │
            reads/writes     │                    │  reads
                 ┌───────────┴──────┐   ┌─────────┴──────────┐
                 │ CURATION PIPELINE │   │ INTERACTIVE PIPELINE│
                 │ (push, batch)     │   │ (pull, real-time)   │
                 │                   │   │                     │
                 │ scheduled LangGraph│  │ chat agent (ReAct)  │
                 │ workflows build    │  │ tools read store +  │
                 │ curated surfaces   │  │ do live lookups     │
                 │ → write to store   │  │                     │
                 └─────────▲─────────┘   └──────────▲──────────┘
                           │                        │
                    Served-up-front           Conversational
                    surfaces (pages)          chat surface
```

- **Interactive pipeline (pull):** the chat agent (current LangGraph ReAct agent) accesses data through tools in real time, responding to the student. Latency-sensitive. This is what exists today.
- **Curation pipeline (push):** scheduled background workflows (LangGraph, but not chat agents) pre-build the served-up-front surfaces and write structured results into the store. Batch. This is the "push not pull / minimal friction" principle made real.
- **Shared data layer:** both pipelines sit on the same personal data store and university knowledge layer. Build data access and storage **once**; both reuse it.

**Key consequence — curation feeds chat.** Curation workflows write structured results (e.g. networking leads) into the store. The chat agent reads that same store as one of its tools. So a lead surfaced on the Networking page is also available in chat ("tell me more about Prof. Arora"), and a recommendation can "transfer into a new chat" seamlessly. We never build the same capability twice.

## 2. Data Layer

### 2.1 Personal Data Store **[in progress — onboarding model established, schema TBD]**

Per-student. Sources, in build-priority order:

- **Onboarding (hybrid, one-time, editable):** see onboarding model below. Covers major, year, interests, goals, current clubs, projects, on-campus jobs. Carries the PoC.
- **Major Map (agent-built, student-confirmed, editable):** full program requirements with each course tagged *taken / in-progress / remaining*. First-class primitive (richer than Canvas; also powers degree-progress features).
- **Canvas (credentialed sync):** enrolled courses, grade/assignment details. Thin on personal signal but already wired.
- **College email + calendar (recurring sync):** strong signal — the university *already* personalizes email by program/school, so it's pre-filtered relevance. Heavier integration (OAuth/permissions/privacy); spec now, phase after PoC. Calendar gives schedule context for time-aware suggestions.

**Onboarding model (decided): hybrid — never make the student type what collagent can fetch; never infer what only the student knows.**

- **Manual (subjective):** interests, goals — cheap to enter, only the student knows them.
- **Agent-assisted (factual):** student provides the minimum (e.g. "Computer Systems Engineering, junior") and collagent uses the knowledge layer to pre-build the expensive parts — major map auto-populated from ASU's published degree requirements, club/interest suggestions to accept or reject. Student **confirms and edits rather than authors**.

**Profile management model (decided): conversational to manage, structured to store.**

- The student can update their profile anytime by conversing with the agent ("I joined the robotics club") or via file attachments (resume, transcript), like a regular chat.
- The agent applies these updates **only through tools with structured, typed fields** — never by saving raw text blobs. Critical data (major map, degree requirements, courses, enrollments) lives in a real database schema; the agent is the editor, never the format.
- Free-form nuance (e.g. a goals statement) may have designated text fields, but the schema decides where text is allowed — not the agent.

*Open for this session: concrete schema, storage choice, sync cadence.*

### 2.2 University Knowledge Layer **[established — source map from June 2026 deep research]**

Per-institution (ASU first). Data access spectrum (cheapest sufficient tool per source):

1. **HTTP fetch + HTML→text extraction / structured feeds (ICS, JSON)** — primary tool.
2. **Headless browser (Playwright), surgical** — only for JS-rendered sources with no cheap path.
3. **Authenticated ingestion (user-consented)** — for SSO-walled sources, the agent fetches *on the logged-in student's behalf* with explicit consent (same trust model as the Canvas token). Never scrape behind SSO without authorization.
4. **Pre-indexed RAG** — periodic crawl → chunk → embed → millisecond retrieval. The moat; needed for snappy surfaces. Deferred past PoC but tool interface kept stable so backend can swap without changing agents.

#### ASU source-to-tier map (deep research, 2026-06)

**Tier 1 — public, cheap, structured (build on these first):**

| Source | URL | What | Access notes |
|---|---|---|---|
| ASU Events | asuevents.asu.edu | University-wide event calendar | Server-rendered Drupal; paginate `?page=N`; **per-event ICS** + GCal links. Backbone for events. |
| Class search (legacy) | webapp4.asu.edu/catalog/myclasslistresults | Class sections, seats, instructors | Plain HTML, no auth, browser User-Agent required. Params: `t` (term), `k`, `s`, `e`, `page`. Term code: `2`+YY+digit (1=Spring, 4=Summer, 7=Fall). **Legacy — monitor for decommission.** |
| iSearch Solr | asudir-solr.asu.edu/asudir/directory/select? | Faculty/staff/student directory — the people graph | **De facto public API** (`wt=json`, `fl`, `q`); CORS-blocked in browser, fine server-side. Feeds Networking. |
| Major maps | webapp4.asu.edu/programs/t5/roadmaps/ASU00/{code}/null/ALL/{year}; degrees.apps.asu.edu/majormaps | 800+ program roadmaps by catalog year | Deterministic deep-link URLs. Feeds agent-assisted major-map onboarding (§2.1). |
| FURI + research pages | students.engineering.asu.edu/furi etc. | Undergrad research opportunities, mentor-ready faculty lists | Server-rendered, public. Feeds Opportunities. |
| Sun Devil Athletics | sundevils.com | Sports schedules/events | Sidearm platform; schedule ICS/CSV exports. |
| Per-college club pages | e.g. math.asu.edu, sese.asu.edu | Curated club lists + links to each club's Discord/Instagram/Sun Devil Central | Server-rendered, public. **Best available public club signal**; also seeds the social-channel registry. |
| EOSS sub-calendars, students.asu.edu, catalog.asu.edu, academic calendar | various | Services, policies, term dates | Static server-rendered pages; RAG-index candidates. |

**Tier 2 — JS-rendered, public (surgical Playwright):**

| Source | Notes |
|---|---|
| catalog.apps.asu.edu (modern class search) | SPA; only needed if webapp4 legacy endpoint dies. |
| degrees.apps.asu.edu | SPA-like; prefer webapp4 roadmap URLs. |
| Workday public careers (asuep.wd5.myworkdayjobs.com) | Workday CXS JSON endpoints typically exist — probe before resorting to browser. |

**Tier 3 — SSO-walled (authenticated, user-consented ingestion only; post-PoC):**

| Source | What we lose without it |
|---|---|
| **Sun Devil Central** (sundevilcentral.eoss.asu.edu) | The authoritative club/org directory. CampusGroups SPA, fully ASURITE-gated, no public API. Org data also *incomplete through 2025-26* (migration ongoing). |
| **Handshake** (asu.joinhandshake.com) | The authoritative jobs/internships board. |
| Workday student jobs, My ASU | On-campus jobs; personalized portal. |

**Tier 4 — unofficial long tail (curated registry + official APIs):**

- **r/ASU** — most machine-readable unofficial source (Reddit JSON/OAuth API).
- **Discord / Instagram / GroupMe** — where real-time club life actually happens; not centrally discoverable. Strategy: build a **curated social-channel registry** seeded from per-college club pages (which publish invite links/handles), ingest via official APIs where permitted. Post-PoC.

**Watch items:** webapp4 decommission risk; Sun Devil Central possibly exposing a public directory/API as migration completes; modern class-search JSON XHR becoming publicly callable. Any of these would re-tier sources.

**Scraping posture (resolved):** asu.edu robots.txt is standard Drupal — public content broadly crawlable. webapp4 needs only a browser UA. SSO walls are respected absolutely; the path through them is user consent (Tier 3), never circumvention.

## 3. Interactive Pipeline (Chat Agent) **[established — design decided]**

Today: LangGraph ReAct agent + Canvas tools, CLI. Target: web chat surface, reads the shared store plus does live knowledge-layer lookups, receives "transferred" recommendations from curated surfaces.

**Agent design principle (decided): no custom graphs — the value is in context engineering.** The chat agent stays a prebuilt LangGraph ReAct loop. All design effort goes into:

- **Per-session system prompt assembled from the profile:** compact rendering of major, year, interests, goals, clubs, major-map progress injected at chat start. This is what makes generic chat feel like the student's advisor.
- **Typed tool belt (the real design surface):**
  - *Profile tools:* `update_profile`, `update_major_map` — structured fields only (§2.1).
  - *Index tools:* `search_people`, `search_events`, `search_opportunities`, `get_recommendation_details` — read the same store the pages render from (curation feeds chat, §1).
  - *Live tools:* existing Canvas tools, live iSearch lookup, `fetch_page`, class search (freshness policy §4).
  - *Action helpers (later):* e.g. draft-an-email-to-professor.
- **Structured outputs on every store-writing tool** (Pydantic schemas) — "agent is the editor, never the format," enforced by types.

Deep-agent patterns, subagents, and custom state machines are explicitly **not needed** for the PoC.

## 4. Curation Pipeline (Background Workflows) **[established — structure decided]**

Scheduled LangGraph workflows. Not chat agents — they run on a schedule, research, and write structured output to the store.

**Two-stage structure (decided): shared indexing + per-student curation.**

1. **Shared indexing jobs (per-institution):** periodically ingest public sources into the knowledge layer as structured records — people (from iSearch Solr, FURI mentor lists, faculty pages), events (from ASU Events ICS, athletics), research opportunities. Computed once, reused by every student.
2. **Per-student curation workflows:** match the student's profile against the shared index (keyword/embedding retrieval to build a candidate pool), then LLM-rank and generate the **personalized why-note** per item. Cheap per student. The experience target: an **executive assistant + college advisor preparing a regular mini-report** per surface — not a feed. Quality over quantity (e.g. 5–10 strong networking leads), refreshed on profile change or new index data, not on fixed daily churn for slow-moving domains.

**Implementation shape (decided): pipelines, not agents.** Per-student curation jobs need no agency — each is a mostly-deterministic pipeline with one or two structured-output LLM calls:

> retrieve candidates from index (plain code) → LLM: "given this profile and these N candidates, pick the best 5–10 with a why-note each" (typed `Recommendation[]`) → write to store.

No ReAct loop, no tool-calling, no state graph — a function. Faster, cheaper, consistent run-to-run, trivially testable. Shared indexing jobs are even less agentic: scrapers/parsers, with LLM used only for normalization/enrichment (e.g. messy faculty bio → structured research-area fields).

**Shared tool/data-access layer:** the chat agent's index tools and the pipelines' retrieval step call the same functions — data access is built once (§1), with two callers.

**Where design effort concentrates: schemas (profile, person, event, recommendation), prompts (system prompt template, rank-and-explain prompt), and the tool belt.** Graph topology stays prebuilt or trivially linear.

**Freshness policy (decided): index-first, live-verify on action.**
- Chat and surfaces read the shared index by default — fast and mutually consistent.
- Live queries in two cases: (1) index miss → live Solr/fetch fallback; (2) the data is about to be acted on (drafting an email, "is this event still on") → verify perishable fields live.
- **On conflict, live wins** and the index entry is refreshed.
- Per-type cadence: people ≈ weekly; events/seats = short cycle or live-verified. No deeper conflict-resolution machinery for the PoC.

*To be detailed: scheduling infra, output schemas.*

## 5. Feature Specs **[in progress]**

Per feature: data inputs → pipeline(s) used → personalization logic → output/UX. (See vision doc §6 for intent.)

**PoC scope decision (2026-06): the PoC is Events + Networking** — re-scoped around the public-data sweet spot found in the source research (§2.2). Networking is promoted from v2 because its data (iSearch Solr people graph, FURI mentor lists, lab/faculty pages) turned out to be fully public; clubs and jobs are deferred because their authoritative sources (Sun Devil Central, Handshake) are SSO-walled.

- **Networking** (flagship — **PoC**) — curation workflow recommends people (professors, researchers; alumni later) with a *reason* + contact path + transfer-to-chat. Data: iSearch Solr, FURI mentor lists, lab/research-group pages, departmental faculty pages. *To be detailed.*
- **Events** (PoC headliner — the public half of Campus Life) — personalized event feed from ASU Events (ICS), athletics, EOSS calendars. "What's happening this week that's actually for me." *To be detailed.*
- **Research Opportunities** (PoC, lightweight) — FURI + public research listings; overlaps Networking's faculty data. *To be detailed.*
- **Clubs** (post-PoC — needs Sun Devil Central authenticated ingestion; interim signal from per-college club pages) — *to be detailed.*
- **Jobs/Internships** (post-PoC — needs Handshake/Workday authenticated ingestion) — *to be detailed.*
- **Academics** — Canvas + major map; degree-progress awareness. *To be detailed.*
- **Chat** — deep-dive surface over all tools + curated results. *To be detailed.*

## 5.5 App Shell & Stack **[established]**

- **Frontend: React/Next.js (TypeScript).** The UI is a first-class product concern — pleasing, easy to understand, friction-minimizing, production-ready, and easy to develop in long-term. Multi-page app: onboarding, curated surfaces (Networking, Events, Opportunities), chat.
- **Backend: Python (FastAPI)** wrapping the existing LangGraph code — exposes the chat agent (streaming) and serves curated-surface data via API. Existing Python/agent investment carries over untouched.
- **Storage: Postgres via Supabase** — one database for everything: student profiles + major maps (relational, typed — matches the structured-fields rule §2.1), the shared index (people/events/opportunities tables), embeddings via pgvector when semantic matching lands. Supabase also provides **auth out of the box** (email/Google sign-up; zero custom auth code) and a TypeScript client for simple frontend reads. The Python backend talks to the same Postgres.
- **Scheduling: APScheduler (cron-style) inside the Python backend** for indexing and curation jobs. No queues, workers, or orchestrators — YAGNI at PoC scale.
- **Deployment: Vercel** (Next.js) + a small always-on Python host (**Railway/Render/Fly.io** — FastAPI must stay up to run the scheduler, so serverless doesn't fit).
- This stack is boring on purpose: every piece is replaceable later and none of it is the moat.

## 6. Integrations **[in progress]**

- **Canvas** — done (API token). Enrollments, grades, assignments.
- **College email** — recurring sync; OAuth; permission may require email-org owner consent. Phase after PoC.
- **Calendar** — recurring sync for schedule-aware suggestions. Phase after PoC.

*To be detailed: auth flows, scopes, consent model.*

## 7. Phasing **[established at high level — re-scoped 2026-06]**

- **PoC:** hybrid onboarding (agent-built major map) + Canvas; **Events + Networking surfaces** (plus lightweight Research Opportunities); Tier-1 public sources only (fetch/ICS/Solr); RAG, in-chat rendering, email/calendar deferred.
- **v2:** RAG knowledge layer; **Clubs + Jobs via user-consented authenticated ingestion** (Sun Devil Central, Handshake); social/activity graph + alumni in Networking; degree-progress intelligence on major map; email/calendar sync; unofficial long-tail registry (r/ASU, Discord/Instagram).
- **Institutional:** SSO, official data access (incl. the integrations CampusGroups has today), scale.

## 8. Open Technical Questions **[in progress]**

- Concrete table schemas: profile, major map, person, event, opportunity, recommendation. (Storage tech resolved: Supabase Postgres, §5.5. Schemas to be designed during implementation planning.)
- Knowledge layer: exact index/refresh cadence per source (policy direction set in §4).
- Networking: people-data accuracy and outreach-consent handling.
- Email/calendar: consent model, especially institutional permission (post-PoC).
- Sun Devil Central: design of the user-consented authenticated ingestion path (post-PoC); monitor for public API.
- webapp4 (legacy class search) decommission contingency: fallback is Playwright on catalog.apps.asu.edu.

## 9. Competitive Note **[established]**

**Sun Devil Central (CampusGroups / Ready Education) is the nearest existing product** — the official campus-engagement hub with university-data integrations we can't reach from outside. Its observed weaknesses (firsthand): poor personalization, no meaningful AI integration, reactive rather than proactive. **Collagent's differentiation is exactly the vision's thesis: AI-first, proactive, the student's agent** — not another portal the student has to go check. We do not compete on official-data integrations (they win there until we have institutional buy-in); we compete on intelligence, curation, and advocacy.
