# src/collagent/event_tools.py
"""Per-user tool: the chat agent reads the same curated event store the surface renders."""
from langchain.tools import tool

from collagent import db


def make_event_tools(user_id: str) -> list:
    @tool("get_event_recommendations")
    def get_event_recommendations() -> str:
        """Return this student's current curated event recommendations
        (title, date, location, and why each was recommended)."""
        recs = db.get_event_recommendations(user_id)
        if not recs:
            return (
                "No event recommendations yet. Suggest the student open the Events "
                "page and click Refresh to generate them."
            )
        lines = []
        for r in recs:
            when = r.starts_at or "TBD"
            where = f", {r.location}" if r.location else ""
            lines.append(f"- {r.title} ({when}{where}): {r.why_note}")
        return "\n".join(lines)

    return [get_event_recommendations]
