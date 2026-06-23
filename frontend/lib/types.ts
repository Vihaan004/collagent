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

export interface Memory {
  id: string;
  content: string;
  kind: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface CalendarItem {
  id: string;
  term: string;
  session: string;
  title: string;
  date_start: string | null;
  date_end: string | null;
  category: string | null;
  fetched_at: string | null;
}

export interface NewsItem {
  id: string;
  source: string;
  source_key: string | null;
  title: string;
  url: string;
  summary: string | null;
  published_at: string | null;
  fetched_at: string | null;
}

export interface DashboardNewsPick {
  id: string | null;
  title: string;
  url: string;
  summary: string | null;
  published_at: string | null;
  why_note: string | null;
}

export interface DashboardView {
  brief_md: string;
  generated_at: string | null;
  news: DashboardNewsPick[];
  events: EventRecommendation[];
  people: PersonRecommendation[];
  deadlines: CalendarItem[];
}
