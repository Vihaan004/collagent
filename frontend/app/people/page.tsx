// frontend/app/people/page.tsx
"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { PersonRecommendation } from "@/lib/types";
import Button from "@/components/ui/Button";
import PersonCard from "@/components/PersonCard";
import PageHeader from "@/components/ui/PageHeader";
import { EmptyState, Spinner } from "@/components/ui/States";

export default function PeoplePage() {
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
          {recs.map((rec) => <PersonCard key={rec.id} rec={rec} />)}
        </ul>
      )}
    </main>
  );
}
