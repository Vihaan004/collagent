# tests/test_api_events.py
from collagent.api.routes import events as ev_routes
from collagent.models import EventRecommendation
from tests.conftest import TEST_USER

REC = EventRecommendation(
    id="r1", event_id="e1", title="Intro to FPGAs",
    url="https://asuevents.asu.edu/event/intro-to-fpgas",
    why_note="Matches your FPGA interest.", rank=0,
)


def test_get_events(client, monkeypatch):
    monkeypatch.setattr(ev_routes.db, "get_event_recommendations", lambda uid: [REC])
    res = client.get("/api/events")
    assert res.status_code == 200
    assert res.json()[0]["title"] == "Intro to FPGAs"
    assert res.json()[0]["why_note"] == "Matches your FPGA interest."


def test_refresh_events_ingests_then_curates(client, monkeypatch):
    calls = []
    monkeypatch.setattr(ev_routes, "fetch_upcoming_events", lambda: calls.append("fetch") or [{"x": 1}])
    monkeypatch.setattr(ev_routes.db, "upsert_events", lambda rows: calls.append("upsert"))
    monkeypatch.setattr(ev_routes, "curate_events", lambda uid: calls.append("curate") or [REC])
    res = client.post("/api/events/refresh", json={})
    assert res.status_code == 200
    assert calls == ["fetch", "upsert", "curate"]  # ingest before curate
    assert res.json()[0]["event_id"] == "e1"


def test_events_unauthenticated_401():
    from fastapi.testclient import TestClient

    from collagent.api.main import app

    assert TestClient(app).get("/api/events").status_code == 401
