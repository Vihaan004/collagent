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
