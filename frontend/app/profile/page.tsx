"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CourseStatus, MajorMapCourse, Profile } from "@/lib/types";
import MajorMapEditor from "@/components/MajorMapEditor";

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

  if (!profile) return <main className="p-6 text-sm text-gray-500">Loading…</main>;

  return (
    <main className="mx-auto max-w-2xl space-y-8 p-6">
      <section>
        <h1 className="text-xl font-semibold">{profile.full_name ?? profile.email}</h1>
        <p className="text-sm text-gray-500">
          {profile.major_name} · {profile.academic_year}
        </p>
      </section>
      <form onSubmit={save} className="space-y-3">
        <label className="block text-sm">
          Interests
          <input value={interests} onChange={(e) => setInterests(e.target.value)}
            className="mt-1 w-full rounded-md border px-3 py-2 text-sm" />
        </label>
        <label className="block text-sm">
          Clubs
          <input value={clubs} onChange={(e) => setClubs(e.target.value)}
            className="mt-1 w-full rounded-md border px-3 py-2 text-sm" />
        </label>
        <label className="block text-sm">
          Goals
          <textarea value={goals} onChange={(e) => setGoals(e.target.value)} rows={2}
            className="mt-1 w-full rounded-md border px-3 py-2 text-sm" />
        </label>
        <button type="submit" className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white">
          {saved ? "Saved ✓" : "Save"}
        </button>
      </form>
      <section>
        <h2 className="mb-3 text-lg font-semibold">Major map</h2>
        <MajorMapEditor courses={courses} onToggle={toggle} />
      </section>
    </main>
  );
}
