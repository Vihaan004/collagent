"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { NewsItem } from "@/lib/types";
import NewsCard from "@/components/NewsCard";
import PageHeader from "@/components/ui/PageHeader";
import Button from "@/components/ui/Button";
import { Spinner, EmptyState } from "@/components/ui/States";

export default function NewsPage() {
  const [items, setItems] = useState<NewsItem[] | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/api/news").then(setItems).catch(() => setItems([]));
  }, []);

  async function refresh() {
    if (busy) return;
    setBusy(true);
    try {
      setItems(await api.post("/api/news/refresh", {}));
    } catch {
      // leave the current list in place; the button re-enables to retry
    } finally {
      setBusy(false);
    }
  }

  const refreshBtn = (
    <Button onClick={refresh} disabled={busy}>
      {busy ? "Fetching news…" : "Refresh news"}
    </Button>
  );

  return (
    <main className="mx-auto max-w-3xl p-6">
      <PageHeader
        title="ASU News"
        subtitle="Recent happenings from around ASU and the open web."
        action={refreshBtn}
      />
      {!items ? (
        <Spinner />
      ) : items.length === 0 ? (
        <EmptyState
          title="No news yet"
          hint="Refresh to pull the latest ASU stories from the open web."
          action={refreshBtn}
        />
      ) : (
        <ul className="space-y-4">
          {items.map((n) => <NewsCard key={n.id} item={n} />)}
        </ul>
      )}
    </main>
  );
}
