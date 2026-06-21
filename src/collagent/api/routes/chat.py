import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel

from collagent import db
from collagent.api.auth import get_current_user_id
from collagent.graph import create_graph, stream_events
from collagent.dashboard_tools import make_dashboard_tools
from collagent.event_tools import make_event_tools
from collagent.memory_tools import make_memory_tools
from collagent.people_tools import make_people_tools
from collagent.profile_tools import make_profile_tools
from collagent.prompts import build_system_prompt

router = APIRouter(prefix="/api/chat", tags=["chat"])

# In-process conversation memory. PoC tradeoff: history is lost on restart and
# does not scale past one process — swap for a Postgres checkpointer post-PoC.
_CHECKPOINTER = MemorySaver()


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"


def sse_format(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


# Plain `def`: graph streaming is sync; FastAPI threadpools it.
@router.post("")
def chat(req: ChatRequest, user_id: str = Depends(get_current_user_id)):
    profile = db.get_profile(user_id)
    courses = db.get_major_map_courses(user_id)
    memories = db.get_memories(user_id)
    agent = create_graph(
        checkpointer=_CHECKPOINTER,
        system_prompt=build_system_prompt(profile, courses, memories),
        extra_tools=(
            tuple(make_profile_tools(user_id))
            + tuple(make_event_tools(user_id))
            + tuple(make_people_tools(user_id))
            + tuple(make_memory_tools(user_id))
            + tuple(make_dashboard_tools(user_id))
        ),
    )
    config = {"configurable": {"thread_id": f"{user_id}:{req.thread_id}"}}

    def gen():
        try:
            for event in stream_events(agent, req.message, config):
                yield sse_format(event)
        except Exception as exc:  # headers already sent; surface the error in-stream
            yield sse_format({"type": "error", "detail": str(exc)})
        yield sse_format({"type": "done"})

    return StreamingResponse(gen(), media_type="text/event-stream")
