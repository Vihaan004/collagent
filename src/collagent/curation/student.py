# src/collagent/curation/student.py
"""Shared student-context summary used by curation pipelines."""
from collagent.models import MajorMapCourse, Profile


def student_summary(profile: Profile | None, courses: list[MajorMapCourse]) -> str:
    if profile is None:
        return "No profile on file; recommend broadly relevant, high-signal matches."
    parts: list[str] = []
    if profile.full_name:
        parts.append(f"Name: {profile.full_name}")
    if profile.major_name:
        parts.append(f"Major: {profile.major_name}")
    if profile.academic_year:
        parts.append(f"Year: {profile.academic_year}")
    if profile.interests:
        parts.append(f"Interests: {', '.join(profile.interests)}")
    if profile.goals:
        parts.append(f"Goals: {profile.goals}")
    if profile.clubs:
        parts.append(f"Clubs: {', '.join(profile.clubs)}")
    if profile.projects:
        parts.append(f"Projects: {profile.projects}")
    if courses:
        taken = sum(1 for c in courses if c.status == "taken")
        parts.append(f"Major-map progress: {taken} of {len(courses)} courses taken")
    return "\n".join(parts) or "Profile is sparse; recommend broadly relevant matches."
