// frontend/app/people/page.tsx
"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { PersonRecommendation } from "@/lib/types";

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
    <main className="mx-auto w-full max-w-2xl p-4">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold">People to connect with</h1>
        <button onClick={refresh} disabled={refreshing}
          className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
          {refreshing ? "Finding people…" : "Refresh"}
        </button>
      </div>

      {loading ? (
        <p className="pt-12 text-center text-sm text-gray-400">Loading…</p>
      ) : recs.length === 0 ? (
        <p className="pt-12 text-center text-sm text-gray-400">
          No recommendations yet — hit Refresh to generate them.
        </p>
      ) : (
        <ul className="space-y-3">
          {recs.map((rec) => (
            <li key={rec.id} className="rounded-lg border p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <a href={rec.profile_url} target="_blank" rel="noopener noreferrer"
                    className="font-medium hover:underline">
                    {rec.name}
                  </a>
                  <p className="text-xs text-gray-500">
                    {rec.title ?? "ASU"}{rec.departments.length ? ` · ${rec.departments.join(", ")}` : ""}
                  </p>
                  {rec.expertise_areas.length > 0 && (
                    <p className="mt-1 text-xs text-gray-500">
                      Expertise: {rec.expertise_areas.join(", ")}
                    </p>
                  )}
                </div>
                <button onClick={() => discuss(rec)}
                  className="shrink-0 rounded-md border px-3 py-1 text-xs font-medium hover:bg-gray-50">
                  Discuss in chat
                </button>
              </div>
              <p className="mt-2 rounded bg-gray-50 px-3 py-2 text-sm text-gray-700">
                {rec.why_note}
              </p>
              {rec.email && (
                <a href={`mailto:${rec.email}`}
                  className="mt-2 inline-block text-xs font-medium text-blue-600 hover:underline">
                  {rec.email}
                </a>
              )}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
