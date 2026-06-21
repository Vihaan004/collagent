from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from collagent import db
from collagent.api.auth import get_current_user_id
from collagent.asu.majormap import build_major_map
from collagent.config import settings
from collagent.models import CourseStatus, MajorMapCourse

router = APIRouter(prefix="/api/major-map", tags=["major-map"])


class GenerateRequest(BaseModel):
    acad_plan_code: str
    catalog_year: str


class StatusUpdate(BaseModel):
    id: str
    status: CourseStatus


class StatusUpdateRequest(BaseModel):
    updates: list[StatusUpdate]


@router.get("", response_model=list[MajorMapCourse])
def read_major_map(user_id: str = Depends(get_current_user_id)):
    return db.get_major_map_courses(user_id)


# Plain `def` on purpose: build_major_map runs sync Playwright; FastAPI threadpools it.
@router.post("/generate", response_model=list[MajorMapCourse])
def generate(req: GenerateRequest, user_id: str = Depends(get_current_user_id)):
    if not settings.major_map_enabled:
        # Feature disabled on this host: never launch Chromium. Onboarding skips this step.
        raise HTTPException(status_code=503, detail="Major-map extraction is disabled.")
    extracted = build_major_map(req.acad_plan_code, req.catalog_year)
    rows = [
        {
            "term_number": c.term_number,
            "course_code": c.course_code,
            "title": c.title,
            "credits": c.credits,
            "requirement_note": c.requirement_note,
            "status": "remaining",
            "sort_order": i,
        }
        for i, c in enumerate(extracted.courses)
    ]
    return db.replace_major_map_courses(user_id, rows)


@router.put("/statuses")
def update_statuses(req: StatusUpdateRequest, user_id: str = Depends(get_current_user_id)):
    db.update_course_statuses(user_id, [(u.id, u.status) for u in req.updates])
    return {"ok": True}
