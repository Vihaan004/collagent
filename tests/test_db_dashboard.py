# tests/test_db_dashboard.py
from unittest.mock import MagicMock

from collagent import db

SNAP = {"id": "d1", "user_id": "u1", "brief_md": "# Hi", "news": [],
        "generated_at": "2026-06-20T00:00:00Z"}


def _client():
    client = MagicMock()
    client.table.return_value.upsert.return_value.execute.return_value.data = [SNAP]
    client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [SNAP]
    client.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
    return client


def test_upsert_dashboard_snapshot_uses_user_conflict(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    snap = db.upsert_dashboard_snapshot("u1", "# Hi", [])
    payload, kwargs = client.table.return_value.upsert.call_args
    assert kwargs.get("on_conflict") == "user_id"
    assert payload[0]["user_id"] == "u1" and payload[0]["brief_md"] == "# Hi"
    assert snap.brief_md == "# Hi"


def test_get_dashboard_snapshot_scopes_to_user(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    snap = db.get_dashboard_snapshot("u1")
    client.table.return_value.select.return_value.eq.assert_called_once_with("user_id", "u1")
    assert snap.brief_md == "# Hi"


def test_get_dashboard_snapshot_none_when_missing(monkeypatch):
    client = _client()
    client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    monkeypatch.setattr(db, "get_client", lambda: client)
    assert db.get_dashboard_snapshot("u1") is None


def test_delete_event_recommendation_scopes_to_id_and_user(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    db.delete_event_recommendation("u1", "r1")
    eq_chain = client.table.return_value.delete.return_value.eq
    eq_chain.assert_called_once_with("id", "r1")
    eq_chain.return_value.eq.assert_called_once_with("user_id", "u1")


def test_delete_person_recommendation_scopes_to_id_and_user(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    db.delete_person_recommendation("u1", "r2")
    eq_chain = client.table.return_value.delete.return_value.eq
    eq_chain.assert_called_once_with("id", "r2")
    eq_chain.return_value.eq.assert_called_once_with("user_id", "u1")
