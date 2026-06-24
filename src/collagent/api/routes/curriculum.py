from fastapi import APIRouter, Depends
from pydantic import BaseModel

from collagent import db
from collagent.api.auth import get_current_user_id
from collagent.asu.checksheet import fetch_curriculum
from collagent.asu.programs import get_checksheet_url

router = APIRouter(prefix="/api/curriculum", tags=["curriculum"])


class CurriculumView(BaseModel):
    program_name: str | None
    checksheet_url: str | None
    markdown: str | None


@router.get("", response_model=CurriculumView)
def read_curriculum(user_id: str = Depends(get_current_user_id)):
    profile = db.get_profile(user_id)
    code = profile.acad_plan_code if profile else None
    name = profile.major_name if profile else None
    url = get_checksheet_url(code) if code else None
    markdown = None
    if url:
        try:
            markdown = fetch_curriculum(url)
        except Exception:
            markdown = None  # surface as empty state, never 500
    return CurriculumView(program_name=name, checksheet_url=url, markdown=markdown)
