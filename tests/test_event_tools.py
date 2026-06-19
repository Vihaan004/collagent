# tests/test_event_tools.py
from collagent import event_tools
from collagent.models import EventRecommendation

REC = EventRecommendation(
    id="r1", event_id="e1", title="Intro to FPGAs", url="https://asuevents.asu.edu/e1",
    description="A hands-on workshop on FPGA design.",
    starts_at="2026-06-20T14:00:00-07:00", location="Tempe",
    why_note="Matches your FPGA interest.", rank=0,
)


def test_get_event_recommendations_renders_list(monkeypatch):
    monkeypatch.setattr(event_tools.db, "get_event_recommendations", lambda uid: [REC])
    tools = {t.name: t for t in event_tools.make_event_tools("u1")}
    out = tools["get_event_recommendations"].invoke({})
    assert "Intro to FPGAs" in out
    assert "Matches your FPGA interest." in out
    assert "Tempe" in out
    assert "A hands-on workshop on FPGA design." in out  # description included
    assert "https://asuevents.asu.edu/e1" in out  # link included


def test_get_event_recommendations_empty(monkeypatch):
    monkeypatch.setattr(event_tools.db, "get_event_recommendations", lambda uid: [])
    tools = {t.name: t for t in event_tools.make_event_tools("u1")}
    out = tools["get_event_recommendations"].invoke({})
    assert "no event recommendations" in out.lower()


SAMPLE_EVENTS = [
    {"title": "Robotics Workshop", "description": "Build a robot arm", "location": "Tempe",
     "starts_at": "2026-06-20T14:00:00-07:00", "url": "https://asuevents.asu.edu/e/robot"},
    {"title": "Yoga on the Lawn", "description": "Relax", "location": "Tempe",
     "starts_at": "2026-06-21T09:00:00-07:00", "url": "https://asuevents.asu.edu/e/yoga"},
]


def test_search_events_filters_by_keyword(monkeypatch):
    monkeypatch.setattr(event_tools, "fetch_upcoming_events", lambda: SAMPLE_EVENTS)
    tools = {t.name: t for t in event_tools.make_event_tools("u1")}
    out = tools["search_events"].invoke({"query": "robot"})
    assert "Robotics Workshop" in out
    assert "Yoga on the Lawn" not in out
    assert "https://asuevents.asu.edu/e/robot" in out


def test_search_events_no_matches(monkeypatch):
    monkeypatch.setattr(event_tools, "fetch_upcoming_events", lambda: SAMPLE_EVENTS)
    tools = {t.name: t for t in event_tools.make_event_tools("u1")}
    out = tools["search_events"].invoke({"query": "quantum"})
    assert "no upcoming events" in out.lower()
