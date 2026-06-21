# src/collagent/api/routes/dashboard.py
from fastapi import APIRouter, Depends

from collagent import db
from collagent.api.auth import get_current_user_id
from collagent.models import DashboardView

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardView)
def read_dashboard(user_id: str = Depends(get_current_user_id)):
    """The last stored dashboard, aggregated for the Home feed: the agent-written Brief +
    tuned news (from the snapshot), plus top-5 events, top-5 people, and upcoming deadlines
    read live from their own tables. The agent maintains it via the chat SSE refresh."""
    snap = db.get_dashboard_snapshot(user_id)
    return DashboardView(
        brief_md=snap.brief_md if snap else "",
        generated_at=snap.generated_at if snap else None,
        news=snap.news if snap else [],
        events=db.get_event_recommendations(user_id)[:5],
        people=db.get_person_recommendations(user_id)[:5],
        deadlines=db.get_upcoming_calendar_items(),
    )
