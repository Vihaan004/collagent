"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Profile, EventRecommendation, PersonRecommendation } from "@/lib/types";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/States";

export default function HomePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [events, setEvents] = useState<EventRecommendation[]>([]);
  const [people, setPeople] = useState<PersonRecommendation[]>([]);

  useEffect(() => {
    api.get("/api/profile")
      .then((p: Profile) => {
        if (!p.onboarded) {
          router.replace("/onboarding");
          return;
        }
        setProfile(p);
        api.get("/api/events").then(setEvents).catch(() => {});
        api.get("/api/people").then(setPeople).catch(() => {});
      })
      .catch(() => router.replace("/login"));
  }, [router]);

  if (!profile) return <main className="p-6"><Spinner /></main>;

  return (
    <main className="mx-auto max-w-3xl space-y-8 p-6">
      <header>
        <h1 className="font-display text-4xl leading-tight text-ink">
          Hey{profile.full_name ? `, ${profile.full_name.split(" ")[0]}` : ""}
        </h1>
        <p className="mt-2 text-sm text-muted">
          {profile.major_name ?? "No major set"}
          {profile.academic_year ? ` · ${profile.academic_year}` : ""}
          {profile.interests.length ? ` · ${profile.interests.join(", ")}` : ""}
        </p>
      </header>

      <div className="grid gap-5 sm:grid-cols-2">
        <PreviewColumn
          title="Events for you"
          href="/events"
          empty="No events yet — open Events and hit Refresh."
          items={events.slice(0, 3).map((e) => ({
            id: e.id,
            primary: e.title,
            secondary: e.location ?? "ASU",
          }))}
        />
        <PreviewColumn
          title="People to know"
          href="/people"
          empty="No people yet — open People and hit Refresh."
          items={people.slice(0, 3).map((p) => ({
            id: p.id,
            primary: p.name,
            secondary: p.title ?? "ASU",
            tag: p.expertise_areas[0],
          }))}
        />
      </div>
    </main>
  );
}

function PreviewColumn({
  title,
  href,
  empty,
  items,
}: {
  title: string;
  href: string;
  empty: string;
  items: { id: string; primary: string; secondary: string; tag?: string }[];
}) {
  return (
    <Card className="flex flex-col">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="font-display text-lg text-ink">{title}</h2>
        <Link href={href} className="text-xs font-medium text-naval hover:underline">
          View all →
        </Link>
      </div>
      {items.length === 0 ? (
        <p className="text-sm text-muted">{empty}</p>
      ) : (
        <ul className="space-y-3">
          {items.map((it) => (
            <li key={it.id} className="border-b border-line pb-3 last:border-0 last:pb-0">
              <Link href={href} className="block">
                <p className="truncate text-sm font-medium text-ink">{it.primary}</p>
                <p className="mt-0.5 flex items-center gap-2 truncate text-xs text-muted">
                  {it.secondary}
                  {it.tag && <Badge>{it.tag}</Badge>}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
