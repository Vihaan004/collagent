export type CourseStatus = "taken" | "in_progress" | "remaining";

export interface Profile {
  id: string;
  email: string;
  full_name: string | null;
  major_name: string | null;
  acad_plan_code: string | null;
  catalog_year: string | null;
  academic_year: string | null;
  interests: string[];
  goals: string | null;
  clubs: string[];
  projects: string | null;
  onboarded: boolean;
}

export interface MajorMapCourse {
  id: string;
  term_number: number;
  course_code: string | null;
  title: string;
  credits: number | null;
  requirement_note: string | null;
  status: CourseStatus;
  sort_order: number;
}

export interface ProgramHit {
  code: string;
  slug: string;
  name: string;
}
