# src/collagent/curation/people.py
"""Per-student people curation: profile + candidate people -> ranked recs with why-notes.
A pure function with one structured-output LLM call (mirrors curation/events.py)."""
from pydantic import BaseModel, Field

from collagent import db
from collagent.curation.student import student_summary
from collagent.graph import get_model
from collagent.models import MajorMapCourse, PersonRecommendation, Profile


class RankedPerson(BaseModel):
    person_id: str = Field(description="Exact person_id of a candidate, copied verbatim")
    why_note: str = Field(description="1-2 sentences on why THIS person fits the student")


class PersonRanking(BaseModel):
    picks: list[RankedPerson] = Field(description="Top 5-10 people, best first")


_RANK_PROMPT = """You are an academic advisor helping one ASU student find faculty and
research mentors to reach out to. From the candidate people below, choose the 5-10 who
best fit this student's interests, major, goals, and coursework, and rank them best-first.
For each pick, write a 1-2 sentence why_note grounded in the person's expertise and the
student's specifics — not generic praise.
Only choose from the candidates and copy each person_id exactly. Do not invent people."""


def _candidate_block(candidates: list[dict]) -> str:
    blocks = []
    for p in candidates:
        expertise = ", ".join(p.get("expertise_areas") or []) or "(not listed)"
        depts = ", ".join(p.get("departments") or []) or "TBD"
        about = (p.get("research_interests") or p.get("short_bio") or "")[:300]
        blocks.append(
            f"person_id: {p['id']}\n"
            f"Name: {p.get('name') or '(unknown)'}\n"
            f"Title: {p.get('title') or 'TBD'}\n"
            f"Department: {depts}\n"
            f"Expertise: {expertise}\n"
            f"About: {about}"
        )
    return "\n\n".join(blocks)


def _rank(
    profile: Profile | None,
    courses: list[MajorMapCourse],
    candidates: list[dict],
    focus: list[str] | None = None,
) -> PersonRanking:
    llm = get_model().with_structured_output(PersonRanking)
    focus_block = (
        f"\n\nThe student is especially focused on {', '.join(focus)} right now; weight "
        f"these topics heavily in your picks and why-notes."
        if focus
        else ""
    )
    user = (
        f"STUDENT:\n{student_summary(profile, courses)}{focus_block}\n\n"
        f"CANDIDATE PEOPLE:\n{_candidate_block(candidates)}"
    )
    return llm.invoke([("system", _RANK_PROMPT), ("user", user)])


def curate_people(
    user_id: str, focus: list[str] | None = None
) -> list[PersonRecommendation]:
    profile = db.get_profile(user_id)
    courses = db.get_major_map_courses(user_id)
    people = db.get_people(limit=60)
    if not people:
        return db.replace_person_recommendations(user_id, [])

    ranking = _rank(profile, courses, people, focus)
    valid_ids = {p["id"] for p in people}
    rows: list[dict] = []
    seen: set[str] = set()
    for pick in ranking.picks:
        if pick.person_id in valid_ids and pick.person_id not in seen:
            rows.append(
                {"person_id": pick.person_id, "why_note": pick.why_note, "rank": len(rows)}
            )
            seen.add(pick.person_id)
    return db.replace_person_recommendations(user_id, rows)
