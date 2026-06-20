from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from collagent.api.routes import (
    calendar,
    chat,
    events,
    majormap,
    memory,
    news,
    people,
    profile,
    programs,
)
from collagent.config import settings

app = FastAPI(title="collagent api")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(profile.router)
app.include_router(programs.router)
app.include_router(majormap.router)
app.include_router(chat.router)
app.include_router(events.router)
app.include_router(people.router)
app.include_router(memory.router)
app.include_router(calendar.router)
app.include_router(news.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
