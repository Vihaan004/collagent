from collagent.models import MajorMapCourse, Memory, Profile

_BASE = """You are Collagent, a proactive personal assistant and advisor for an ASU student.
You work for the student: be concrete, helpful, and grounded in their actual context below.
When the student tells you something new about themselves (interests, clubs, goals, course
progress), persist it using your profile tools — never just acknowledge it.
When the student shares a durable preference, goal, or detail worth recalling in future
conversations, save it with your memory tools (remember / update_memory / forget). Use
list_memories to review or correct what you've stored. Don't store transient chit-chat.
"""


def _format_major_map(courses: list[MajorMapCourse]) -> str:
    if not courses:
        return "Major map: not set up yet."
    taken = sum(1 for c in courses if c.status == "taken")
    in_progress = sum(1 for c in courses if c.status == "in_progress")
    remaining = [c for c in courses if c.status == "remaining"]
    lines = [
        f"Major map progress: {taken} taken, {in_progress} in progress, {len(remaining)} remaining."
    ]
    if remaining:
        sample = ", ".join(
            f"{c.course_code or c.title}" for c in remaining[:15]
        )
        lines.append(f"Remaining requirements include: {sample}")
    return "\n".join(lines)


def _format_memories(memories: list[Memory] | None) -> str:
    if not memories:
        return ""
    lines = ["", "What you remember about this student (from past conversations):"]
    lines.extend(f"- {m.content}" for m in memories)
    return "\n".join(lines)


def build_system_prompt(
    profile: Profile | None,
    courses: list[MajorMapCourse],
    memories: list[Memory] | None = None,
) -> str:
    mem_block = _format_memories(memories)
    if profile is None or (not profile.onboarded and not profile.major_name):
        return (
            _BASE
            + "\nThe student has not completed onboarding yet; encourage them to."
            + mem_block
        )

    parts = [_BASE, "Student context:"]
    if profile.full_name:
        parts.append(f"- Name: {profile.full_name}")
    if profile.major_name:
        parts.append(f"- Major: {profile.major_name}")
    if profile.academic_year:
        parts.append(f"- Year: {profile.academic_year}")
    if profile.interests:
        parts.append(f"- Interests: {', '.join(profile.interests)}")
    if profile.goals:
        parts.append(f"- Goals: {profile.goals}")
    if profile.clubs:
        parts.append(f"- Clubs: {', '.join(profile.clubs)}")
    if profile.projects:
        parts.append(f"- Projects: {profile.projects}")
    parts.append(_format_major_map(courses))
    return "\n".join(parts) + mem_block
