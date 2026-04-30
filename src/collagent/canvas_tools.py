import os
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

import httpx
from langchain.tools import tool


DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_PER_PAGE = 100


def _get_canvas_config() -> tuple[str, str] | None:
    api_url = os.getenv("CANVAS_API_URL")
    api_token = os.getenv("CANVAS_API_TOKEN")
    if not api_url or not api_token:
        return None
    return api_url.rstrip("/"), api_token


def _canvas_request(
    method: str,
    endpoint: str,
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
) -> tuple[bool, Any | str]:
    config = _get_canvas_config()
    if not config:
        return False, "Missing CANVAS_API_URL or CANVAS_API_TOKEN in environment."

    api_url, api_token = config
    if not endpoint.startswith("/"):
        endpoint = f"/{endpoint}"

    url = f"{api_url}{endpoint}"
    headers = {"Authorization": f"Bearer {api_token}"}

    try:
        response = httpx.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=data,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return False, f"Canvas request failed: {exc}"

    try:
        return True, response.json()
    except ValueError:
        return False, "Canvas response was not valid JSON."


def _canvas_get(endpoint: str, params: dict[str, Any] | None = None) -> tuple[bool, Any | str]:
    return _canvas_request("GET", endpoint, params=params)


def _canvas_post(endpoint: str, data: dict[str, Any]) -> tuple[bool, Any | str]:
    return _canvas_request("POST", endpoint, data=data)


def _parse_link_header(link_header: str | None) -> dict[str, str]:
    if not link_header:
        return {}
    links: dict[str, str] = {}
    for part in link_header.split(","):
        section = part.strip().split(";")
        if len(section) < 2:
            continue
        url = section[0].strip().strip("<>")
        rel = None
        for item in section[1:]:
            item = item.strip()
            if item.startswith("rel="):
                rel = item.split("=", 1)[1].strip("\"")
                break
        if rel and url:
            links[rel] = url
    return links


def _canvas_get_paginated(
    endpoint: str,
    params: dict[str, Any] | None = None,
) -> tuple[bool, list[Any] | str]:
    config = _get_canvas_config()
    if not config:
        return False, "Missing CANVAS_API_URL or CANVAS_API_TOKEN in environment."

    api_url, api_token = config
    if not endpoint.startswith("/"):
        endpoint = f"/{endpoint}"

    headers = {"Authorization": f"Bearer {api_token}"}
    collected: list[Any] = []
    url = f"{api_url}{endpoint}"
    next_params = params.copy() if params else {}
    if "per_page" not in next_params:
        next_params["per_page"] = DEFAULT_PER_PAGE

    while url:
        try:
            response = httpx.get(
                url,
                headers=headers,
                params=next_params,
                timeout=DEFAULT_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return False, f"Canvas request failed: {exc}"

        try:
            page_data = response.json()
        except ValueError:
            return False, "Canvas response was not valid JSON."

        if isinstance(page_data, list):
            collected.extend(page_data)
        else:
            return True, [page_data]

        links = _parse_link_header(response.headers.get("Link"))
        url = links.get("next")
        next_params = {}

    return True, collected


def _format_date(value: str | None) -> str:
    if not value:
        return "N/A"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return value


def _coerce_list(value: Any | None) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


@tool(
    "canvas_get_self",
    description="Fetches the current Canvas user profile using CANVAS_API_URL and CANVAS_API_TOKEN.",
)
def canvas_get_self() -> str:
    ok, data = _canvas_get("/users/self")
    if not ok:
        return str(data)

    if isinstance(data, dict):
        name = data.get("name")
        user_id = data.get("id")
        login_id = data.get("login_id")
        return f"id={user_id}, name={name}, login_id={login_id}"

    return str(data)


@tool("list_my_courses", description="Lists active courses for the current user.")
def list_my_courses() -> str:
    ok, data = _canvas_get_paginated(
        "/courses",
        params={"enrollment_state": "active", "per_page": DEFAULT_PER_PAGE},
    )
    if not ok:
        return str(data)

    courses = data if isinstance(data, list) else []
    if not courses:
        return "No active courses found."

    lines = ["Active Courses:"]
    for course in courses:
        if not isinstance(course, dict):
            continue
        lines.append(
            f"- {course.get('course_code', 'No code')}: {course.get('name', 'Unnamed course')} (id={course.get('id')})"
        )

    return "\n".join(lines)


@tool("get_course_overview", description="Gets basic course info and optional syllabus summary.")
def get_course_overview(course_id: int | str, include_syllabus: bool = False) -> str:
    ok, course = _canvas_get(f"/courses/{course_id}")
    if not ok:
        return str(course)

    if not isinstance(course, dict):
        return "Unexpected response for course data."

    lines = [
        f"Course: {course.get('name', 'Unnamed')} ({course.get('course_code', 'No code')})",
        f"Start: {_format_date(course.get('start_at'))}",
        f"End: {_format_date(course.get('end_at'))}",
        f"Time zone: {course.get('time_zone', 'N/A')}",
    ]

    if include_syllabus:
        ok, syllabus_course = _canvas_get(
            f"/courses/{course_id}", params={"include[]": "syllabus_body"}
        )
        if ok and isinstance(syllabus_course, dict):
            syllabus = syllabus_course.get("syllabus_body")
            if syllabus:
                lines.append("Syllabus: (HTML content available)")
            else:
                lines.append("Syllabus: None")
        else:
            lines.append("Syllabus: Error fetching syllabus")

    return "\n".join(lines)


@tool("list_course_assignments", description="Lists assignments for a course.")
def list_course_assignments(course_id: int | str) -> str:
    ok, data = _canvas_get_paginated(
        f"/courses/{course_id}/assignments",
        params={"per_page": DEFAULT_PER_PAGE, "include[]": ["submission"]},
    )
    if not ok:
        return str(data)

    assignments = data if isinstance(data, list) else []
    if not assignments:
        return f"No assignments found for course {course_id}."

    lines = [f"Assignments for course {course_id}:"]
    for assignment in assignments:
        if not isinstance(assignment, dict):
            continue
        lines.append(
            f"- {assignment.get('name', 'Unnamed')} (id={assignment.get('id')}, due={assignment.get('due_at', 'N/A')})"
        )

    return "\n".join(lines)


@tool("get_assignment_details", description="Gets detailed assignment info for a course.")
def get_assignment_details(course_id: int | str, assignment_id: int | str) -> str:
    ok, data = _canvas_get(f"/courses/{course_id}/assignments/{assignment_id}")
    if not ok:
        return str(data)

    if not isinstance(data, dict):
        return "Unexpected response for assignment data."

    lines = [
        f"Name: {data.get('name', 'Unnamed')}",
        f"Due: {_format_date(data.get('due_at'))}",
        f"Points: {data.get('points_possible', 'N/A')}",
        f"Published: {data.get('published', False)}",
        f"Submission types: {', '.join(_coerce_list(data.get('submission_types')))}",
    ]
    return "\n".join(lines)


@tool("get_my_upcoming_assignments", description="Lists upcoming assignments across all courses.")
def get_my_upcoming_assignments(days: int = 7) -> str:
    end_date = datetime.now(timezone.utc) + timedelta(days=days)

    ok, data = _canvas_get_paginated(
        "/users/self/upcoming_events",
        params={"per_page": DEFAULT_PER_PAGE},
    )
    if not ok:
        return str(data)

    events = data if isinstance(data, list) else []
    assignments: list[dict[str, Any]] = []

    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("type") == "assignment" or event.get("assignment"):
            assignment_data = event.get("assignment", event)
            due_at = assignment_data.get("due_at")
            if due_at:
                try:
                    due_date = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if due_date <= end_date:
                    assignments.append(assignment_data)

    if not assignments:
        return f"No assignments due in the next {days} days."

    assignments.sort(key=lambda a: a.get("due_at", ""))

    lines = [f"Upcoming assignments (next {days} days):"]
    for assignment in assignments:
        lines.append(
            f"- {assignment.get('name', 'Unnamed')} (course_id={assignment.get('course_id')}, due={_format_date(assignment.get('due_at'))})"
        )

    return "\n".join(lines)


@tool("get_submission_status", description="Shows submitted vs missing assignments.")
def get_submission_status(course_id: int | str | None = None) -> str:
    if course_id:
        ok, data = _canvas_get_paginated(
            f"/courses/{course_id}/assignments",
            params={"per_page": DEFAULT_PER_PAGE, "include[]": ["submission"]},
        )
        if not ok:
            return str(data)
        assignments = data if isinstance(data, list) else []
        header = f"Submission status for course {course_id}:"
    else:
        ok, courses = _canvas_get_paginated(
            "/courses",
            params={"enrollment_state": "active", "per_page": DEFAULT_PER_PAGE},
        )
        if not ok:
            return str(courses)
        assignments = []
        for course in courses if isinstance(courses, list) else []:
            cid = course.get("id") if isinstance(course, dict) else None
            if not cid:
                continue
            ok, data = _canvas_get_paginated(
                f"/courses/{cid}/assignments",
                params={"per_page": DEFAULT_PER_PAGE, "include[]": ["submission"]},
            )
            if ok and isinstance(data, list):
                for assignment in data:
                    if isinstance(assignment, dict):
                        assignment["_course_id"] = cid
                        assignments.append(assignment)
        header = "Submission status (all courses):"

    submitted = []
    missing = []

    for assignment in assignments:
        if not isinstance(assignment, dict):
            continue
        submission = assignment.get("submission") or {}
        is_submitted = submission.get("submitted_at") is not None
        if is_submitted:
            submitted.append(assignment)
        else:
            missing.append(assignment)

    lines = [header]
    lines.append(f"Missing: {len(missing)}")
    lines.append(f"Submitted: {len(submitted)}")

    return "\n".join(lines)


@tool("get_my_course_grades", description="Fetches current grades across active courses.")
def get_my_course_grades() -> str:
    ok, courses = _canvas_get_paginated(
        "/courses",
        params={
            "enrollment_state": "active",
            "include[]": ["total_scores", "current_grading_period_scores"],
            "per_page": DEFAULT_PER_PAGE,
        },
    )
    if not ok:
        return str(courses)

    lines = ["Course grades:"]
    for course in courses if isinstance(courses, list) else []:
        if not isinstance(course, dict):
            continue
        enrollments = course.get("enrollments") or []
        if not enrollments:
            continue
        enrollment = enrollments[0]
        current_score = enrollment.get("computed_current_score")
        current_grade = enrollment.get("computed_current_grade", "N/A")
        lines.append(
            f"- {course.get('course_code', 'No code')}: {current_grade} ({current_score if current_score is not None else 'N/A'}%)"
        )

    return "\n".join(lines)


@tool("list_discussion_topics", description="Lists discussion topics for a course.")
def list_discussion_topics(course_id: int | str, include_announcements: bool = False) -> str:
    params: dict[str, Any] = {"per_page": DEFAULT_PER_PAGE}
    if include_announcements:
        params["include[]"] = ["announcement"]

    ok, data = _canvas_get_paginated(
        f"/courses/{course_id}/discussion_topics", params=params
    )
    if not ok:
        return str(data)

    topics = data if isinstance(data, list) else []
    if not topics:
        return f"No discussion topics found for course {course_id}."

    lines = [f"Discussion topics for course {course_id}:"]
    for topic in topics:
        if not isinstance(topic, dict):
            continue
        topic_type = "Announcement" if topic.get("is_announcement") else "Discussion"
        lines.append(
            f"- {topic.get('title', 'Untitled')} (id={topic.get('id')}, {topic_type})"
        )

    return "\n".join(lines)


@tool("get_discussion_topic_details", description="Gets details for a discussion topic.")
def get_discussion_topic_details(course_id: int | str, topic_id: int | str) -> str:
    ok, data = _canvas_get(
        f"/courses/{course_id}/discussion_topics/{topic_id}"
    )
    if not ok:
        return str(data)

    if not isinstance(data, dict):
        return "Unexpected response for discussion topic."

    lines = [
        f"Title: {data.get('title', 'Untitled')}",
        f"Author: {(data.get('author') or {}).get('display_name', 'Unknown')}",
        f"Posted: {_format_date(data.get('posted_at'))}",
        f"Replies: {data.get('discussion_entries_count', 0)}",
    ]
    return "\n".join(lines)


@tool("list_pages", description="Lists pages for a course.")
def list_pages(course_id: int | str) -> str:
    ok, data = _canvas_get_paginated(
        f"/courses/{course_id}/pages", params={"per_page": DEFAULT_PER_PAGE}
    )
    if not ok:
        return str(data)

    pages = data if isinstance(data, list) else []
    if not pages:
        return f"No pages found for course {course_id}."

    lines = [f"Pages for course {course_id}:"]
    for page in pages:
        if not isinstance(page, dict):
            continue
        status = "Published" if page.get("published") else "Unpublished"
        lines.append(
            f"- {page.get('title', 'Untitled')} (url={page.get('url', 'N/A')}, {status})"
        )

    return "\n".join(lines)


@tool("get_page_content", description="Gets the content of a page for a course.")
def get_page_content(course_id: int | str, page_url_or_id: str) -> str:
    ok, data = _canvas_get(f"/courses/{course_id}/pages/{page_url_or_id}")
    if not ok:
        return str(data)

    if not isinstance(data, dict):
        return "Unexpected response for page content."

    title = data.get("title", "Untitled")
    body = data.get("body", "") or ""
    if len(body) > 2000:
        body = body[:2000] + "..."

    return f"{title}\n\n{body}"


@tool("list_modules", description="Lists modules for a course.")
def list_modules(course_id: int | str) -> str:
    ok, data = _canvas_get_paginated(
        f"/courses/{course_id}/modules", params={"per_page": DEFAULT_PER_PAGE}
    )
    if not ok:
        return str(data)

    modules = data if isinstance(data, list) else []
    if not modules:
        return f"No modules found for course {course_id}."

    lines = [f"Modules for course {course_id}:"]
    for module in modules:
        if not isinstance(module, dict):
            continue
        lines.append(
            f"- {module.get('name', 'Untitled')} (id={module.get('id')})"
        )

    return "\n".join(lines)


@tool("get_module_items", description="Lists items in a course module.")
def get_module_items(course_id: int | str, module_id: int | str) -> str:
    ok, data = _canvas_get_paginated(
        f"/courses/{course_id}/modules/{module_id}/items",
        params={"per_page": DEFAULT_PER_PAGE},
    )
    if not ok:
        return str(data)

    items = data if isinstance(data, list) else []
    if not items:
        return f"No module items found for module {module_id}."

    lines = [f"Module items for module {module_id}:"]
    for item in items:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- {item.get('title', 'Untitled')} (type={item.get('type', 'N/A')})"
        )

    return "\n".join(lines)


@tool("list_course_files", description="Lists files for a course.")
def list_course_files(course_id: int | str) -> str:
    ok, data = _canvas_get_paginated(
        f"/courses/{course_id}/files", params={"per_page": DEFAULT_PER_PAGE}
    )
    if not ok:
        return str(data)

    files = data if isinstance(data, list) else []
    if not files:
        return f"No files found for course {course_id}."

    lines = [f"Files for course {course_id}:"]
    for file_item in files:
        if not isinstance(file_item, dict):
            continue
        lines.append(
            f"- {file_item.get('display_name', 'Unnamed')} (id={file_item.get('id')}, size={file_item.get('size', 'N/A')})"
        )

    return "\n".join(lines)


@tool("get_file_metadata", description="Gets metadata for a file by ID.")
def get_file_metadata(file_id: int | str) -> str:
    ok, data = _canvas_get(f"/files/{file_id}")
    if not ok:
        return str(data)

    if not isinstance(data, dict):
        return "Unexpected response for file metadata."

    lines = [
        f"Name: {data.get('display_name', 'Unnamed')}",
        f"Size: {data.get('size', 'N/A')}",
        f"Updated: {_format_date(data.get('updated_at'))}",
        f"Content type: {data.get('content-type', 'N/A')}",
        f"URL: {data.get('url', 'N/A')}",
    ]

    return "\n".join(lines)


@tool("list_upcoming_events", description="Lists upcoming calendar events.")
def list_upcoming_events(days: int = 7) -> str:
    ok, data = _canvas_get_paginated(
        "/users/self/upcoming_events",
        params={"per_page": DEFAULT_PER_PAGE},
    )
    if not ok:
        return str(data)

    events = data if isinstance(data, list) else []
    if not events:
        return f"No upcoming events in the next {days} days."

    cutoff = datetime.now(timezone.utc) + timedelta(days=days)
    lines = [f"Upcoming events (next {days} days):"]
    for event in events:
        if not isinstance(event, dict):
            continue
        start_at = event.get("start_at") or event.get("due_at")
        if start_at:
            try:
                start_dt = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
            except ValueError:
                continue
            if start_dt > cutoff:
                continue
        lines.append(
            f"- {event.get('title', 'Untitled')} (type={event.get('type', 'N/A')}, date={_format_date(start_at)})"
        )

    return "\n".join(lines)


@tool("list_conversations", description="Lists recent inbox conversations.")
def list_conversations(limit: int = 20) -> str:
    ok, data = _canvas_get_paginated(
        "/conversations",
        params={"per_page": min(limit, DEFAULT_PER_PAGE)},
    )
    if not ok:
        return str(data)

    conversations = data if isinstance(data, list) else []
    if not conversations:
        return "No conversations found."

    lines = ["Recent conversations:"]
    for convo in conversations[:limit]:
        if not isinstance(convo, dict):
            continue
        subject = convo.get("subject", "(no subject)")
        last_message = convo.get("last_message", "")
        lines.append(f"- {subject}: {last_message[:120]}")

    return "\n".join(lines)


@tool("send_message", description="Sends a Canvas inbox message to one or more recipients.")
def send_message(recipients: Iterable[int | str], subject: str, body: str) -> str:
    recipient_ids = [str(r) for r in recipients]
    payload = {
        "recipients[]": recipient_ids,
        "subject": subject,
        "body": body,
    }

    ok, data = _canvas_post("/conversations", payload)
    if not ok:
        return str(data)

    if not isinstance(data, dict):
        return "Message sent."

    return f"Message sent (id={data.get('id', 'N/A')})."


CANVAS_TOOLS = [
    canvas_get_self,
    list_my_courses,
    get_course_overview,
    list_course_assignments,
    get_assignment_details,
    get_my_upcoming_assignments,
    get_submission_status,
    get_my_course_grades,
    list_discussion_topics,
    get_discussion_topic_details,
    list_pages,
    get_page_content,
    list_modules,
    get_module_items,
    list_course_files,
    get_file_metadata,
    list_upcoming_events,
    list_conversations,
    # send_message,
]
