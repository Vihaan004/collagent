"use client";
import Card from "@/components/ui/Card";
import Markdown from "@/components/ui/Markdown";

// One news item rendered for either surface. `summary` and `why_note` are markdown,
// so they go through <Markdown> — previously they were dropped into raw {text} and
// leaked **bold**/[]() syntax into the card.
export interface NewsCardItem {
  title: string;
  url: string;
  summary?: string | null;
  published_at?: string | null;
  why_note?: string | null;
}

function formatDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (isNaN(d.getTime())) return null;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function NewsCard({
  item,
  compact = false,
}: {
  item: NewsCardItem;
  compact?: boolean;
}) {
  const date = formatDate(item.published_at);

  // Compact: a tight borderless row for the dashboard News panel — headline, date,
  // and one trimmed line (the why-note if the agent tuned it, else the summary).
  if (compact) {
    const blurb = item.why_note || item.summary;
    return (
      <li className="group py-3 first:pt-0">
        <a href={item.url} target="_blank" rel="noopener noreferrer"
          className="font-medium leading-snug text-ink group-hover:text-naval group-hover:underline">
          {item.title}
        </a>
        {date && <p className="mt-0.5 text-xs text-muted">{date}</p>}
        {blurb && (
          <p className="mt-1 line-clamp-2 text-sm leading-snug text-ink/75">{blurb}</p>
        )}
      </li>
    );
  }

  return (
    <Card as="li" className="transition-colors hover:border-line-strong">
      <div className="flex items-baseline justify-between gap-3">
        <a href={item.url} target="_blank" rel="noopener noreferrer"
          className="font-medium text-ink hover:text-naval hover:underline">
          {item.title}
        </a>
        {date && <span className="shrink-0 text-xs text-muted">{date}</span>}
      </div>
      {item.summary && (
        <Markdown className="mt-1 text-sm text-muted">{item.summary}</Markdown>
      )}
      {item.why_note && (
        <Markdown className="mt-3 rounded-r-md border-l-[3px] border-orange bg-cream-200 px-3 py-2 text-sm leading-relaxed text-ink/90">
          {item.why_note}
        </Markdown>
      )}
    </Card>
  );
}
