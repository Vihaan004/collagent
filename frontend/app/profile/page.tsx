"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CourseStatus, MajorMapCourse, Profile } from "@/lib/types";
import MajorMapEditor from "@/components/MajorMapEditor";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { Spinner } from "@/components/ui/States";

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [courses, setCourses] = useState<MajorMapCourse[]>([]);
  const [interests, setInterests] = useState("");
  const [clubs, setClubs] = useState("");
  const [goals, setGoals] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.get("/api/profile").then((p: Profile) => {
      setProfile(p);
      setInterests(p.interests.join(", "));
      setClubs(p.clubs.join(", "));
      setGoals(p.goals ?? "");
    });
    api.get("/api/major-map").then(setCourses);
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

  async function toggle(id: string, status: CourseStatus) {
    setCourses((cs) => cs.map((c) => (c.id === id ? { ...c, status } : c)));
    await api.put("/api/major-map/statuses", { updates: [{ id, status }] });
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
        <h2 className="mb-3 font-display text-xl text-ink">Major map</h2>
        <MajorMapEditor courses={courses} onToggle={toggle} />
      </section>
    </main>
  );
}
