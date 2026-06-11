"use client";
import type { CourseStatus, MajorMapCourse } from "@/lib/types";

const NEXT_STATUS: Record<CourseStatus, CourseStatus> = {
  remaining: "taken",
  taken: "in_progress",
  in_progress: "remaining",
};

const STATUS_STYLE: Record<CourseStatus, string> = {
  taken: "bg-green-100 text-green-800 border-green-300",
  in_progress: "bg-amber-100 text-amber-800 border-amber-300",
  remaining: "bg-gray-50 text-gray-600 border-gray-200",
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
      <p className="text-sm text-gray-500">
        Click a course to cycle its status: remaining → taken → in progress.
      </p>
      {terms.map((term) => (
        <section key={term}>
          <h3 className="mb-2 text-sm font-semibold text-gray-700">Term {term}</h3>
          <ul className="grid gap-2 sm:grid-cols-2">
            {courses
              .filter((c) => c.term_number === term)
              .map((c) => (
                <li key={c.id}>
                  <button
                    onClick={() => onToggle(c.id, NEXT_STATUS[c.status])}
                    className={`w-full rounded-md border px-3 py-2 text-left text-sm ${STATUS_STYLE[c.status]}`}
                  >
                    <span className="font-medium">{c.course_code ?? "—"}</span> {c.title}
                    <span className="float-right text-xs">{c.status.replace("_", " ")}</span>
                  </button>
                </li>
              ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
