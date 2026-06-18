from datetime import datetime, timezone
from functools import lru_cache

from supabase import Client, create_client

from collagent.config import settings
from collagent.models import (
    CourseStatus,
    EventRecommendation,
    MajorMapCourse,
    Profile,
    ProfileUpdate,
)


@lru_cache(maxsize=1)
def get_client() -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def get_profile(user_id: str) -> Profile | None:
    res = get_client().table("profiles").select("*").eq("id", user_id).execute()
    if not res.data:
        return None
    return Profile(**res.data[0])


def update_profile(user_id: str, update: ProfileUpdate) -> Profile:
    payload = update.model_dump(exclude_unset=True)
    res = get_client().table("profiles").update(payload).eq("id", user_id).execute()
    if not res.data:
        raise ValueError(f"Profile {user_id} not found during update")
    return Profile(**res.data[0])


def get_major_map_courses(user_id: str) -> list[MajorMapCourse]:
    res = (
        get_client().table("major_map_courses").select("*")
        .eq("user_id", user_id)
        .order("term_number").order("sort_order")
        .execute()
    )
    return [MajorMapCourse(**row) for row in res.data]


def replace_major_map_courses(user_id: str, courses: list[dict]) -> list[MajorMapCourse]:
    if not courses:
        raise ValueError("courses must not be empty; refusing to delete existing map")
    client = get_client()
    client.table("major_map_courses").delete().eq("user_id", user_id).execute()
    rows = [{**c, "user_id": user_id} for c in courses]
    res = client.table("major_map_courses").insert(rows).execute()
    return [MajorMapCourse(**row) for row in res.data]


def update_course_statuses(user_id: str, updates: list[tuple[str, CourseStatus]]) -> None:
    client = get_client()
    for course_id, status in updates:
        (
            client.table("major_map_courses").update({"status": status})
            .eq("id", course_id).eq("user_id", user_id)
            .execute()
        )


def upsert_events(rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    res = (
        get_client().table("events")
        .upsert(rows, on_conflict="source,source_event_key")
        .execute()
    )
    return res.data


def get_upcoming_events(limit: int = 40, since: str | None = None) -> list[dict]:
    since = since or datetime.now(timezone.utc).isoformat()
    res = (
        get_client().table("events").select("*")
        .gte("starts_at", since)
        .order("starts_at")
        .limit(limit)
        .execute()
    )
    return res.data


def _flatten_rec(row: dict) -> EventRecommendation:
    ev = row.get("events") or {}
    return EventRecommendation(
        id=row["id"],
        event_id=row["event_id"],
        why_note=row["why_note"],
        rank=row["rank"],
        title=ev.get("title", ""),
        description=ev.get("description"),
        starts_at=ev.get("starts_at"),
        ends_at=ev.get("ends_at"),
        location=ev.get("location"),
        url=ev.get("url", ""),
    )


def get_event_recommendations(user_id: str) -> list[EventRecommendation]:
    res = (
        get_client().table("event_recommendations")
        .select("id, event_id, why_note, rank, events(*)")
        .eq("user_id", user_id)
        .order("rank")
        .execute()
    )
    return [_flatten_rec(row) for row in res.data]


def replace_event_recommendations(
    user_id: str, rows: list[dict]
) -> list[EventRecommendation]:
    client = get_client()
    client.table("event_recommendations").delete().eq("user_id", user_id).execute()
    if rows:
        payload = [{**r, "user_id": user_id} for r in rows]
        client.table("event_recommendations").insert(payload).execute()
    return get_event_recommendations(user_id)
