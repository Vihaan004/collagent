// frontend/app/events/page.tsx
"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { EventRecommendation } from "@/lib/types";

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
    <main className="mx-auto w-full max-w-2xl p-4">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold">Events for you</h1>
        <button onClick={refresh} disabled={refreshing}
          className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
          {refreshing ? "Finding events…" : "Refresh"}
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
                  <a href={rec.url} target="_blank" rel="noopener noreferrer"
                    className="font-medium hover:underline">
                    {rec.title}
                  </a>
                  <p className="text-xs text-gray-500">
                    {formatWhen(rec.starts_at)}{rec.location ? ` · ${rec.location}` : ""}
                  </p>
                </div>
                <button onClick={() => discuss(rec)}
                  className="shrink-0 rounded-md border px-3 py-1 text-xs font-medium hover:bg-gray-50">
                  Discuss in chat
                </button>
              </div>
              <p className="mt-2 rounded bg-gray-50 px-3 py-2 text-sm text-gray-700">
                {rec.why_note}
              </p>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
