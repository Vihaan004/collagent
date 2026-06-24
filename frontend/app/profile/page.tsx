"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CurriculumView, Memory, Profile } from "@/lib/types";
import Markdown from "@/components/ui/Markdown";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { Spinner } from "@/components/ui/States";

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [interests, setInterests] = useState("");
  const [clubs, setClubs] = useState("");
  const [goals, setGoals] = useState("");
  const [saved, setSaved] = useState(false);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [curriculum, setCurriculum] = useState<CurriculumView | null>(null);
  const [curriculumLoading, setCurriculumLoading] = useState(true);

  useEffect(() => {
    api.get("/api/profile").then((p: Profile) => {
      setProfile(p);
      setInterests(p.interests.join(", "));
      setClubs(p.clubs.join(", "));
      setGoals(p.goals ?? "");
    });
    api.get("/api/memory").then(setMemories);
    api
      .get("/api/curriculum")
      .then(setCurriculum)
      .catch(() => setCurriculum(null))
      .finally(() => setCurriculumLoading(false));
  }, []);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    await api.put("/api/profile", {
      interests: interests.split(",").map((s) => s.trim()).filter(Boolean),
      clubs: clubs.split(",").map((s) => s.trim()).filter(Boolean),
      goals,
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  async function forget(id: string) {
    setMemories((ms) => ms.filter((m) => m.id !== id));
    await api.del(`/api/memory/${id}`);
  }

  if (!profile) return <main className="p-6"><Spinner /></main>;

  return (
    <main className="mx-auto max-w-2xl space-y-8 p-6">
      <header>
        <h1 className="font-display text-3xl leading-tight text-ink">
          {profile.full_name ?? profile.email}
        </h1>
        <p className="mt-1 text-sm text-muted">
          {profile.major_name} · {profile.academic_year}
        </p>
      </header>

      <Card>
        <form onSubmit={save} className="space-y-4">
          <Field label="Interests">
            <Input value={interests} onChange={(e) => setInterests(e.target.value)} />
          </Field>
          <Field label="Clubs">
            <Input value={clubs} onChange={(e) => setClubs(e.target.value)} />
          </Field>
          <Field label="Goals">
            <Textarea value={goals} onChange={(e) => setGoals(e.target.value)} rows={2} />
          </Field>
          <Button type="submit" variant={saved ? "accent" : "primary"}>
            {saved ? "Saved ✓" : "Save"}
          </Button>
        </form>
      </Card>

      <section>
        <h2 className="mb-3 font-display text-xl text-ink">Your curriculum</h2>
        {curriculumLoading ? (
          <Spinner />
        ) : curriculum?.markdown ? (
          <Card>
            <Markdown>{curriculum.markdown}</Markdown>
            {curriculum.checksheet_url && (
              <a
                href={curriculum.checksheet_url}
                target="_blank"
                rel="noreferrer"
                className="mt-4 inline-block text-xs text-muted underline hover:text-ink"
              >
                View official ASU checksheet
              </a>
            )}
          </Card>
        ) : (
          <p className="text-sm text-muted">
            No curriculum on file for your program yet.
          </p>
        )}
      </section>

      <section>
        <h2 className="mb-3 font-display text-xl text-ink">What Collagent remembers</h2>
        {memories.length === 0 ? (
          <p className="text-sm text-muted">
            Nothing yet. As you chat, Collagent will remember durable details about you here.
          </p>
        ) : (
          <ul className="space-y-2">
            {memories.map((m) => (
              <li
                key={m.id}
                className="flex items-start justify-between gap-3 rounded-lg border border-line bg-surface px-4 py-2.5"
              >
                <span className="text-sm text-ink">{m.content}</span>
                <button
                  onClick={() => forget(m.id)}
                  className="shrink-0 text-xs font-medium text-muted hover:text-orange"
                >
                  Forget
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
