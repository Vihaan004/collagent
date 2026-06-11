"""Per-user tool factory: the agent edits the profile only through these typed tools."""
from langchain.tools import tool

from collagent import db
from collagent.models import AcademicYear, CourseStatus, ProfileUpdate


def make_profile_tools(user_id: str) -> list:
    @tool("update_profile")
    def update_profile(
        full_name: str | None = None,
        major_name: str | None = None,
        academic_year: AcademicYear | None = None,
        interests: list[str] | None = None,
        goals: str | None = None,
        clubs: list[str] | None = None,
        projects: str | None = None,
    ) -> str:
        """Update the student's profile. Only pass fields the student explicitly
        stated or confirmed. interests/clubs REPLACE the stored list, so include
        existing values plus the new ones when adding."""
        fields = {
            k: v
            for k, v in dict(
                full_name=full_name, major_name=major_name, academic_year=academic_year,
                interests=interests, goals=goals, clubs=clubs, projects=projects,
            ).items()
            if v is not None
        }
        if not fields:
            return "No fields provided; nothing updated."
        db.update_profile(user_id, ProfileUpdate(**fields))
        return f"Profile updated: {', '.join(fields)}."

    @tool("set_course_status")
    def set_course_status(course_code: str, status: CourseStatus) -> str:
        """Mark a major-map course as taken, in_progress, or remaining.
        course_code is the catalog code, e.g. 'CSE 110'."""
        courses = db.get_major_map_courses(user_id)
        normalized = " ".join(course_code.upper().split())
        match = next((c for c in courses if (c.course_code or "").upper() == normalized), None)
        if match is None:
            return f"Course '{course_code}' not found on the major map."
        db.update_course_statuses(user_id, [(match.id, status)])
        return f"{match.course_code} marked as {status}."

    return [update_profile, set_course_status]
