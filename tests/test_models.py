import pytest
from pydantic import ValidationError

from collagent.models import MajorMapCourse, Profile, ProfileUpdate


def test_profile_defaults():
    p = Profile(id="u1", email="a@asu.edu")
    assert p.interests == [] and p.clubs == [] and p.onboarded is False


def test_profile_ignores_extra_db_columns():
    p = Profile(id="u1", email="a@asu.edu", created_at="2026-01-01T00:00:00Z")
    assert p.id == "u1"


def test_course_status_validated():
    with pytest.raises(ValidationError):
        MajorMapCourse(id="c1", user_id="u1", term_number=1, title="X", status="done")


def test_profile_update_excludes_unset():
    u = ProfileUpdate(major_name="Computer Science")
    assert u.model_dump(exclude_unset=True) == {"major_name": "Computer Science"}
