from fastapi import APIRouter, Depends

from collagent import db
from collagent.api.auth import get_current_user_id
from collagent.asu.news import fetch_news
from collagent.models import NewsItem

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("", response_model=list[NewsItem])
def read_news(_user_id: str = Depends(get_current_user_id)):
    """Recent cached ASU news (shared global cache, newest first)."""
    return db.get_recent_news()


@router.post("/refresh", response_model=list[NewsItem])
def refresh_news(_user_id: str = Depends(get_current_user_id)):
    """Re-ingest ASU news from Tavily, then return the recent cache. No-ops if the
    Tavily key is unset (returns whatever is already cached)."""
    rows = fetch_news()
    if rows:
        db.upsert_news_items(rows)
    return db.get_recent_news()
