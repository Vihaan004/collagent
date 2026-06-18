# tests/test_curation_events.py
from collagent.curation import events as curation
from collagent.curation.events import EventRanking, RankedEvent
from collagent.models import Profile


def test_curate_drops_hallucinated_ids_and_reranks(monkeypatch):
    profile = Profile(id="u1", email="a@asu.edu", interests=["FPGAs"])
    monkeypatch.setattr(curation.db, "get_profile", lambda uid: profile)
    monkeypatch.setattr(curation.db, "get_major_map_courses", lambda uid: [])
    monkeypatch.setattr(
        curation.db, "get_upcoming_events",
        lambda limit=40: [{"id": "e1", "title": "FPGA Talk"}, {"id": "e2", "title": "Yoga"}],
    )
    # LLM returns a hallucinated id ("e9") and a valid one; e9 must be dropped.
    monkeypatch.setattr(
        curation, "_rank",
        lambda profile, courses, evs: EventRanking(picks=[
            RankedEvent(event_id="e9", why_note="ghost"),
            RankedEvent(event_id="e1", why_note="matches FPGAs"),
        ]),
    )
    captured = {}
    monkeypatch.setattr(
        curation.db, "replace_event_recommendations",
        lambda uid, rows: captured.setdefault("rows", rows) or [],
    )
    curation.curate_events("u1")
    assert captured["rows"] == [{"event_id": "e1", "why_note": "matches FPGAs", "rank": 0}]


def test_curate_with_no_events_clears_recs(monkeypatch):
    monkeypatch.setattr(curation.db, "get_profile", lambda uid: None)
    monkeypatch.setattr(curation.db, "get_major_map_courses", lambda uid: [])
    monkeypatch.setattr(curation.db, "get_upcoming_events", lambda limit=40: [])
    monkeypatch.setattr(
        curation, "_rank",
        lambda *a: (_ for _ in ()).throw(AssertionError("_rank must not run when events is empty")),
    )
    captured = {}
    monkeypatch.setattr(
        curation.db, "replace_event_recommendations",
        lambda uid, rows: captured.setdefault("rows", rows) or [],
    )
    curation.curate_events("u1")
    assert captured["rows"] == []
