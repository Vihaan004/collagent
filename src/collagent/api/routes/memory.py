from fastapi import APIRouter, Depends, Response

from collagent import db
from collagent.api.auth import get_current_user_id
from collagent.models import Memory

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("", response_model=list[Memory])
def list_memories(user_id: str = Depends(get_current_user_id)):
    return db.get_memories(user_id)


@router.delete("/{memory_id}", status_code=204)
def delete_memory(memory_id: str, user_id: str = Depends(get_current_user_id)):
    db.delete_memory(user_id, memory_id)
    return Response(status_code=204)
