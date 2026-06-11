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
