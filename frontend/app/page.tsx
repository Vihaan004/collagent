"use client";
import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { streamDashboardRefresh } from "@/lib/dashboardRefresh";
import type { DashboardView, Profile } from "@/lib/types";
import Button from "@/components/ui/Button";
import Eyebrow from "@/components/ui/Eyebrow";
import Markdown from "@/components/ui/Markdown";
import EventCard from "@/components/EventCard";
import PersonCard from "@/components/PersonCard";
import NewsCard from "@/components/NewsCard";
import { Spinner } from "@/components/ui/States";

const EMPTY_VIEW: DashboardView = {
  brief_md: "", generated_at: null, news: [], events: [], people: [], deadlines: [],
};

// How many items each dashboard panel previews before "View all". Tuned so the page
// holds on one screen; the rest live on the dedicated pages.
const LIMITS = { events: 4, people: 4, news: 6 };

const TODAY = new Date().toLocaleDateString(undefined, {
  weekday: "long", month: "long", day: "numeric",
});

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
        api.get("/api/dashboard").then(setView).catch(() => setView(EMPTY_VIEW));
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
  const firstName = profile.full_name ? profile.full_name.split(" ")[0] : null;
  const events = (v?.events ?? []).slice(0, LIMITS.events);
  const people = (v?.people ?? []).slice(0, LIMITS.people);
  const news = (v?.news ?? []).slice(0, LIMITS.news);
  // Split news into two newspaper-style columns to use the wide bottom band.
  const newsCols = [news.filter((_, i) => i % 2 === 0), news.filter((_, i) => i % 2 === 1)];

  return (
    <main className="lg:h-[calc(100vh-57px)] lg:overflow-hidden">
      <div className="grid h-full grid-cols-1 lg:grid-cols-[minmax(280px,23%)_1fr]">
        {/* ── Masthead / Brief rail ─────────────────────────────────────────── */}
        <aside className="flex min-h-0 flex-col border-b border-line bg-surface/50 lg:border-b-0 lg:border-r">
          <div className="border-b border-line px-6 pb-5 pt-6">
            <div className="flex items-center justify-between gap-3">
              <Eyebrow>The Daily Brief</Eyebrow>
              <span className="font-mono text-[11px] text-muted">{TODAY}</span>
            </div>
            <h1 className="mt-3 font-display text-[2rem] leading-tight text-ink">
              Hey{firstName ? <>, <span className="italic text-naval">{firstName}</span></> : ""}
            </h1>
            <p className="mt-1 text-sm text-muted">
              {profile.major_name ?? "No major set"}
              {profile.academic_year ? ` · ${profile.academic_year}` : ""}
            </p>
            <Button onClick={refresh} disabled={step !== null} className="mt-4 w-full">
              {step !== null ? "Refreshing…" : "Refresh my dashboard"}
            </Button>
            {step !== null && (
              <p className="mt-3 flex items-center gap-2 text-xs text-muted">
                <span className="h-3 w-3 animate-spin rounded-full border-2 border-line-strong border-t-naval" />
                {step}
              </p>
            )}
            {error && <p className="mt-3 text-xs text-orange">{error}</p>}
          </div>

          <div className="thin-scroll min-h-0 flex-1 overflow-y-auto px-6 py-5">
            {!v ? (
              <Spinner />
            ) : v.brief_md ? (
              <Markdown>{v.brief_md}</Markdown>
            ) : (
              <p className="text-sm text-muted">
                Your brief is empty. Hit <span className="font-medium text-ink">Refresh my dashboard</span> and
                Collagent will pull together your week — deadlines, events, people, and the
                ASU news that matters to you.
              </p>
            )}
          </div>
        </aside>

        {/* ── Panels: Events + People over News ─────────────────────────────── */}
        <section className="grid min-h-0 grid-cols-1 lg:grid-rows-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="grid min-h-0 grid-cols-1 lg:grid-cols-2">
            <Panel label="Events" href="/events" count={v?.events.length}>
              {!v ? (
                <PanelEmpty muted>Loading…</PanelEmpty>
              ) : events.length ? (
                <ul className="divide-y divide-line">
                  {events.map((rec) => <EventCard key={rec.id} rec={rec} compact />)}
                </ul>
              ) : (
                <PanelEmpty>No events yet — refresh to find some.</PanelEmpty>
              )}
            </Panel>
            <Panel label="People" href="/people" count={v?.people.length}
              className="border-t border-line lg:border-l lg:border-t-0">
              {!v ? (
                <PanelEmpty muted>Loading…</PanelEmpty>
              ) : people.length ? (
                <ul className="divide-y divide-line">
                  {people.map((rec) => <PersonCard key={rec.id} rec={rec} compact />)}
                </ul>
              ) : (
                <PanelEmpty>No people yet — refresh to find collaborators.</PanelEmpty>
              )}
            </Panel>
          </div>

          <Panel label="News" href="/news" count={v?.news.length}
            className="border-t border-line">
            {!v ? (
              <PanelEmpty muted>Loading…</PanelEmpty>
            ) : news.length ? (
              <div className="grid grid-cols-1 gap-x-10 lg:grid-cols-2">
                {newsCols.map((col, i) => (
                  <ul key={i} className="divide-y divide-line">
                    {col.map((n, j) => <NewsCard key={n.id ?? `${i}-${j}`} item={n} compact />)}
                  </ul>
                ))}
              </div>
            ) : (
              <PanelEmpty>No news yet — refresh to pull the latest from ASU.</PanelEmpty>
            )}
          </Panel>
        </section>
      </div>
    </main>
  );
}

function Panel({
  label, href, count, children, className = "",
}: {
  label: string;
  href: string;
  count?: number;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`flex min-h-0 flex-col ${className}`}>
      <div className="flex items-center justify-between gap-3 px-5 pb-3 pt-4">
        <span className="flex items-center gap-2.5">
          <Eyebrow>{label}</Eyebrow>
          {count !== undefined && count > 0 && (
            <span className="font-mono text-[11px] text-muted/70">{count}</span>
          )}
        </span>
        <Link href={href}
          className="text-xs font-medium text-muted transition-colors hover:text-naval">
          View all →
        </Link>
      </div>
      <div className="thin-scroll min-h-0 flex-1 overflow-y-auto px-5 pb-5">{children}</div>
    </div>
  );
}

function PanelEmpty({ children, muted = false }: { children: ReactNode; muted?: boolean }) {
  return <p className={`pt-2 text-sm ${muted ? "text-muted/70" : "text-muted"}`}>{children}</p>;
}
