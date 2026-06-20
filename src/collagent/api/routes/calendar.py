from fastapi import APIRouter, Depends

from collagent import db
from collagent.api.auth import get_current_user_id
from collagent.asu.calendar import fetch_calendar
from collagent.models import CalendarItem

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("", response_model=list[CalendarItem])
def read_calendar(_user_id: str = Depends(get_current_user_id)):
    """Upcoming current-term academic-calendar items (shared, not per-user)."""
    return db.get_upcoming_calendar_items()


@router.post("/refresh", response_model=list[CalendarItem])
def refresh_calendar(_user_id: str = Depends(get_current_user_id)):
    """Re-ingest the current term from the ASU registrar, then return upcoming items."""
    rows = fetch_calendar()
    if rows:
        db.upsert_calendar_items(rows)
    return db.get_upcoming_calendar_items()
