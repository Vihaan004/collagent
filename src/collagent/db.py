from functools import lru_cache

from supabase import Client, create_client

from collagent.config import settings
from collagent.models import CourseStatus, MajorMapCourse, Profile, ProfileUpdate


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
