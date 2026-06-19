# src/collagent/people_tools.py
"""Per-user people tools: the chat agent reads the curated store (door B) and can run
a live ASU directory lookup, persisting found people into the shared index."""
from langchain.tools import tool

from collagent import db
from collagent.asu.people import search_faculty


def _render(*, name, title, departments, expertise_areas, email, profile_url, why_note=None) -> str:
    dept = f" · {', '.join(departments)}" if departments else ""
    lines = [f"- {name} — {title or 'TBD'}{dept}"]
    if expertise_areas:
        lines.append(f"  Expertise: {', '.join(expertise_areas)}")
    if why_note:
        lines.append(f"  Why recommended: {why_note}")
    if email:
        lines.append(f"  Email: {email}")
    lines.append(f"  Profile: {profile_url}")
    return "\n".join(lines)


def make_people_tools(user_id: str) -> list:
    @tool("get_person_recommendations")
    def get_person_recommendations() -> str:
        """Return this student's current curated people-to-contact recommendations
        (name, title, department, expertise, contact, and why each was recommended)."""
        recs = db.get_person_recommendations(user_id)
        if not recs:
            return (
                "No people recommendations yet. Suggest the student open the People "
                "page and click Refresh to generate them."
            )
        return "\n\n".join(
            _render(
                name=r.name, title=r.title, departments=r.departments,
                expertise_areas=r.expertise_areas, email=r.email,
                profile_url=r.profile_url, why_note=r.why_note,
            )
            for r in recs
        )

    @tool("search_people")
    def search_people(query: str) -> str:
        """Search the ASU directory live for faculty/staff by name or topic. Use for
        ad-hoc lookups not already in the student's saved recommendations. Pass ONLY
        the person's name OR a single topic keyword as `query` (e.g. 'Aman Arora',
        'robotics'). Do NOT pass a full sentence or question, and do NOT append 'ASU',
        the university name, or a guessed research topic to a person's name — the
        directory matches every word, so extra words make a real person return zero
        matches. To look someone up, search their name alone."""
        found = search_faculty(query)
        if not found:
            return f"No ASU directory matches found for '{query}'."
        db.upsert_people(found)
        return "\n\n".join(
            _render(
                name=p["name"], title=p.get("title"),
                departments=p.get("departments") or [],
                expertise_areas=p.get("expertise_areas") or [],
                email=p.get("email"), profile_url=p.get("profile_url", ""),
            )
            for p in found
        )

    return [get_person_recommendations, search_people]
