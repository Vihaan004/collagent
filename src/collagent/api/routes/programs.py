from fastapi import APIRouter, Depends, Query

from collagent.api.auth import get_current_user_id
from collagent.asu.programs import search_programs

router = APIRouter(prefix="/api/programs", tags=["programs"])


@router.get("/search")
def search(q: str = Query(min_length=2), user_id: str = Depends(get_current_user_id)):
    return search_programs(q)
