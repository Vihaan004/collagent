# tests/test_event_tools.py
from collagent import event_tools
from collagent.models import EventRecommendation

REC = EventRecommendation(
    id="r1", event_id="e1", title="Intro to FPGAs", url="u",
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


def test_get_event_recommendations_empty(monkeypatch):
    monkeypatch.setattr(event_tools.db, "get_event_recommendations", lambda uid: [])
    tools = {t.name: t for t in event_tools.make_event_tools("u1")}
    out = tools["get_event_recommendations"].invoke({})
    assert "no event recommendations" in out.lower()
