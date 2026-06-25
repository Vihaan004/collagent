from fastapi import APIRouter, Depends
from pydantic import BaseModel

from collagent import db
from collagent.api.auth import get_current_user_id
from collagent.asu.programs import get_checksheet_url

router = APIRouter(prefix="/api/curriculum", tags=["curriculum"])


class CurriculumLink(BaseModel):
    program_name: str | None
    checksheet_url: str | None


# The profile page only needs the official ASU checksheet link (from the program
# directory). The agent reads the full curriculum text via the read_curriculum
# tool, so this route deliberately does not fetch/render the checksheet.
@router.get("", response_model=CurriculumLink)
def read_curriculum_link(user_id: str = Depends(get_current_user_id)):
    profile = db.get_profile(user_id)
    code = profile.acad_plan_code if profile else None
    name = profile.major_name if profile else None
    url = get_checksheet_url(code) if code else None
    return CurriculumLink(program_name=name, checksheet_url=url)
