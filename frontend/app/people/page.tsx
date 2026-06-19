// frontend/app/people/page.tsx
"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { PersonRecommendation } from "@/lib/types";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import PageHeader from "@/components/ui/PageHeader";
import { EmptyState, Spinner } from "@/components/ui/States";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[parts.length - 1]?.[0] ?? "")).toUpperCase();
}

export default function PeoplePage() {
  const router = useRouter();
  const [recs, setRecs] = useState<PersonRecommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    api.get("/api/people")
      .then(setRecs)
      .catch(() => setRecs([]))
      .finally(() => setLoading(false));
  }, []);

  async function refresh() {
    setRefreshing(true);
    try {
      setRecs(await api.post("/api/people/refresh", {}));
    } catch {
      // keep existing recs on failure
    } finally {
      setRefreshing(false);
    }
  }

  function discuss(rec: PersonRecommendation) {
    const role = rec.title ? `, ${rec.title}` : "";
    const ask = `Tell me about ${rec.name}${role} at ASU and how I might connect with them.`;
    router.push(`/chat?ask=${encodeURIComponent(ask)}`);
  }

  return (
    <main className="mx-auto w-full max-w-2xl p-6">
      <PageHeader
        title="People to connect with"
        subtitle="Faculty and mentors worth reaching out to, matched to your path."
        action={
          <Button onClick={refresh} disabled={refreshing}>
            {refreshing ? "Finding people…" : "Refresh"}
          </Button>
        }
      />

      {loading ? (
        <Spinner />
      ) : recs.length === 0 ? (
        <EmptyState
          title="No recommendations yet"
          hint="Hit Refresh and Collagent will find ASU faculty aligned with your interests."
          action={<Button onClick={refresh} disabled={refreshing}>Refresh</Button>}
        />
      ) : (
        <ul className="space-y-4">
          {recs.map((rec) => (
            <Card as="li" key={rec.id}>
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
                    <Button variant="secondary" onClick={() => discuss(rec)}
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
          ))}
        </ul>
      )}
    </main>
  );
}
