"use client";
import { useRouter } from "next/navigation";
import type { PersonRecommendation } from "@/lib/types";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[parts.length - 1]?.[0] ?? "")).toUpperCase();
}

export default function PersonCard({ rec }: { rec: PersonRecommendation }) {
  const router = useRouter();
  function discuss() {
    const role = rec.title ? `, ${rec.title}` : "";
    const ask = `Tell me about ${rec.name}${role} at ASU and how I might connect with them.`;
    router.push(`/chat?ask=${encodeURIComponent(ask)}`);
  }
  return (
    <Card as="li">
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
            <Button variant="secondary" onClick={discuss}
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
  );
}
