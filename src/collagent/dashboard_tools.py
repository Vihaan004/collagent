# src/collagent/dashboard_tools.py
"""The orchestrator's dashboard tools. One agent (chat + dashboard) uses these to
maintain "The Daily Brief": deterministic pipeline tools that re-run the existing
curation/ingestion sequences, read tools the agent uses to synthesize the Brief,
user-scoped CRUD over recommendations, and a tool that persists the snapshot.
Every tool is scoped to user_id (spec §5 guardrail). calendar_items stays read-only:
the agent may re-ingest (update_calendar) and read (get_deadlines) but not edit it."""
from langchain.tools import tool

from collagent import db
from collagent.asu.calendar import fetch_calendar
from collagent.asu.events import fetch_upcoming_events
from collagent.asu.news import fetch_news
from collagent.asu.people import fetch_faculty, query_terms
from collagent.curation.events import curate_events
from collagent.curation.people import curate_people


def make_dashboard_tools(user_id: str) -> list:
    # ---- deterministic pipeline tools (write to DB, return only a status) ----
    @tool("refresh_events")
    def refresh_events() -> str:
        """Re-ingest upcoming ASU events and regenerate this student's ranked event
        recommendations. Writes to the database (the dashboard's Events section reflects
        it). Returns a short status, not the data."""
        db.upsert_events(fetch_upcoming_events())
        recs = curate_events(user_id)
        return f"Events refreshed: {len(recs)} recommendations."

    @tool("refresh_people")
    def refresh_people() -> str:
        """Re-ingest ASU faculty/staff matched to this student and regenerate ranked
        people-to-contact recommendations. Writes to the database. Returns a short
        status, not the data."""
        profile = db.get_profile(user_id)
        db.upsert_people(fetch_faculty(query_terms(profile)))
        recs = curate_people(user_id)
        return f"People refreshed: {len(recs)} recommendations."

    @tool("refresh_news")
    def refresh_news() -> str:
        """Re-ingest open-web ASU news via web search and update the shared news cache.
        Returns a short status. No-ops if the news provider key is unset."""
        rows = fetch_news()
        if rows:
            db.upsert_news_items(rows)
        return f"News refreshed: {len(rows)} articles fetched."

    @tool("update_calendar")
    def update_calendar() -> str:
        """Re-ingest the current term's ASU academic calendar (deadlines, breaks,
        registration windows) from the registrar. Read-only afterward. Returns a short
        status."""
        rows = fetch_calendar()
        if rows:
            db.upsert_calendar_items(rows)
        return f"Calendar updated: {len(rows)} items."

    return [refresh_events, refresh_people, refresh_news, update_calendar]
