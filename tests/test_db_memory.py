# tests/test_db_memory.py
from unittest.mock import MagicMock

from collagent import db

ROW = {"id": "m1", "user_id": "u1", "content": "Prefers FPGA research", "kind": "fact",
       "created_at": "2026-06-20T00:00:00Z", "updated_at": "2026-06-20T00:00:00Z"}


def _client():
    client = MagicMock()
    # get_memories: select().eq().order().execute()
    client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [ROW]
    # create_memory: insert().execute()
    client.table.return_value.insert.return_value.execute.return_value.data = [ROW]
    # update_memory: update().eq().eq().execute()
    client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = [ROW]
    # delete_memory: delete().eq().eq().execute()
    client.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
    return client


def test_get_memories_scopes_to_user(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    mems = db.get_memories("u1")
    assert len(mems) == 1 and mems[0].content == "Prefers FPGA research"
    client.table.return_value.select.return_value.eq.assert_called_once_with("user_id", "u1")


def test_create_memory_inserts_user_scoped_row(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    m = db.create_memory("u1", "Prefers FPGA research", "fact")
    inserted = client.table.return_value.insert.call_args.args[0]
    assert inserted["user_id"] == "u1" and inserted["content"] == "Prefers FPGA research"
    assert inserted["kind"] == "fact"
    assert m.id == "m1"


def test_update_memory_filters_by_id_and_user(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    m = db.update_memory("u1", "m1", "new content")
    assert m.id == "m1"
    eq_chain = client.table.return_value.update.return_value.eq
    eq_chain.assert_called_once_with("id", "m1")
    eq_chain.return_value.eq.assert_called_once_with("user_id", "u1")


def test_update_memory_missing_raises(monkeypatch):
    client = _client()
    client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
    monkeypatch.setattr(db, "get_client", lambda: client)
    import pytest
    with pytest.raises(ValueError):
        db.update_memory("u1", "nope", "x")


def test_delete_memory_filters_by_id_and_user(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    db.delete_memory("u1", "m1")
    eq_chain = client.table.return_value.delete.return_value.eq
    eq_chain.assert_called_once_with("id", "m1")
    eq_chain.return_value.eq.assert_called_once_with("user_id", "u1")
