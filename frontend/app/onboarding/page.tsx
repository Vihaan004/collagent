"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { CourseStatus, MajorMapCourse, ProgramHit } from "@/lib/types";
import MajorMapEditor from "@/components/MajorMapEditor";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { Field, Input, Textarea, Select } from "@/components/ui/Field";

const YEARS = ["freshman", "sophomore", "junior", "senior", "graduate"];

// Major-map extraction (Playwright/Chromium on the backend) can be disabled on
// RAM-light demo hosts. When off, onboarding finishes after "About you".
const MAJOR_MAP_ENABLED = process.env.NEXT_PUBLIC_MAJOR_MAP_ENABLED !== "false";
const STEPS = MAJOR_MAP_ENABLED
  ? ["About you", "Major map", "Your courses"]
  : ["About you"];

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
    if (!MAJOR_MAP_ENABLED) {
      await finish(); // map extraction disabled on this host: complete onboarding now
      return;
    }
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
    try {
      const updates = courses
        .filter((c) => c.status !== "remaining")
        .map((c) => ({ id: c.id, status: c.status }));
      if (updates.length) await api.put("/api/major-map/statuses", { updates });
      await api.put("/api/profile", { onboarded: true });
      router.push("/");
    } catch {
      setError("Couldn't save your setup — check that the backend is running and try again.");
    }
  }

  return (
    <main className="mx-auto max-w-2xl space-y-6 p-6">
      <header className="pt-2 text-center">
        <h1 className="font-display text-3xl text-naval">collagent</h1>
        <p className="mt-1 text-sm text-muted">Let&apos;s set up your personal interface to ASU.</p>
      </header>

      <Stepper current={step} />

      {error && (
        <p className="rounded-lg border border-orange/40 bg-orange/5 p-3 text-sm text-orange-700">
          {error}
        </p>
      )}

      {step === 1 && (
        <Card>
          <form onSubmit={saveBasics} className="space-y-4">
            <Field label="Full name">
              <Input value={fullName} onChange={(e) => setFullName(e.target.value)} required
                placeholder="Your name" />
            </Field>
            <Field label="Academic year">
              <Select value={year} onChange={(e) => setYear(e.target.value)}>
                {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
              </Select>
            </Field>
            <div className="relative">
              <Field label="Major">
                <Input
                  value={program ? program.name : query}
                  onChange={(e) => { setProgram(null); setQuery(e.target.value); }}
                  required placeholder="Search your major (e.g. Computer Science)"
                />
              </Field>
              {!program && hits.length > 0 && (
                <ul className="absolute z-10 mt-1 w-full overflow-hidden rounded-lg border border-line bg-surface shadow-sm">
                  {hits.map((h) => (
                    <li key={h.code}>
                      <button type="button" onClick={() => { setProgram(h); setHits([]); }}
                        className="w-full px-3 py-2 text-left text-sm text-ink hover:bg-cream-200">
                        {h.name}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <Field label="Interests">
              <Input value={interests} onChange={(e) => setInterests(e.target.value)}
                placeholder="Comma-separated (e.g. FPGAs, robotics)" />
            </Field>
            <Field label="Clubs (optional)">
              <Input value={clubs} onChange={(e) => setClubs(e.target.value)}
                placeholder="Comma-separated" />
            </Field>
            <Field label="Goals">
              <Textarea value={goals} onChange={(e) => setGoals(e.target.value)} rows={3}
                placeholder="What are you aiming for? (e.g. research, internships, grad school)" />
            </Field>
            <Button type="submit">Continue</Button>
          </form>
        </Card>
      )}

      {step === 2 && (
        <Card className="space-y-4">
          <p className="text-sm leading-relaxed text-ink">
            Collagent will now read ASU&apos;s official major map for{" "}
            <span className="font-medium text-naval">{program?.name}</span> and build your personal
            degree map. Takes about a minute.
          </p>
          <div className="flex items-center gap-3">
            <Button onClick={generateMap} disabled={generating}>
              {generating ? "Building your major map…" : "Build my major map"}
            </Button>
            <button onClick={finish} className="text-sm text-muted underline hover:text-ink">
              Skip for now
            </button>
          </div>
        </Card>
      )}

      {step === 3 && (
        <Card className="space-y-4">
          <p className="text-sm leading-relaxed text-ink">
            Here&apos;s your major map. Mark what you&apos;ve already taken or are taking now.
          </p>
          <MajorMapEditor courses={courses} onToggle={toggleStatus} />
          <Button onClick={finish}>Finish setup</Button>
        </Card>
      )}
    </main>
  );
}

function Stepper({ current }: { current: number }) {
  return (
    <div className="flex items-center gap-2">
      {STEPS.map((label, i) => {
        const n = i + 1;
        const active = n === current;
        const done = n < current;
        return (
          <div key={label} className="flex flex-1 items-center gap-2">
            <span
              className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-medium ${
                done ? "bg-naval text-paper" : active ? "bg-orange text-paper" : "bg-cream text-muted"
              }`}
            >
              {done ? "✓" : n}
            </span>
            <span className={`text-xs ${active ? "font-medium text-ink" : "text-muted"}`}>
              {label}
            </span>
            {n < STEPS.length && <span className="h-px flex-1 bg-line" />}
          </div>
        );
      })}
    </div>
  );
}
