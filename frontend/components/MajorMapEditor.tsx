"use client";
import type { CourseStatus, MajorMapCourse } from "@/lib/types";

const NEXT_STATUS: Record<CourseStatus, CourseStatus> = {
  remaining: "taken",
  taken: "in_progress",
  in_progress: "remaining",
};

// Status colors keyed to the warm palette: cream for untouched, naval for done,
// orange for in-progress.
const STATUS_STYLE: Record<CourseStatus, string> = {
  taken: "border-naval bg-naval/10 text-naval",
  in_progress: "border-orange bg-orange/10 text-orange-700",
  remaining: "border-line bg-surface text-muted hover:border-line-strong",
};

export default function MajorMapEditor({
  courses,
  onToggle,
}: {
  courses: MajorMapCourse[];
  onToggle: (id: string, status: CourseStatus) => void;
}) {
  const terms = [...new Set(courses.map((c) => c.term_number))].sort((a, b) => a - b);
  return (
    <div className="space-y-6">
      <p className="text-sm text-muted">
        Click a course to cycle its status: remaining → taken → in progress.
      </p>
      {terms.map((term) => (
        <section key={term}>
          <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-muted">
            Term {term}
          </h3>
          <ul className="grid gap-2 sm:grid-cols-2">
            {courses
              .filter((c) => c.term_number === term)
              .map((c) => (
                <li key={c.id}>
                  <button
                    onClick={() => onToggle(c.id, NEXT_STATUS[c.status])}
                    className={`w-full rounded-lg border px-3 py-2 text-left text-sm transition-colors ${STATUS_STYLE[c.status]}`}
                  >
                    <span className="font-medium">{c.course_code ?? "—"}</span> {c.title}
                    <span className="float-right text-xs capitalize">{c.status.replace("_", " ")}</span>
                  </button>
                </li>
              ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
