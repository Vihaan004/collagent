"use client";
import { useRouter } from "next/navigation";
import type { EventRecommendation } from "@/lib/types";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";

function formatWhen(iso: string | null): string {
  if (!iso) return "Date TBD";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });
}

export default function EventCard({ rec }: { rec: EventRecommendation }) {
  const router = useRouter();
  function discuss() {
    const ask = `Tell me about the event: ${rec.title}`;
    router.push(`/chat?ask=${encodeURIComponent(ask)}`);
  }
  return (
    <Card as="li">
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
        <Button variant="secondary" onClick={discuss}
          className="shrink-0 px-3 py-1.5 text-xs">
          Discuss in chat
        </Button>
      </div>
      <p className="mt-3 rounded-r-md border-l-[3px] border-orange bg-cream-200 px-3 py-2 text-sm leading-relaxed text-ink/90">
        {rec.why_note}
      </p>
    </Card>
  );
}
