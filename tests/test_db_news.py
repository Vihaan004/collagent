# tests/test_db_news.py
from unittest.mock import MagicMock

from collagent import db

ROW = {"id": "n1", "source": "tavily", "source_key": "https://news.asu.edu/chip",
       "title": "ASU lands grant", "url": "https://news.asu.edu/chip",
       "summary": "snippet", "published_at": None, "fetched_at": "2026-06-20T00:00:00Z"}


def _client():
    client = MagicMock()
    client.table.return_value.upsert.return_value.execute.return_value.data = [ROW]
    client.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value.data = [ROW]
    return client


def test_upsert_news_items_uses_conflict_target(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    db.upsert_news_items([ROW])
    _, kwargs = client.table.return_value.upsert.call_args
    assert kwargs.get("on_conflict") == "source,source_key"


def test_upsert_news_items_empty_noop(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    assert db.upsert_news_items([]) == []
    client.table.return_value.upsert.assert_not_called()


def test_get_recent_news_orders_by_fetched_and_limits(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    rows = db.get_recent_news(limit=12)
    assert rows[0].title == "ASU lands grant"
    client.table.return_value.select.return_value.order.assert_called_once_with("fetched_at", desc=True)
    client.table.return_value.select.return_value.order.return_value.limit.assert_called_once_with(12)
