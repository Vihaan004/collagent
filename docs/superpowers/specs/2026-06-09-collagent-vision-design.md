# Collagent — Vision & North-Star Document

**Status:** Living document. Captures the *ideal* collagent experience and the strategy behind it. Guides all development. Revisited as ideas evolve.

**Date:** 2026-06-09
**Scope:** This is the product vision / north star. The PoC technical spec (architecture, tool design, build order) is a separate document.

---

## 1. Vision & Thesis

**Collagent is a proactive, personalized operating layer over your university.**

Today, getting value from a university means manually hunting across dozens of disconnected websites — class search, club directories, event calendars, job boards, advising pages, research labs — and then mentally filtering everything down to what's actually relevant to *you*. The information exists; the friction is enormous, and most students never find the resources they're entitled to.

Collagent collapses that. It knows who the student is — their major, interests, courses, clubs, goals — and it **pre-researches the institution on their behalf**, surfacing curated, relevant resources *up front* with minimal friction. People worth meeting, events worth attending, opportunities worth applying to, requirements worth planning around — each delivered already filtered to the individual, each carrying a reason it was chosen.

**Why this beats the alternatives:**

- **vs. Googling the university's websites** — Collagent aggregates fragmented sources into one place *and* personalizes. The student stops navigating; the resources come to them.
- **vs. the university's own AI chatbot** — An official bot is generic, liability-averse, and built to answer *the institution's* FAQs. It will not advocate for one student's goals, reason across their personal context, or proactively connect them to a specific professor. Collagent works *for the student*.
- **vs. ChatGPT / Claude + connectors** — General assistants have the reasoning but lack the curated, institution-specific knowledge and the persistent personal context. They are pull, not push; reactive, not proactive.

## 2. The Wedge

Collagent's defensible position is the **intersection of aggregation and personalization**:

> **Aggregation** (one place for fragmented, hard-to-find institutional information)
> **× Personalization** (everything filtered through who this student is — major, interests, courses, clubs, network, goals)

Neither a search engine nor an official bot occupies that intersection well. Two reinforcing moats grow from it:

1. **The curated institutional knowledge layer** — the indexed, structured, continuously-maintained model of one university's resources. This is hard to build and maintain, and it *is* the product. The chat is just the interface.
2. **The personal context graph** — the accumulating model of each student (and, over time, the network connecting them). The longer a student uses collagent, the better and more irreplaceable it gets.

## 3. Target User & Go-To-Market

**Primary user:** ASU students. Single-campus depth before multi-campus breadth — a tool that does *everything* for ASU is more valuable and more sellable than a shallow tool spanning fifty schools.

**GTM (Direction C — bottom-up, then institutional):**

1. **Bottom-up first.** Students adopt collagent individually. Data comes from public ASU sources plus the student's own credentialed access (Canvas) and self-provided context. Fast to launch, full product control, real user feedback.
2. **Institutional later.** Use student traction as leverage to sell ASU itself — unlocking richer data access, SSO, and built-in distribution. This is where it scales.

The PoC exists to prove the thesis with real student test users and to serve as a demo for future institutional conversations.

## 4. Design Principles

These are the non-negotiable values that define the collagent experience:

- **Push, not pull.** The primary features are *served up front*, pre-computed by background research. The student should get value before typing anything. Chat is one surface and the place to go deeper — not the only way in.
- **Minimal friction.** Every feature is measured by how much effort it removes from using college resources. If it adds steps, it's wrong.
- **Every recommendation carries a reason.** Nothing is surfaced as an opaque suggestion. The student always sees *why* this person / event / opportunity was matched to them. Trust comes from transparency.
- **The curated index is the product.** Invest in the institutional knowledge layer, not the chat wrapper. The agent loop is commodity; the data is the moat.
- **Depth before breadth.** Nail ASU completely before generalizing. Nail one domain impressively before spreading thin.
- **The student's advocate.** Collagent works for the student's goals, not the institution's messaging. This is the philosophical line that separates it from any official tool.

## 5. Personal Data Model

Collagent's personalization is only as good as what it knows about the student. The model, in order of build priority:

- **Onboarding (hybrid).** Major, year, interests, goals, current clubs, projects, on-campus jobs. Lightweight, transparent, works day one. Editable anytime — including conversationally, with the agent applying updates through structured fields. The principle: never make the student type what collagent can fetch (e.g. the major map is pre-built from published requirements and merely confirmed); never infer what only the student knows (interests, goals).
- **Canvas (credentialed).** Enrolled courses and grade/assignment details. Note: Canvas is *thin* on personal data — it gives enrollments and academic performance, not interests or intent. Useful but narrow.
- **Major Map (student-owned primitive).** The full set of requirements for the student's program, with each course tagged *taken / in-progress / remaining*. Created in a one-time setup, editable when the student changes major. This is both a richer personalization substrate than Canvas alone *and* a feature in its own right (degree-progress awareness). A named, first-class component.
- **Social / activity graph (future moat).** Inferred and accumulated context: who the student knows, what they engage with in-app, the network connecting students, professors, researchers, and alumni in a field. The richest and most defensible signal — and the most privacy-sensitive.

**Privacy & trust stance:** Because the entire pitch leverages personal data, trust is a first-class design surface, not an afterthought. The student owns their data and their context. Recommendations are transparent (the "reason" principle). Data collection is opt-in and legible. This stance must be designed deliberately as the personal graph grows.

## 6. Core Surfaces & Features

Collagent is a set of **pre-computed surfaces** plus chat — not a single chat box. Each surface is populated proactively and personalized.

### Networking (flagship)
The clearest expression of the vision. Collagent collects the student's context — major, interests, courses, clubs, projects, jobs, goals — and **proactively recommends people worth connecting with**, grounded in purpose and data: professors, researchers, and alumni in the student's field and interests.

*Hero example:* A Computer Systems Engineering major interested in FPGAs, enrolled in a hardware-acceleration club, who wants to work with FPGAs professionally → collagent surfaces Prof. Aman Arora (FPGA research + relevant classes at ASU), other ASU researchers in the area, and alumni working in the field. Each entry includes a contact path, a **note explaining why they were matched**, and a button to **transfer the recommendation into a new chat** to go deeper (e.g. draft an intro email, learn about their research).

A dedicated Networking page lists these people up front. The student does no searching.

### Campus Life
Clubs, organizations, events, fairs, sports — filtered to the individual. The crisp magic moment: *"What's happening this week that's actually for me?"* This is where "curated + personal" most visibly beats both Google and an official bot. (The *events* half is the PoC headliner; clubs follow once authenticated ingestion exists — see §8.)

### Opportunities
Jobs, internships, research positions, career services — matched to the student's field, skills, and goals. Reuses the same discovery-and-match machinery as Campus Life and Networking, pointed at a different source set.

### Academics (Canvas + Major Map)
Table stakes, already partly built via Canvas. Degree-progress awareness via the major map ("you still need a 400-level systems elective; here are the two offered next fall that fit your FPGA interest"), course/degree information, assignment and grade context.

### Chat (deep-dive surface)
Not the front door — the place to go deeper on anything surfaced elsewhere, and a general agentic interface to all of collagent's tools and knowledge. Recommendations and items from other surfaces flow *into* chat.

## 7. Data Access Strategy

There is no clean university API for most of this information, so data access is the central engineering challenge — and the factor that most determines collagent's impact. The strategy is a spectrum, applying the cheapest sufficient tool to each source:

1. **HTTP fetch + HTML→text extraction** — most ASU content pages (degree info, services, club descriptions) are server-rendered and can be fetched cheaply, no browser needed. Primary tool; covers the majority of "university information."
2. **Headless browser (Playwright), used surgically** — reserved *only* for JS-rendered, interactive sources (e.g. Class Search) that won't yield to a plain fetch. The expensive tool, used where actually required.
3. **Pre-indexed retrieval (RAG)** — periodically crawl the stable content, chunk and embed it, retrieve in milliseconds. This is the moat and gives the snappy latency proactive surfaces and demos require.

**Architectural commitment:** the agent's tool interface stays stable across these backends, so the system can start with live fetch and swap in a cached/indexed backend later without changing the agent.

## 8. Roadmap / Phasing

- **PoC (now):** Prove the thesis with real student test users; serve as a demo.
  - Personalization: hybrid onboarding (agent-built major map, student-confirmed) + Canvas.
  - Domains: **Events** (the public half of Campus Life) as headliner, **Networking** as the flagship differentiator — promoted into the PoC after source research showed ASU's people graph (iSearch) and research listings (FURI) are fully public, while clubs (Sun Devil Central) and jobs (Handshake) sit behind SSO.
  - Data access: public sources only — HTTP fetch, ICS feeds, the iSearch Solr endpoint. Full RAG index deferred but interface kept stable. In-chat website rendering deferred (YAGNI).
- **v2:** The compounding moat. Pre-indexed RAG knowledge layer; clubs and jobs via user-consented authenticated ingestion; social/activity graph and alumni in Networking; degree-progress intelligence on the major map; email/calendar sync.
- **Institutional:** Sell ASU. SSO, deeper/official data access, scale. Generalize to additional campuses only after ASU is deep.

## 9. Risks & Open Questions

- **Data maintenance cost.** The curated index is the moat *and* the recurring cost. University sites change and fragment; keeping the knowledge layer fresh per-institution is the make-or-break operational challenge.
- **Privacy & trust.** The personal graph is the magic and the liability. Mishandling it kills adoption. Stance must be deliberate (see §5).
- **Competition from official bots.** ASU could ship its own assistant. Defense: collagent is the student's advocate, personalized and proactive in ways an institutional tool structurally cannot be.
- **Open: scraping posture.** Terms-of-service and rate-limit considerations for scraping ASU sources bottom-up, before any institutional agreement.
- **Open: networking accuracy & consent.** Recommending real people (professors, alumni) by name raises accuracy and outreach-etiquette questions to resolve before the flagship ships.
