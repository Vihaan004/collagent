from fastapi import APIRouter, Depends, HTTPException

from collagent import db
from collagent.api.auth import get_current_user_id
from collagent.models import Profile, ProfileUpdate

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=Profile)
def read_profile(user_id: str = Depends(get_current_user_id)):
    profile = db.get_profile(user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.put("", response_model=Profile)
def write_profile(update: ProfileUpdate, user_id: str = Depends(get_current_user_id)):
    return db.update_profile(user_id, update)
