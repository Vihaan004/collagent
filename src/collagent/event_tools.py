# src/collagent/event_tools.py
"""Per-user tool: the chat agent reads the same curated event store the surface renders."""
from langchain.tools import tool

from collagent import db
from collagent.asu.events import fetch_upcoming_events


def make_event_tools(user_id: str) -> list:
    @tool("get_event_recommendations")
    def get_event_recommendations() -> str:
        """Return this student's current curated event recommendations
        (title, date, location, description, link, and why each was recommended)."""
        recs = db.get_event_recommendations(user_id)
        if not recs:
            return (
                "No event recommendations yet. Suggest the student open the Events "
                "page and click Refresh to generate them."
            )
        blocks = []
        for r in recs:
            when = r.starts_at or "TBD"
            where = f", {r.location}" if r.location else ""
            lines = [f"- {r.title} ({when}{where})", f"  Why recommended: {r.why_note}"]
            if r.description:
                lines.append(f"  About: {r.description[:500]}")
            lines.append(f"  Link: {r.url}")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

    @tool("search_events")
    def search_events(query: str) -> str:
        """Search upcoming ASU events live by keyword (matches title, description, or
        location). Use for ad-hoc event lookups not in the student's saved recommendations."""
        q = query.lower().strip()
        matches = []
        for e in fetch_upcoming_events():
            haystack = " ".join(
                filter(None, [e.get("title"), e.get("description"), e.get("location")])
            ).lower()
            if q in haystack:
                matches.append(e)
            if len(matches) >= 8:
                break
        if not matches:
            return f"No upcoming events found matching '{query}'."
        blocks = []
        for e in matches:
            when = e.get("starts_at") or "TBD"
            where = f", {e['location']}" if e.get("location") else ""
            blocks.append(f"- {e['title']} ({when}{where})\n  Link: {e['url']}")
        return "\n\n".join(blocks)

    return [get_event_recommendations, search_events]
