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
        registration windows) from the registrar and update the stored calendar. Returns
        a short status. (The calendar can only be re-ingested, never hand-edited.)"""
        rows = fetch_calendar()
        if rows:
            db.upsert_calendar_items(rows)
        return f"Calendar updated: {len(rows)} items."

    # ---- read tools the agent uses to synthesize the Brief ----
    @tool("get_news")
    def get_news() -> str:
        """List recent ASU news from the shared cache, each with its id, title, summary,
        and link. Use the ids when calling save_dashboard_brief."""
        items = db.get_recent_news()
        if not items:
            return "No news cached yet. Run refresh_news first."
        return "\n\n".join(
            f"- [{n.id}] {n.title}\n  {(n.summary or '')[:200]}\n  Link: {n.url}"
            for n in items
        )

    @tool("get_deadlines")
    def get_deadlines() -> str:
        """List upcoming academic-calendar items for the current term (deadlines, breaks,
        registration windows). Read-only."""
        items = db.get_upcoming_calendar_items()
        if not items:
            return "No calendar items yet. Run update_calendar first."
        return "\n".join(
            f"- {c.date_start or 'TBD'}: {c.title}"
            + (f" ({c.category})" if c.category else "")
            for c in items
        )

    # ---- user-scoped CRUD over recommendations ----
    @tool("remove_event_recommendation")
    def remove_event_recommendation(recommendation_id: str) -> str:
        """Remove one event from this student's recommendations (e.g. they said they're
        not interested). Pass the recommendation id. Consider also remembering the
        preference with your memory tools."""
        db.delete_event_recommendation(user_id, recommendation_id)
        return f"Removed event recommendation {recommendation_id}."

    @tool("remove_person_recommendation")
    def remove_person_recommendation(recommendation_id: str) -> str:
        """Remove one person from this student's recommendations. Pass the recommendation
        id. Consider also remembering the preference with your memory tools."""
        db.delete_person_recommendation(user_id, recommendation_id)
        return f"Removed person recommendation {recommendation_id}."

    # ---- persist the synthesized Brief + tuned news subset ----
    @tool("save_dashboard_brief")
    def save_dashboard_brief(brief_md: str, news: list[dict]) -> str:
        """Persist this student's dashboard Brief and tuned news subset. `brief_md` is a
        concise markdown Brief (lightweight, informative, suggestive — surface any
        imminent deadline). `news` is a list of picks, each
        {"id": <a news id from get_news>, "why_note": <one line on why it matters to
        them>}; choose about 5. Ids are resolved server-side, so copy them exactly;
        unknown ids are ignored."""
        # Resolve against a wide window (a superset of what get_news shows) so every id
        # the agent could have picked resolves; titles/urls always come from the DB.
        by_id = {n.id: n for n in db.get_recent_news(limit=50)}
        picks: list[dict] = []
        for item in news:
            n = by_id.get(item.get("id"))
            if not n:
                continue
            picks.append({
                "id": n.id,
                "title": n.title,
                "url": n.url,
                "summary": n.summary,
                "published_at": n.published_at,
                "why_note": item.get("why_note", ""),
            })
        db.upsert_dashboard_snapshot(user_id, brief_md, picks)
        return f"Saved dashboard brief with {len(picks)} news picks."

    return [
        refresh_events, refresh_people, refresh_news, update_calendar,
        get_news, get_deadlines,
        remove_event_recommendation, remove_person_recommendation,
        save_dashboard_brief,
    ]
