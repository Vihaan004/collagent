"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { CourseStatus, MajorMapCourse, ProgramHit } from "@/lib/types";
import MajorMapEditor from "@/components/MajorMapEditor";

const YEARS = ["freshman", "sophomore", "junior", "senior", "graduate"];

// 2025 major maps are CAS-walled; 2024 (the 2024-25 catalog) is the latest public year.
const CATALOG_YEAR = "2024";

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [error, setError] = useState<string | null>(null);

  // step 1 state
  const [fullName, setFullName] = useState("");
  const [year, setYear] = useState("freshman");
  const [interests, setInterests] = useState("");
  const [goals, setGoals] = useState("");
  const [clubs, setClubs] = useState("");
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<ProgramHit[]>([]);
  const [program, setProgram] = useState<ProgramHit | null>(null);

  // step 2/3 state
  const [generating, setGenerating] = useState(false);
  const [courses, setCourses] = useState<MajorMapCourse[]>([]);

  useEffect(() => {
    if (query.length < 2 || program) return;
    const t = setTimeout(() => {
      api.get(`/api/programs/search?q=${encodeURIComponent(query)}`).then(setHits).catch(() => {});
    }, 250);
    return () => clearTimeout(t);
  }, [query, program]);

  async function saveBasics(e: React.FormEvent) {
    e.preventDefault();
    if (!program) return setError("Pick your major from the search results.");
    setError(null);
    await api.put("/api/profile", {
      full_name: fullName,
      academic_year: year,
      major_name: program.name,
      acad_plan_code: program.code,
      catalog_year: CATALOG_YEAR,
      interests: interests.split(",").map((s) => s.trim()).filter(Boolean),
      goals,
      clubs: clubs.split(",").map((s) => s.trim()).filter(Boolean),
    });
    setStep(2);
  }

  async function generateMap() {
    if (!program) return;
    setGenerating(true);
    setError(null);
    try {
      const result = await api.post("/api/major-map/generate", {
        acad_plan_code: program.code,
        catalog_year: CATALOG_YEAR,
      });
      setCourses(result);
      setStep(3);
    } catch {
      setError("Couldn't build your major map automatically. You can retry or skip for now.");
    } finally {
      setGenerating(false);
    }
  }

  function toggleStatus(id: string, status: CourseStatus) {
    setCourses((cs) => cs.map((c) => (c.id === id ? { ...c, status } : c)));
  }

  async function finish() {
    const updates = courses
      .filter((c) => c.status !== "remaining")
      .map((c) => ({ id: c.id, status: c.status }));
    if (updates.length) await api.put("/api/major-map/statuses", { updates });
    await api.put("/api/profile", { onboarded: true });
    router.push("/");
  }

  return (
    <main className="mx-auto max-w-2xl space-y-6 p-6">
      <h1 className="text-2xl font-semibold">Set up Collagent</h1>
      <p className="text-sm text-gray-500">Step {step} of 3</p>
      {error && <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>}

      {step === 1 && (
        <form onSubmit={saveBasics} className="space-y-4">
          <input value={fullName} onChange={(e) => setFullName(e.target.value)} required
            placeholder="Full name" className="w-full rounded-md border px-3 py-2 text-sm" />
          <select value={year} onChange={(e) => setYear(e.target.value)}
            className="w-full rounded-md border px-3 py-2 text-sm">
            {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
          <div className="relative">
            <input
              value={program ? program.name : query}
              onChange={(e) => { setProgram(null); setQuery(e.target.value); }}
              required placeholder="Search your major (e.g. Computer Science)"
              className="w-full rounded-md border px-3 py-2 text-sm"
            />
            {!program && hits.length > 0 && (
              <ul className="absolute z-10 mt-1 w-full rounded-md border bg-white shadow">
                {hits.map((h) => (
                  <li key={h.code}>
                    <button type="button" onClick={() => { setProgram(h); setHits([]); }}
                      className="w-full px-3 py-2 text-left text-sm hover:bg-gray-50">
                      {h.name}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <input value={interests} onChange={(e) => setInterests(e.target.value)}
            placeholder="Interests, comma-separated (e.g. FPGAs, robotics)"
            className="w-full rounded-md border px-3 py-2 text-sm" />
          <input value={clubs} onChange={(e) => setClubs(e.target.value)}
            placeholder="Clubs you're in, comma-separated (optional)"
            className="w-full rounded-md border px-3 py-2 text-sm" />
          <textarea value={goals} onChange={(e) => setGoals(e.target.value)}
            placeholder="What are your goals? (e.g. research, internships, grad school)"
            className="w-full rounded-md border px-3 py-2 text-sm" rows={3} />
          <button type="submit" className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white">
            Continue
          </button>
        </form>
      )}

      {step === 2 && (
        <div className="space-y-4">
          <p className="text-sm">
            Collagent will now read ASU&apos;s official major map for{" "}
            <span className="font-medium">{program?.name}</span> and build your personal
            degree map. Takes about a minute.
          </p>
          <button onClick={generateMap} disabled={generating}
            className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
            {generating ? "Building your major map…" : "Build my major map"}
          </button>
          <button onClick={finish} className="ml-3 text-sm text-gray-500 underline">
            Skip for now
          </button>
        </div>
      )}

      {step === 3 && (
        <div className="space-y-4">
          <p className="text-sm">
            Here&apos;s your major map. Mark what you&apos;ve already taken or are taking now.
          </p>
          <MajorMapEditor courses={courses} onToggle={toggleStatus} />
          <button onClick={finish} className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white">
            Finish setup
          </button>
        </div>
      )}
    </main>
  );
}
