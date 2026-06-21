// frontend/app/events/page.tsx
"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { EventRecommendation } from "@/lib/types";
import Button from "@/components/ui/Button";
import EventCard from "@/components/EventCard";
import PageHeader from "@/components/ui/PageHeader";
import { EmptyState, Spinner } from "@/components/ui/States";

export default function EventsPage() {
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
          {recs.map((rec) => <EventCard key={rec.id} rec={rec} />)}
        </ul>
      )}
    </main>
  );
}
