"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { PersonRecommendation } from "@/lib/types";
import PersonCard from "@/components/PersonCard";
import PageHeader from "@/components/ui/PageHeader";
import Button from "@/components/ui/Button";
import { Spinner, EmptyState } from "@/components/ui/States";

export default function PeoplePage() {
  const [items, setItems] = useState<PersonRecommendation[] | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/api/people").then(setItems).catch(() => setItems([]));
  }, []);

  async function refresh() {
    if (busy) return;
    setBusy(true);
    try {
      setItems(await api.post("/api/people/refresh", {}));
    } catch {
      // leave the current list in place; the button re-enables to retry
    } finally {
      setBusy(false);
    }
  }

  const refreshBtn = (
    <Button onClick={refresh} disabled={busy}>
      {busy ? "Finding people…" : "Refresh people"}
    </Button>
  );

  return (
    <main className="mx-auto max-w-3xl p-6">
      <PageHeader
        title="People"
        subtitle="ASU faculty and staff worth reaching out to, ranked for you."
        action={refreshBtn}
      />
      {!items ? (
        <Spinner />
      ) : items.length === 0 ? (
        <EmptyState
          title="No people yet"
          hint="Refresh and Collagent will search the ASU directory for people aligned with your work."
          action={refreshBtn}
        />
      ) : (
        <ul className="space-y-4">
          {items.map((rec) => <PersonCard key={rec.id} rec={rec} />)}
        </ul>
      )}
    </main>
  );
}
