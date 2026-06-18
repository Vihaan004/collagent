# tests/test_db_events.py
from unittest.mock import MagicMock

from collagent import db

REC_ROW = {
    "id": "r1", "event_id": "e1", "why_note": "fits you", "rank": 0,
    "events": {
        "title": "Intro to FPGAs", "description": "Learn FPGAs",
        "starts_at": "2026-06-20T14:00:00-07:00", "ends_at": None,
        "location": "Tempe", "url": "https://asuevents.asu.edu/event/intro-to-fpgas",
    },
}


def _client():
    client = MagicMock()
    client.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "e1"}]
    client.table.return_value.select.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value.data = [{"id": "e1", "title": "X"}]
    client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [REC_ROW]
    client.table.return_value.delete.return_value.eq.return_value.execute.return_value.data = []
    client.table.return_value.insert.return_value.execute.return_value.data = [{"id": "r1"}]
    return client


def test_upsert_events_uses_conflict_target(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    db.upsert_events([{"source": "asu_events", "source_event_key": "k", "title": "X", "url": "u"}])
    _, kwargs = client.table.return_value.upsert.call_args
    assert kwargs.get("on_conflict") == "source,source_event_key"


def test_get_upcoming_events_filters_future(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    rows = db.get_upcoming_events(limit=5)
    assert rows == [{"id": "e1", "title": "X"}]
    client.table.return_value.select.return_value.gte.assert_called_once()
    client.table.return_value.select.return_value.gte.return_value.order.return_value.limit.assert_called_once_with(5)


def test_get_event_recommendations_flattens_join(monkeypatch):
    monkeypatch.setattr(db, "get_client", lambda: _client())
    recs = db.get_event_recommendations("u1")
    assert len(recs) == 1
    assert recs[0].title == "Intro to FPGAs"
    assert recs[0].why_note == "fits you"
    assert recs[0].event_id == "e1" and recs[0].rank == 0


def test_replace_event_recommendations_deletes_then_inserts(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    recs = db.replace_event_recommendations("u1", [{"event_id": "e1", "why_note": "w", "rank": 0}])
    client.table.return_value.delete.assert_called_once()
    inserted = client.table.return_value.insert.call_args.args[0]
    assert inserted[0]["user_id"] == "u1" and inserted[0]["event_id"] == "e1"
    assert recs[0].title == "Intro to FPGAs"  # return value round-trips through get_event_recommendations
