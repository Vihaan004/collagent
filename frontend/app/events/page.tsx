"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { EventRecommendation } from "@/lib/types";
import EventCard from "@/components/EventCard";
import PageHeader from "@/components/ui/PageHeader";
import Button from "@/components/ui/Button";
import { Spinner, EmptyState } from "@/components/ui/States";

export default function EventsPage() {
  const [items, setItems] = useState<EventRecommendation[] | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/api/events").then(setItems).catch(() => setItems([]));
  }, []);

  async function refresh() {
    if (busy) return;
    setBusy(true);
    try {
      setItems(await api.post("/api/events/refresh", {}));
    } catch {
      // leave the current list in place; the button re-enables to retry
    } finally {
      setBusy(false);
    }
  }

  const refreshBtn = (
    <Button onClick={refresh} disabled={busy}>
      {busy ? "Refreshing…" : "Refresh events"}
    </Button>
  );

  return (
    <main className="mx-auto max-w-3xl p-6">
      <PageHeader
        title="Events"
        subtitle="Upcoming ASU events matched to your interests and major."
        action={refreshBtn}
      />
      {!items ? (
        <Spinner />
      ) : items.length === 0 ? (
        <EmptyState
          title="No events yet"
          hint="Refresh to pull upcoming ASU events and rank them against your profile."
          action={refreshBtn}
        />
      ) : (
        <ul className="space-y-4">
          {items.map((rec) => <EventCard key={rec.id} rec={rec} />)}
        </ul>
      )}
    </main>
  );
}
