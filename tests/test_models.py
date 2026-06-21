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


def test_event_recommendation_defaults_and_required():
    from collagent.models import EventRecommendation

    rec = EventRecommendation(
        id="r1", event_id="e1", title="Intro to FPGAs", url="https://x/event",
        why_note="Matches your FPGA interest.", rank=0,
    )
    assert rec.description is None and rec.location is None
    assert rec.starts_at is None and rec.rank == 0


def test_event_recommendation_ignores_extra_columns():
    from collagent.models import EventRecommendation

    rec = EventRecommendation(
        id="r1", event_id="e1", title="X", url="u", why_note="w", rank=1,
        created_at="2026-06-12T00:00:00Z",
    )
    assert rec.id == "r1"


def test_person_recommendation_ignores_extra_fields():
    from collagent.models import PersonRecommendation

    rec = PersonRecommendation(
        id="r1", person_id="p1", name="Bing Si", title="Associate Professor",
        departments=["SCAI"], expertise_areas=["Machine Learning"],
        email="bing.si@asu.edu", profile_url="https://search.asu.edu/profile/123",
        why_note="Matches your ML interest.", rank=0, unexpected="x",
    )
    assert rec.name == "Bing Si"
    assert rec.expertise_areas == ["Machine Learning"]
    assert not hasattr(rec, "unexpected")


def test_memory_model_parses_row_and_defaults():
    from collagent.models import Memory
    m = Memory(id="m1", user_id="u1", content="Prefers FPGA research")
    assert m.kind == "fact"
    assert m.created_at is None
    # tolerates extra DB columns + populated timestamps
    full = Memory(id="m1", user_id="u1", content="x", kind="goal",
                  created_at="2026-06-20T00:00:00Z", updated_at="2026-06-20T00:00:00Z",
                  extra="ignored")
    assert full.kind == "goal" and full.updated_at == "2026-06-20T00:00:00Z"


def test_calendar_item_defaults_and_extra_ignored():
    from collagent.models import CalendarItem
    c = CalendarItem(id="c1", term="Summer 2026", session="A", title="Classes Begin",
                     date_start="2026-05-18")
    assert c.session == "A" and c.date_end is None and c.category is None
    full = CalendarItem(id="c1", term="Summer 2026", session="whole", title="X",
                        date_start="2026-05-18", date_end="2026-05-19", category="deadline",
                        fetched_at="2026-06-20T00:00:00Z", extra="ignored")
    assert full.category == "deadline" and full.date_end == "2026-05-19"


def test_news_item_defaults_and_extra_ignored():
    from collagent.models import NewsItem
    n = NewsItem(id="n1", title="ASU lands grant", url="https://asu.edu/x")
    assert n.source == "tavily" and n.summary is None and n.published_at is None
    full = NewsItem(id="n1", title="X", url="u", source="tavily", source_key="u",
                    summary="snippet", published_at="2026-06-17T00:00:00Z",
                    fetched_at="2026-06-20T00:00:00Z", extra="ignored")
    assert full.summary == "snippet"


def test_dashboard_snapshot_parses_and_ignores_extra():
    from collagent.models import DashboardSnapshot
    snap = DashboardSnapshot(
        brief_md="# Today",
        news=[{"id": "n1", "title": "T", "url": "https://x", "why_note": "w", "junk": "drop"}],
    )
    assert snap.brief_md == "# Today"
    assert snap.news[0].title == "T" and snap.news[0].why_note == "w"


def test_dashboard_view_defaults_empty():
    from collagent.models import DashboardView
    view = DashboardView()
    assert view.brief_md == "" and view.events == [] and view.deadlines == []
