# src/collagent/curation/events.py
"""Per-student events curation: profile + candidate events -> ranked recs with why-notes.
A pure function with one structured-output LLM call (spec: 'pipeline, not agent')."""
from pydantic import BaseModel, Field

from collagent import db
from collagent.graph import get_model
from collagent.models import EventRecommendation, MajorMapCourse, Profile


class RankedEvent(BaseModel):
    event_id: str = Field(description="Exact event_id of a candidate, copied verbatim")
    why_note: str = Field(description="1-2 sentences on why THIS event fits the student")


class EventRanking(BaseModel):
    picks: list[RankedEvent] = Field(description="Top 5-10 events, best first")


_RANK_PROMPT = """You are an executive assistant curating ASU campus events for one student.
From the candidate events below, choose the 5-10 that best fit this student and rank them
best-first. For each pick, write a 1-2 sentence why_note grounded in the student's specific
interests, major, goals, clubs, or coursework — not generic praise.
Only choose from the candidates and copy each event_id exactly. Do not invent events."""


def _student_summary(profile: Profile | None, courses: list[MajorMapCourse]) -> str:
    if profile is None:
        return "No profile on file; recommend broadly appealing, high-signal events."
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
    return "\n".join(parts) or "Profile is sparse; recommend broadly relevant events."


def _candidate_block(candidates: list[dict]) -> str:
    blocks = []
    for e in candidates:
        about = (e.get("description") or "")[:300]
        blocks.append(
            f"event_id: {e['id']}\n"
            f"Title: {e.get('title') or '(untitled)'}\n"
            f"When: {e.get('starts_at') or 'TBD'}\n"
            f"Where: {e.get('location') or 'TBD'}\n"
            f"About: {about}"
        )
    return "\n\n".join(blocks)


def _rank(
    profile: Profile | None, courses: list[MajorMapCourse], candidates: list[dict]
) -> EventRanking:
    llm = get_model().with_structured_output(EventRanking)
    user = (
        f"STUDENT:\n{_student_summary(profile, courses)}\n\n"
        f"CANDIDATE EVENTS:\n{_candidate_block(candidates)}"
    )
    return llm.invoke([("system", _RANK_PROMPT), ("user", user)])


def curate_events(user_id: str) -> list[EventRecommendation]:
    profile = db.get_profile(user_id)
    courses = db.get_major_map_courses(user_id)
    events = db.get_upcoming_events(limit=40)
    if not events:
        return db.replace_event_recommendations(user_id, [])

    ranking = _rank(profile, courses, events)
    valid_ids = {e["id"] for e in events}
    rows: list[dict] = []
    seen: set[str] = set()
    for pick in ranking.picks:
        if pick.event_id in valid_ids and pick.event_id not in seen:
            rows.append(
                {"event_id": pick.event_id, "why_note": pick.why_note, "rank": len(rows)}
            )
            seen.add(pick.event_id)
    return db.replace_event_recommendations(user_id, rows)
