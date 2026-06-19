# src/collagent/api/routes/people.py
from fastapi import APIRouter, Depends

from collagent import db
from collagent.api.auth import get_current_user_id
from collagent.asu.people import fetch_faculty, query_terms
from collagent.curation.people import curate_people
from collagent.models import PersonRecommendation

router = APIRouter(prefix="/api/people", tags=["people"])


@router.get("", response_model=list[PersonRecommendation])
def read_people(user_id: str = Depends(get_current_user_id)):
    return db.get_person_recommendations(user_id)


# Plain def: ingestion does sync httpx fan-out + an LLM call; FastAPI threadpools it.
@router.post("/refresh", response_model=list[PersonRecommendation])
def refresh_people(user_id: str = Depends(get_current_user_id)):
    profile = db.get_profile(user_id)
    db.upsert_people(fetch_faculty(query_terms(profile)))
    return curate_people(user_id)
