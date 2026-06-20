from typing import Literal

from pydantic import BaseModel

CourseStatus = Literal["taken", "in_progress", "remaining"]
AcademicYear = Literal["freshman", "sophomore", "junior", "senior", "graduate"]


class Profile(BaseModel):
    model_config = {"extra": "ignore"}

    id: str
    email: str
    full_name: str | None = None
    major_name: str | None = None
    acad_plan_code: str | None = None
    catalog_year: str | None = None
    academic_year: AcademicYear | None = None
    interests: list[str] = []
    goals: str | None = None
    clubs: list[str] = []
    projects: str | None = None
    onboarded: bool = False


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    major_name: str | None = None
    acad_plan_code: str | None = None
    catalog_year: str | None = None
    academic_year: AcademicYear | None = None
    interests: list[str] | None = None
    goals: str | None = None
    clubs: list[str] | None = None
    projects: str | None = None
    onboarded: bool | None = None


class MajorMapCourse(BaseModel):
    model_config = {"extra": "ignore"}

    id: str
    user_id: str
    term_number: int
    course_code: str | None = None
    title: str
    credits: float | None = None
    requirement_note: str | None = None
    status: CourseStatus = "remaining"
    sort_order: int = 0


class EventRecommendation(BaseModel):
    """Flattened view of an event_recommendations row joined to its event."""

    model_config = {"extra": "ignore"}

    id: str            # recommendation row id
    event_id: str
    title: str
    description: str | None = None
    starts_at: str | None = None
    ends_at: str | None = None
    location: str | None = None
    url: str
    why_note: str
    rank: int


class PersonRecommendation(BaseModel):
    """Flattened view of a person_recommendations row joined to its person."""

    model_config = {"extra": "ignore"}

    id: str            # recommendation row id
    person_id: str
    name: str
    title: str | None = None
    departments: list[str] = []
    expertise_areas: list[str] = []
    email: str | None = None
    profile_url: str
    photo_url: str | None = None
    research_interests: str | None = None
    short_bio: str | None = None
    why_note: str
    rank: int


class Memory(BaseModel):
    """A durable, user-owned fact the chat agent curates. Mirrors a user_memories row."""

    model_config = {"extra": "ignore"}

    id: str
    user_id: str
    content: str
    kind: str = "fact"
    created_at: str | None = None
    updated_at: str | None = None


class CalendarItem(BaseModel):
    """A single academic-calendar entry for the current term. Mirrors a calendar_items row."""

    model_config = {"extra": "ignore"}

    id: str
    term: str
    session: str = "whole"
    title: str
    date_start: str | None = None
    date_end: str | None = None
    category: str | None = None
    fetched_at: str | None = None


class NewsItem(BaseModel):
    """A cached open-web news article (Tavily). Global, not per-user. Mirrors a news_items row."""

    model_config = {"extra": "ignore"}

    id: str
    source: str = "tavily"
    source_key: str | None = None
    title: str
    url: str
    summary: str | None = None
    published_at: str | None = None
    fetched_at: str | None = None
