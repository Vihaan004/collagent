# tests/test_api_dashboard.py
from collagent.api.routes import dashboard as dash_routes
from collagent.models import (
    CalendarItem,
    DashboardSnapshot,
    EventRecommendation,
    PersonRecommendation,
)


def test_get_dashboard_aggregates_snapshot_and_live(client, monkeypatch):
    monkeypatch.setattr(dash_routes.db, "get_dashboard_snapshot",
                        lambda uid: DashboardSnapshot(brief_md="# Hi", news=[],
                                                      generated_at="2026-06-20T00:00:00Z"))
    monkeypatch.setattr(dash_routes.db, "get_event_recommendations",
                        lambda uid: [EventRecommendation(id="e1", event_id="ev1", title="Talk",
                                                         url="https://e", why_note="w", rank=0)])
    monkeypatch.setattr(dash_routes.db, "get_person_recommendations",
                        lambda uid: [PersonRecommendation(id="p1", person_id="pe1", name="Dr X",
                                                          profile_url="https://p", why_note="w", rank=0)])
    monkeypatch.setattr(dash_routes.db, "get_upcoming_calendar_items",
                        lambda: [CalendarItem(id="c1", term="Summer 2026", title="Drop deadline")])
    res = client.get("/api/dashboard")
    assert res.status_code == 200
    body = res.json()
    assert body["brief_md"] == "# Hi"
    assert body["events"][0]["title"] == "Talk"
    assert body["people"][0]["name"] == "Dr X"
    assert body["deadlines"][0]["title"] == "Drop deadline"


def test_get_dashboard_top5_slicing(client, monkeypatch):
    many_events = [
        EventRecommendation(id=f"e{i}", event_id=f"ev{i}", title=f"T{i}",
                            url="https://e", why_note="w", rank=i)
        for i in range(8)
    ]
    monkeypatch.setattr(dash_routes.db, "get_dashboard_snapshot", lambda uid: None)
    monkeypatch.setattr(dash_routes.db, "get_event_recommendations", lambda uid: many_events)
    monkeypatch.setattr(dash_routes.db, "get_person_recommendations", lambda uid: [])
    monkeypatch.setattr(dash_routes.db, "get_upcoming_calendar_items", lambda: [])
    body = client.get("/api/dashboard").json()
    assert body["brief_md"] == "" and len(body["events"]) == 5


def test_dashboard_unauthenticated_401():
    from fastapi.testclient import TestClient

    from collagent.api.main import app

    assert TestClient(app).get("/api/dashboard").status_code == 401
