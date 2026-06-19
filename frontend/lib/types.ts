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

export interface EventRecommendation {
  id: string;
  event_id: string;
  title: string;
  description: string | null;
  starts_at: string | null;
  ends_at: string | null;
  location: string | null;
  url: string;
  why_note: string;
  rank: number;
}

export interface PersonRecommendation {
  id: string;
  person_id: string;
  name: string;
  title: string | null;
  departments: string[];
  expertise_areas: string[];
  email: string | null;
  profile_url: string;
  photo_url: string | null;
  research_interests: string | null;
  short_bio: string | null;
  why_note: string;
  rank: number;
}
