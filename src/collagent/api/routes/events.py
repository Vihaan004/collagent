# src/collagent/api/routes/events.py
from fastapi import APIRouter, Depends

from collagent import db
from collagent.api.auth import get_current_user_id
from collagent.asu.events import fetch_upcoming_events
from collagent.curation.events import curate_events
from collagent.models import EventRecommendation

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", response_model=list[EventRecommendation])
def read_events(user_id: str = Depends(get_current_user_id)):
    return db.get_event_recommendations(user_id)


# Plain def: ingestion does sync httpx fan-out + an LLM call; FastAPI threadpools it.
@router.post("/refresh", response_model=list[EventRecommendation])
def refresh_events(user_id: str = Depends(get_current_user_id)):
    db.upsert_events(fetch_upcoming_events())
    return curate_events(user_id)
