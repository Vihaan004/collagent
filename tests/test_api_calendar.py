# tests/test_api_calendar.py
from collagent.api.routes import calendar as cal_routes
from collagent.models import CalendarItem

ITEM = CalendarItem(id="c1", term="Summer 2026", session="A", title="Classes Begin",
                    date_start="2026-05-18", category="academic")


def test_get_calendar(client, monkeypatch):
    monkeypatch.setattr(cal_routes.db, "get_upcoming_calendar_items", lambda **k: [ITEM])
    res = client.get("/api/calendar")
    assert res.status_code == 200
    assert res.json()[0]["title"] == "Classes Begin"
    assert res.json()[0]["session"] == "A"


def test_refresh_calendar_fetches_then_upserts(client, monkeypatch):
    calls = []
    monkeypatch.setattr(cal_routes, "fetch_calendar",
                        lambda: calls.append("fetch") or [{"term": "Summer 2026", "session": "A",
                        "title": "Classes Begin", "date_start": "2026-05-18", "date_end": None,
                        "category": "academic"}])
    monkeypatch.setattr(cal_routes.db, "upsert_calendar_items",
                        lambda rows: calls.append("upsert"))
    monkeypatch.setattr(cal_routes.db, "get_upcoming_calendar_items", lambda **k: [ITEM])
    res = client.post("/api/calendar/refresh", json={})
    assert res.status_code == 200
    assert calls == ["fetch", "upsert"]  # fetch before upsert
    assert res.json()[0]["title"] == "Classes Begin"


def test_calendar_unauthenticated_401():
    from fastapi.testclient import TestClient

    from collagent.api.main import app

    assert TestClient(app).get("/api/calendar").status_code == 401
