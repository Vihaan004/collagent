from collagent.models import MajorMapCourse, Profile
from collagent.prompts import build_system_prompt

PROFILE = Profile(
    id="u1", email="a@asu.edu", full_name="Vihaan", major_name="Computer Systems Engineering",
    academic_year="junior", interests=["FPGAs", "hardware acceleration"], goals="Work with FPGAs",
)
COURSES = [
    MajorMapCourse(id="c1", user_id="u1", term_number=1, course_code="CSE 110", title="Programming", status="taken"),
    MajorMapCourse(id="c2", user_id="u1", term_number=5, course_code="CSE 420", title="Computer Architecture", status="remaining"),
]


def test_prompt_includes_profile_facts():
    prompt = build_system_prompt(PROFILE, COURSES)
    assert "Vihaan" in prompt
    assert "Computer Systems Engineering" in prompt
    assert "FPGAs" in prompt
    assert "junior" in prompt


def test_prompt_summarizes_major_map():
    prompt = build_system_prompt(PROFILE, COURSES)
    assert "1 taken" in prompt and "1 remaining" in prompt
    assert "CSE 420" in prompt


def test_prompt_handles_empty_profile():
    prompt = build_system_prompt(Profile(id="u1", email="a@asu.edu"), [])
    assert "has not completed onboarding" in prompt


def test_prompt_includes_memories_when_present():
    from collagent.models import Memory
    mems = [Memory(id="m1", user_id="u1", content="Prefers FPGA research")]
    prompt = build_system_prompt(PROFILE, COURSES, mems)
    assert "Prefers FPGA research" in prompt


def test_prompt_memories_block_injected_for_empty_profile():
    from collagent.models import Memory
    mems = [Memory(id="m1", user_id="u1", content="Wants a research internship")]
    prompt = build_system_prompt(Profile(id="u1", email="a@asu.edu"), [], mems)
    assert "has not completed onboarding" in prompt  # base path preserved
    assert "Wants a research internship" in prompt    # memories still injected


def test_prompt_no_memory_block_when_none():
    prompt = build_system_prompt(PROFILE, COURSES)  # memories defaults to None
    assert "remember about this student" not in prompt


def test_prompt_includes_orchestrator_full_refresh_flow():
    # orchestrator guidance is present on every prompt (one agent serves both surfaces)
    out = build_system_prompt(None, [])
    low = out.lower()
    assert "dashboard" in low and "refresh" in low
    assert "save_dashboard_brief" in out  # names the persistence step
    # still present when the student is fully onboarded
    assert "save_dashboard_brief" in build_system_prompt(PROFILE, COURSES)
