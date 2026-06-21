# Dashboard Spine (Frontend) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate the Home page into the agent-managed "Daily Brief" feed — Brief, Deadlines, ASU Happenings, top-5 Events, top-5 People — rendered from `GET /api/dashboard`, with a "Refresh my dashboard" button that streams the orchestrator's progress in place over the chat SSE transport.

**Architecture:** Home becomes a single client page that fetches `GET /api/dashboard` (one call returns the stored Brief + tuned news plus live top recommendations and deadlines). The Refresh button POSTs the canned message `refresh my dashboard` to the existing `/api/chat` SSE endpoint, shows each tool step as it streams, then re-fetches `GET /api/dashboard` when the stream ends. Event/People card markup is extracted into shared components so Home and (briefly) the old pages share one source; the standalone `/events` and `/people` pages and their nav links are then removed.

**Tech Stack:** Next.js 16 (App Router, client components), React, Tailwind, `react-markdown` + `remark-gfm` (already used in chat), existing `lib/api.ts` (`api.get`, `apiFetch`) and `lib/supabase` auth.

**Decisions (locked with the user):**
- **Refresh UX:** in-place progress on Home (stream tool steps, then auto-refetch). NOT a hand-off to `/chat`.
- **Old routes:** delete `app/events/page.tsx` and `app/people/page.tsx` after extracting their cards into shared components. Old URLs will 404 (acceptable; nav is the only entry today).
- **Nav:** collapses to Home · Chat · Profile (+ Sign out). Profile stays a nav link (the spec's "account menu" is gold-plating; not in scope).
- **No frontend unit tests exist** (no vitest/jest). Per prior frontend slices, the gate is `npx tsc --noEmit` (typecheck) + `npm run lint` + a described live smoke. `npm run build` is the final full gate.

> ⚠️ **Per `frontend/AGENTS.md`:** this is Next.js **16.2.9** with breaking changes vs. older training data. Before writing any frontend code, skim the relevant guide under `frontend/node_modules/next/dist/docs/01-app/`. Follow the patterns already in this repo (`app/chat/page.tsx`, `app/events/page.tsx`) over anything from memory.

---

## File Structure

- **Modify** `frontend/lib/types.ts` — add `CalendarItem`, `DashboardNewsPick`, `DashboardView` interfaces mirroring the backend models.
- **Create** `frontend/components/EventCard.tsx` — one event recommendation card (title link, when/location, "Discuss in chat", why-note). Self-contained: owns its `formatWhen` + `discuss` navigation.
- **Create** `frontend/components/PersonCard.tsx` — one person recommendation card (avatar initials, name link, title/depts, expertise badges, why-note, email, "Discuss in chat"). Owns its `initials` + `discuss`.
- **Create** `frontend/lib/dashboardRefresh.ts` — `streamDashboardRefresh(onStep)`: POSTs `refresh my dashboard` to `/api/chat`, parses the SSE stream, invokes `onStep(label)` per tool event, resolves when the stream ends.
- **Rewrite** `frontend/app/page.tsx` — the consolidated dashboard Home.
- **Modify** `frontend/components/Nav.tsx` — drop the Events/People links.
- **Delete** `frontend/app/events/page.tsx`, `frontend/app/people/page.tsx`.

Each task leaves the app building green and shippable.

---

## Task D-T1: Frontend dashboard types

**Files:**
- Modify: `frontend/lib/types.ts` (append after `Memory`, end of file)

- [ ] **Step 1: Add the interfaces**

Mirror the backend models exactly (`src/collagent/models.py` lines 103–169). Append to `frontend/lib/types.ts`:

```ts
export interface CalendarItem {
  id: string;
  term: string;
  session: string;
  title: string;
  date_start: string | null;
  date_end: string | null;
  category: string | null;
  fetched_at: string | null;
}

export interface DashboardNewsPick {
  id: string | null;
  title: string;
  url: string;
  summary: string | null;
  published_at: string | null;
  why_note: string | null;
}

export interface DashboardView {
  brief_md: string;
  generated_at: string | null;
  news: DashboardNewsPick[];
  events: EventRecommendation[];
  people: PersonRecommendation[];
  deadlines: CalendarItem[];
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors (these are additive type declarations; nothing references them yet).

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/types.ts
git commit -m "feat: dashboard view types for the home feed"
```

---

## Task D-T2: Extract EventCard and PersonCard shared components

Behavior-preserving extraction: pull the card markup out of the two pages into reusable components, then point the existing pages at them. The pages still render identically and build stays green. (D-T5 deletes the pages; Home will use these components in D-T4.)

**Files:**
- Create: `frontend/components/EventCard.tsx`
- Create: `frontend/components/PersonCard.tsx`
- Modify: `frontend/app/events/page.tsx` (replace inline card with `<EventCard>`)
- Modify: `frontend/app/people/page.tsx` (replace inline card with `<PersonCard>`)

- [ ] **Step 1: Create `frontend/components/EventCard.tsx`**

Lift the card markup + `formatWhen` + `discuss` from `app/events/page.tsx` verbatim. Card already supports `as="li"`.

```tsx
"use client";
import { useRouter } from "next/navigation";
import type { EventRecommendation } from "@/lib/types";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";

function formatWhen(iso: string | null): string {
  if (!iso) return "Date TBD";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });
}

export default function EventCard({ rec }: { rec: EventRecommendation }) {
  const router = useRouter();
  function discuss() {
    const ask = `Tell me about the event: ${rec.title}`;
    router.push(`/chat?ask=${encodeURIComponent(ask)}`);
  }
  return (
    <Card as="li">
      <div className="flex items-start justify-between gap-3">
        <div>
          <a href={rec.url} target="_blank" rel="noopener noreferrer"
            className="font-medium text-ink hover:text-naval hover:underline">
            {rec.title}
          </a>
          <p className="mt-0.5 text-xs text-muted">
            {formatWhen(rec.starts_at)}{rec.location ? ` · ${rec.location}` : ""}
          </p>
        </div>
        <Button variant="secondary" onClick={discuss}
          className="shrink-0 px-3 py-1.5 text-xs">
          Discuss in chat
        </Button>
      </div>
      <p className="mt-3 rounded-r-md border-l-[3px] border-orange bg-cream-200 px-3 py-2 text-sm leading-relaxed text-ink/90">
        {rec.why_note}
      </p>
    </Card>
  );
}
```

- [ ] **Step 2: Create `frontend/components/PersonCard.tsx`**

Lift the card markup + `initials` + `discuss` from `app/people/page.tsx` verbatim.

```tsx
"use client";
import { useRouter } from "next/navigation";
import type { PersonRecommendation } from "@/lib/types";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[parts.length - 1]?.[0] ?? "")).toUpperCase();
}

export default function PersonCard({ rec }: { rec: PersonRecommendation }) {
  const router = useRouter();
  function discuss() {
    const role = rec.title ? `, ${rec.title}` : "";
    const ask = `Tell me about ${rec.name}${role} at ASU and how I might connect with them.`;
    router.push(`/chat?ask=${encodeURIComponent(ask)}`);
  }
  return (
    <Card as="li">
      <div className="flex items-start gap-3">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-cream text-sm font-medium text-naval">
          {initials(rec.name)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <a href={rec.profile_url} target="_blank" rel="noopener noreferrer"
                className="font-medium text-ink hover:text-naval hover:underline">
                {rec.name}
              </a>
              <p className="mt-0.5 text-xs text-muted">
                {rec.title ?? "ASU"}{rec.departments.length ? ` · ${rec.departments.join(", ")}` : ""}
              </p>
            </div>
            <Button variant="secondary" onClick={discuss}
              className="shrink-0 px-3 py-1.5 text-xs">
              Discuss in chat
            </Button>
          </div>

          {rec.expertise_areas.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {rec.expertise_areas.slice(0, 5).map((area) => (
                <Badge key={area}>{area}</Badge>
              ))}
            </div>
          )}

          <p className="mt-3 rounded-r-md border-l-[3px] border-orange bg-cream-200 px-3 py-2 text-sm leading-relaxed text-ink/90">
            {rec.why_note}
          </p>

          {rec.email && (
            <a href={`mailto:${rec.email}`}
              className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-naval hover:underline">
              {rec.email}
            </a>
          )}
        </div>
      </div>
    </Card>
  );
}
```

- [ ] **Step 3: Point `app/events/page.tsx` at `EventCard`**

Remove the local `formatWhen` and `discuss`, remove the now-unused `useRouter`/`Card` imports if no longer referenced (keep `Card`? no — the list no longer wraps in Card directly). Replace the `recs.map(...)` block so each item is `<EventCard key={rec.id} rec={rec} />`. Add `import EventCard from "@/components/EventCard";`. The `<ul className="space-y-4">` wrapper stays.

- [ ] **Step 4: Point `app/people/page.tsx` at `PersonCard`**

Same: remove local `initials`/`discuss`, drop unused imports (`useRouter`, `Card`, `Badge` now live in the component), render `<PersonCard key={rec.id} rec={rec} />` inside the existing `<ul>`. Add `import PersonCard from "@/components/PersonCard";`.

- [ ] **Step 5: Typecheck + lint**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: clean. Lint will catch any leftover unused imports — remove them.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/EventCard.tsx frontend/components/PersonCard.tsx frontend/app/events/page.tsx frontend/app/people/page.tsx
git commit -m "refactor: extract EventCard and PersonCard components"
```

---

## Task D-T3: Dashboard refresh SSE helper

A small module that drives the orchestrator refresh over the existing chat SSE stream and reports progress. Mirrors the SSE parsing in `app/chat/page.tsx` (events: `token`, `tool`, `tool_result`, `error`; framed by `\n\n`, each line prefixed `data: `). For the dashboard we only surface `tool` steps as human labels.

**Files:**
- Create: `frontend/lib/dashboardRefresh.ts`

- [ ] **Step 1: Write the helper**

```ts
import { apiFetch } from "@/lib/api";

// Human-friendly labels for the orchestrator's refresh tools; falls back to the raw
// tool name so new tools still show *something*.
const STEP_LABELS: Record<string, string> = {
  refresh_events: "Refreshing events…",
  refresh_people: "Finding people…",
  refresh_news: "Fetching ASU news…",
  update_calendar: "Updating the calendar…",
  get_news: "Reviewing news…",
  get_deadlines: "Checking deadlines…",
  get_event_recommendations: "Reading your events…",
  get_person_recommendations: "Reading your people…",
  save_dashboard_brief: "Writing your brief…",
};

export const REFRESH_PROMPT = "Refresh my dashboard";

/**
 * Run a full dashboard refresh by prompting the orchestrator over the chat SSE
 * transport. Calls `onStep` with a friendly label each time a tool starts.
 * Resolves when the stream ends; rejects on transport/auth error.
 */
export async function streamDashboardRefresh(
  onStep: (label: string) => void,
): Promise<void> {
  const res = await apiFetch("/api/chat", {
    method: "POST",
    body: JSON.stringify({ message: REFRESH_PROMPT, thread_id: "web" }),
  });
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const event = JSON.parse(line.slice(6));
      if (event.type === "tool" && event.name) {
        onStep(STEP_LABELS[event.name] ?? `Running ${event.name}…`);
      } else if (event.type === "error") {
        throw new Error("refresh stream error");
      }
    }
  }
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/dashboardRefresh.ts
git commit -m "feat: dashboard refresh SSE helper"
```

---

## Task D-T4: Rewrite Home as the Daily Brief feed

**Files:**
- Rewrite: `frontend/app/page.tsx`

**Behavior:**
- On mount: `api.get("/api/profile")`. If not onboarded → `router.replace("/onboarding")`. On auth failure → `router.replace("/login")`. Then `api.get("/api/dashboard")` into a `DashboardView`.
- Render header greeting (keep the existing `Hey, {first name}` + profile subline) with the Refresh button in the action slot.
- Refresh button: disabled while running; calls `streamDashboardRefresh(setStep)`; on resolve, re-fetch `GET /api/dashboard` and clear the step; on reject, show a one-line inline error and keep the current view. While running, render the current `step` label as a small progress strip under the header.
- Sections top→bottom, each only rendered when it has content (the dashboard may be empty before the first refresh — show one `EmptyState` prompting Refresh if everything is empty and not loading):
  1. **The Brief** — `brief_md` via `ReactMarkdown` + `remarkGfm` in a `Card` with the `chat-md` class (same styling hook chat uses). Show `generated_at` as a relative-ish caption if present. Skip if `brief_md` is empty.
  2. **Upcoming Deadlines** — `deadlines` as a compact list (date + title + optional category badge). Skip if empty.
  3. **ASU Happenings** — `news` as cards: title links to `url` (new tab), `summary`, and the `why_note` in the orange left-border treatment. Skip if empty.
  4. **Recommended Events** — `events` → `<EventCard>` in a `<ul className="space-y-4">`. Skip if empty.
  5. **People to Connect** — `people` → `<PersonCard>`. Skip if empty.

- [ ] **Step 1: Write `frontend/app/page.tsx`**

```tsx
"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "@/lib/api";
import { streamDashboardRefresh } from "@/lib/dashboardRefresh";
import type { Profile, DashboardView } from "@/lib/types";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import EventCard from "@/components/EventCard";
import PersonCard from "@/components/PersonCard";
import { EmptyState, Spinner } from "@/components/ui/States";

function formatDate(iso: string | null): string {
  if (!iso) return "TBD";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso; // calendar dates may be non-ISO strings
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function HomePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [view, setView] = useState<DashboardView | null>(null);
  const [step, setStep] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get("/api/profile")
      .then((p: Profile) => {
        if (!p.onboarded) {
          router.replace("/onboarding");
          return;
        }
        setProfile(p);
        api.get("/api/dashboard").then(setView).catch(() => setView(null));
      })
      .catch(() => router.replace("/login"));
  }, [router]);

  async function refresh() {
    if (step !== null) return;
    setError(null);
    setStep("Starting…");
    try {
      await streamDashboardRefresh(setStep);
      setView(await api.get("/api/dashboard"));
    } catch {
      setError("Refresh didn't finish — try again.");
    } finally {
      setStep(null);
    }
  }

  if (!profile) return <main className="p-6"><Spinner /></main>;

  const v = view;
  const everythingEmpty =
    !!v && !v.brief_md && v.news.length === 0 && v.events.length === 0 &&
    v.people.length === 0 && v.deadlines.length === 0;

  return (
    <main className="mx-auto max-w-3xl space-y-8 p-6">
      <header className="flex items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-4xl leading-tight text-ink">
            Hey{profile.full_name ? `, ${profile.full_name.split(" ")[0]}` : ""}
          </h1>
          <p className="mt-2 text-sm text-muted">
            {profile.major_name ?? "No major set"}
            {profile.academic_year ? ` · ${profile.academic_year}` : ""}
          </p>
        </div>
        <Button onClick={refresh} disabled={step !== null} className="shrink-0">
          {step !== null ? "Refreshing…" : "Refresh my dashboard"}
        </Button>
      </header>

      {step !== null && (
        <p className="flex items-center gap-2 text-sm text-muted">
          <span className="h-3 w-3 animate-spin rounded-full border-2 border-line-strong border-t-naval" />
          {step}
        </p>
      )}
      {error && <p className="text-sm text-orange">{error}</p>}

      {!v ? (
        <Spinner />
      ) : everythingEmpty && step === null ? (
        <EmptyState
          title="Your Daily Brief is empty"
          hint="Hit “Refresh my dashboard” and Collagent will pull together your events, people, news, and deadlines."
          action={<Button onClick={refresh}>Refresh my dashboard</Button>}
        />
      ) : (
        <div className="space-y-8">
          {v.brief_md && (
            <Card>
              <div className="chat-md">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{v.brief_md}</ReactMarkdown>
              </div>
            </Card>
          )}

          {v.deadlines.length > 0 && (
            <Section title="Upcoming Deadlines">
              <Card>
                <ul className="space-y-2">
                  {v.deadlines.map((c) => (
                    <li key={c.id} className="flex items-center gap-3 text-sm">
                      <span className="w-14 shrink-0 font-medium text-naval">{formatDate(c.date_start)}</span>
                      <span className="flex-1 text-ink">{c.title}</span>
                      {c.category && <Badge>{c.category}</Badge>}
                    </li>
                  ))}
                </ul>
              </Card>
            </Section>
          )}

          {v.news.length > 0 && (
            <Section title="ASU Happenings">
              <ul className="space-y-4">
                {v.news.map((n, i) => (
                  <Card as="li" key={n.id ?? i}>
                    <a href={n.url} target="_blank" rel="noopener noreferrer"
                      className="font-medium text-ink hover:text-naval hover:underline">
                      {n.title}
                    </a>
                    {n.summary && <p className="mt-1 text-sm text-muted">{n.summary}</p>}
                    {n.why_note && (
                      <p className="mt-3 rounded-r-md border-l-[3px] border-orange bg-cream-200 px-3 py-2 text-sm leading-relaxed text-ink/90">
                        {n.why_note}
                      </p>
                    )}
                  </Card>
                ))}
              </ul>
            </Section>
          )}

          {v.events.length > 0 && (
            <Section title="Recommended Events">
              <ul className="space-y-4">
                {v.events.map((rec) => <EventCard key={rec.id} rec={rec} />)}
              </ul>
            </Section>
          )}

          {v.people.length > 0 && (
            <Section title="People to Connect">
              <ul className="space-y-4">
                {v.people.map((rec) => <PersonCard key={rec.id} rec={rec} />)}
              </ul>
            </Section>
          )}
        </div>
      )}
    </main>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="mb-3 font-display text-xl text-ink">{title}</h2>
      {children}
    </section>
  );
}
```

- [ ] **Step 2: Typecheck + lint**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: clean. (`react-markdown`/`remark-gfm` are already deps — see `app/chat/page.tsx`.)

- [ ] **Step 3: Commit**

```bash
git add frontend/app/page.tsx
git commit -m "feat: consolidate Home into the Daily Brief dashboard feed"
```

---

## Task D-T5: Collapse nav and remove old routes

**Files:**
- Modify: `frontend/components/Nav.tsx`
- Delete: `frontend/app/events/page.tsx`
- Delete: `frontend/app/people/page.tsx`

- [ ] **Step 1: Trim the nav links**

In `frontend/components/Nav.tsx`, reduce `LINKS` to:

```tsx
const LINKS = [
  { href: "/", label: "Home" },
  { href: "/chat", label: "Chat" },
  { href: "/profile", label: "Profile" },
];
```

Leave everything else (active-link logic, sign-out) unchanged.

- [ ] **Step 2: Delete the standalone pages**

```bash
git rm frontend/app/events/page.tsx frontend/app/people/page.tsx
```

- [ ] **Step 3: Verify nothing else imports them**

Run: `cd frontend && grep -rn "app/events\|app/people\|/events\|/people" app components lib --include=*.ts --include=*.tsx`
Expected: no references to the deleted page routes. (The `discuss()` handlers navigate to `/chat?ask=`, not `/events`/`/people`, so cards are unaffected. The `?ask=` deep-link into `/chat` still works.)

- [ ] **Step 4: Typecheck + lint**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/Nav.tsx
git commit -m "feat: collapse nav to Home/Chat/Profile, drop standalone event/people pages"
```

---

## Task D-T6: Full build, live smoke, review, finish

**Files:** none (verification + integration).

- [ ] **Step 1: Full production build (final typecheck gate)**

Run: `cd frontend && npm run build`
Expected: build succeeds with no type errors and the `/events`,`/people` routes absent from the route manifest; `/` present.

- [ ] **Step 2: Backend suite still green**

Run: `uv run pytest -q`
Expected: 155 passed (no backend changes in this slice; this is a guard against accidental edits).

- [ ] **Step 3: Live smoke (manual, with the dev servers running)**

Bring up backend (`uv run uvicorn collagent.api.main:app --reload`) and frontend (`cd frontend && npm run dev`), sign in as the test user, then verify:
- Home loads and calls `GET /api/dashboard` once (Network tab); the last stored Brief + sections render immediately.
- Clicking **Refresh my dashboard** streams progress labels in order (events → people → news → calendar → brief), the button is disabled meanwhile, and on completion the feed re-renders with fresh data.
- Each empty section is hidden; a fully empty dashboard shows the single EmptyState.
- "Discuss in chat" on an event/person card opens `/chat` and auto-sends the prompt.
- Nav shows only Home · Chat · Profile; visiting `/events` 404s.

- [ ] **Step 4: Request code review**

Use superpowers:requesting-code-review against the diff for this slice (combine spec-compliance + code-quality into one reviewer per the [[subagent-efficiency]] preference). Address any blocking findings; note cosmetic ones.

- [ ] **Step 5: Finish the branch**

Use superpowers:finishing-a-development-branch (verify tests → present the 4 options → execute the user's choice).

---

## Self-Review

**Spec coverage (design doc §3 + §5):**
- Nav → Home + Chat (+ Profile reachable): D-T5. ✓
- Home renders Brief, Deadlines, ASU Happenings, top-5 Events, top-5 People from DB: D-T4 reads `GET /api/dashboard` (backend already slices events/people to top-5). ✓
- Brief is markdown, lightweight: D-T4 renders `brief_md` via ReactMarkdown. ✓
- "Discuss in chat" hand-off on event/people cards: preserved in EventCard/PersonCard (D-T2). ✓
- Refresh = prompt to orchestrator over chat SSE, with visible progress, dashboard renders last stored state instantly: D-T3 helper + D-T4 wiring. ✓
- `/events`,`/people` cease to be destinations: D-T5 deletes them. ✓

**Placeholder scan:** every code step contains full file contents or an exact, unambiguous edit. No TBD/"handle edge cases". ✓

**Type consistency:** `DashboardView`/`DashboardNewsPick`/`CalendarItem` (D-T1) match backend `models.py` field-for-field and are the exact types consumed in D-T4. `EventCard`/`PersonCard` take `{ rec }` of the existing `EventRecommendation`/`PersonRecommendation` types. `streamDashboardRefresh(onStep)` signature matches its D-T4 call site (`setStep`). ✓

**Risks:**
- Calendar `date_start` may not be ISO-parseable; `formatDate` falls back to the raw string (handled).
- The `thread_id: "web"` shares the chat thread — a refresh appends to the same conversation history. Acceptable (the orchestrator is one agent); noted for the reviewer. If undesirable later, use a separate thread id for refreshes.
