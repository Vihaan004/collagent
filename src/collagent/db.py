from datetime import datetime, timezone
from functools import lru_cache

from supabase import Client, create_client

from collagent.config import settings
from collagent.models import (
    CalendarItem,
    CourseStatus,
    DashboardSnapshot,
    EventRecommendation,
    MajorMapCourse,
    Memory,
    NewsItem,
    PersonRecommendation,
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


def upsert_people(rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    res = (
        get_client().table("people")
        .upsert(rows, on_conflict="source,source_person_key")
        .execute()
    )
    return res.data


def get_people(limit: int = 60) -> list[dict]:
    res = (
        get_client().table("people").select("*")
        .order("fetched_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data


def _flatten_person_rec(row: dict) -> PersonRecommendation:
    p = row.get("people") or {}
    return PersonRecommendation(
        id=row["id"],
        person_id=row["person_id"],
        why_note=row["why_note"],
        rank=row["rank"],
        name=p.get("name", ""),
        title=p.get("title"),
        departments=p.get("departments") or [],
        expertise_areas=p.get("expertise_areas") or [],
        email=p.get("email"),
        profile_url=p.get("profile_url", ""),
        photo_url=p.get("photo_url"),
        research_interests=p.get("research_interests"),
        short_bio=p.get("short_bio"),
    )


def get_person_recommendations(user_id: str) -> list[PersonRecommendation]:
    res = (
        get_client().table("person_recommendations")
        .select("id, person_id, why_note, rank, people(*)")
        .eq("user_id", user_id)
        .order("rank")
        .execute()
    )
    return [_flatten_person_rec(row) for row in res.data]


def get_memories(user_id: str) -> list[Memory]:
    res = (
        get_client().table("user_memories").select("*")
        .eq("user_id", user_id)
        .order("created_at")
        .execute()
    )
    return [Memory(**row) for row in res.data]


def create_memory(user_id: str, content: str, kind: str = "fact") -> Memory:
    res = (
        get_client().table("user_memories")
        .insert({"user_id": user_id, "content": content, "kind": kind})
        .execute()
    )
    return Memory(**res.data[0])


def update_memory(user_id: str, memory_id: str, content: str) -> Memory:
    res = (
        get_client().table("user_memories")
        .update({"content": content, "updated_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", memory_id).eq("user_id", user_id)
        .execute()
    )
    if not res.data:
        raise ValueError(f"Memory {memory_id} not found for user")
    return Memory(**res.data[0])


def delete_memory(user_id: str, memory_id: str) -> None:
    (
        get_client().table("user_memories").delete()
        .eq("id", memory_id).eq("user_id", user_id)
        .execute()
    )


def upsert_calendar_items(rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    res = (
        get_client().table("calendar_items")
        .upsert(rows, on_conflict="term,session,title")
        .execute()
    )
    return res.data


def get_upcoming_calendar_items(
    since: str | None = None, limit: int = 50
) -> list[CalendarItem]:
    since = since or datetime.now(timezone.utc).date().isoformat()
    res = (
        get_client().table("calendar_items").select("*")
        .gte("date_start", since)
        .order("date_start")
        .limit(limit)
        .execute()
    )
    return [CalendarItem(**row) for row in res.data]


def upsert_news_items(rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    res = (
        get_client().table("news_items")
        .upsert(rows, on_conflict="source,source_key")
        .execute()
    )
    return res.data


def get_recent_news(limit: int = 12) -> list[NewsItem]:
    res = (
        get_client().table("news_items").select("*")
        .order("fetched_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [NewsItem(**row) for row in res.data]


def replace_person_recommendations(
    user_id: str, rows: list[dict]
) -> list[PersonRecommendation]:
    client = get_client()
    client.table("person_recommendations").delete().eq("user_id", user_id).execute()
    if rows:
        payload = [{**r, "user_id": user_id} for r in rows]
        client.table("person_recommendations").insert(payload).execute()
    return get_person_recommendations(user_id)


def get_dashboard_snapshot(user_id: str) -> DashboardSnapshot | None:
    res = (
        get_client().table("dashboard_snapshots").select("*")
        .eq("user_id", user_id)
        .execute()
    )
    if not res.data:
        return None
    return DashboardSnapshot(**res.data[0])


def upsert_dashboard_snapshot(
    user_id: str, brief_md: str, news: list[dict]
) -> DashboardSnapshot:
    res = (
        get_client().table("dashboard_snapshots")
        .upsert(
            {
                "user_id": user_id,
                "brief_md": brief_md,
                "news": news,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="user_id",
        )
        .execute()
    )
    return DashboardSnapshot(**res.data[0])


def delete_event_recommendation(user_id: str, recommendation_id: str) -> None:
    (
        get_client().table("event_recommendations").delete()
        .eq("id", recommendation_id).eq("user_id", user_id)
        .execute()
    )


def delete_person_recommendation(user_id: str, recommendation_id: str) -> None:
    (
        get_client().table("person_recommendations").delete()
        .eq("id", recommendation_id).eq("user_id", user_id)
        .execute()
    )
