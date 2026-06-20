# tests/test_db_calendar.py
from unittest.mock import MagicMock

from collagent import db

ROW = {"id": "c1", "term": "Summer 2026", "session": "A", "title": "Classes Begin",
       "date_start": "2026-05-18", "date_end": None, "category": "academic",
       "fetched_at": "2026-06-20T00:00:00Z"}


def _client():
    client = MagicMock()
    client.table.return_value.upsert.return_value.execute.return_value.data = [ROW]
    client.table.return_value.select.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value.data = [ROW]
    return client


def test_upsert_calendar_items_uses_conflict_target(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    db.upsert_calendar_items([ROW])
    _, kwargs = client.table.return_value.upsert.call_args
    assert kwargs.get("on_conflict") == "term,session,title"


def test_upsert_calendar_items_empty_noop(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    assert db.upsert_calendar_items([]) == []
    client.table.return_value.upsert.assert_not_called()


def test_get_upcoming_calendar_items_filters_and_orders(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    rows = db.get_upcoming_calendar_items(since="2026-06-20", limit=10)
    assert rows[0].title == "Classes Begin"
    client.table.return_value.select.return_value.gte.assert_called_once_with("date_start", "2026-06-20")
    client.table.return_value.select.return_value.gte.return_value.order.assert_called_once_with("date_start")
