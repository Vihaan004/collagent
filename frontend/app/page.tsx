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

const EMPTY_VIEW: DashboardView = {
  brief_md: "", generated_at: null, news: [], events: [], people: [], deadlines: [],
};

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
