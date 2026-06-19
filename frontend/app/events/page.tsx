// frontend/app/events/page.tsx
"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { EventRecommendation } from "@/lib/types";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import PageHeader from "@/components/ui/PageHeader";
import { EmptyState, Spinner } from "@/components/ui/States";

function formatWhen(iso: string | null): string {
  if (!iso) return "Date TBD";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });
}

export default function EventsPage() {
  const router = useRouter();
  const [recs, setRecs] = useState<EventRecommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    api.get("/api/events")
      .then(setRecs)
      .catch(() => setRecs([]))
      .finally(() => setLoading(false));
  }, []);

  async function refresh() {
    setRefreshing(true);
    try {
      setRecs(await api.post("/api/events/refresh", {}));
    } catch {
      // surface a minimal error; keep existing recs
    } finally {
      setRefreshing(false);
    }
  }

  function discuss(rec: EventRecommendation) {
    const ask = `Tell me about the event: ${rec.title}`;
    router.push(`/chat?ask=${encodeURIComponent(ask)}`);
  }

  return (
    <main className="mx-auto w-full max-w-2xl p-6">
      <PageHeader
        title="Events for you"
        subtitle="Picked from what's happening at ASU around your interests."
        action={
          <Button onClick={refresh} disabled={refreshing}>
            {refreshing ? "Finding events…" : "Refresh"}
          </Button>
        }
      />

      {loading ? (
        <Spinner />
      ) : recs.length === 0 ? (
        <EmptyState
          title="No recommendations yet"
          hint="Hit Refresh and Collagent will scan upcoming ASU events for you."
          action={<Button onClick={refresh} disabled={refreshing}>Refresh</Button>}
        />
      ) : (
        <ul className="space-y-4">
          {recs.map((rec) => (
            <Card as="li" key={rec.id}>
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
                <Button variant="secondary" onClick={() => discuss(rec)}
                  className="shrink-0 px-3 py-1.5 text-xs">
                  Discuss in chat
                </Button>
              </div>
              <p className="mt-3 rounded-r-md border-l-[3px] border-orange bg-cream-200 px-3 py-2 text-sm leading-relaxed text-ink/90">
                {rec.why_note}
              </p>
            </Card>
          ))}
        </ul>
      )}
    </main>
  );
}
