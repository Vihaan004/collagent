# tests/test_db_people.py
from unittest.mock import MagicMock

from collagent import db

REC_ROW = {
    "id": "r1", "person_id": "p1", "why_note": "fits you", "rank": 0,
    "people": {
        "name": "Bing Si", "title": "Associate Professor",
        "departments": ["SCAI"], "expertise_areas": ["Machine Learning"],
        "email": "bing.si@asu.edu", "profile_url": "https://search.asu.edu/profile/123",
        "photo_url": None, "research_interests": None, "short_bio": None,
    },
}


def _client():
    client = MagicMock()
    client.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "p1"}]
    client.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value.data = [{"id": "p1", "name": "Bing Si"}]
    client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [REC_ROW]
    client.table.return_value.delete.return_value.eq.return_value.execute.return_value.data = []
    client.table.return_value.insert.return_value.execute.return_value.data = [{"id": "r1"}]
    return client


def test_upsert_people_uses_conflict_target(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    db.upsert_people([{"source": "asu_isearch", "source_person_key": "k", "name": "X", "profile_url": "u"}])
    _, kwargs = client.table.return_value.upsert.call_args
    assert kwargs.get("on_conflict") == "source,source_person_key"


def test_get_people_orders_and_limits(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    rows = db.get_people(limit=30)
    assert rows == [{"id": "p1", "name": "Bing Si"}]
    client.table.return_value.select.return_value.order.return_value.limit.assert_called_once_with(30)


def test_get_person_recommendations_flattens_join(monkeypatch):
    monkeypatch.setattr(db, "get_client", lambda: _client())
    recs = db.get_person_recommendations("u1")
    assert len(recs) == 1
    assert recs[0].name == "Bing Si"
    assert recs[0].why_note == "fits you"
    assert recs[0].person_id == "p1" and recs[0].rank == 0
    assert recs[0].expertise_areas == ["Machine Learning"]


def test_replace_person_recommendations_deletes_then_inserts(monkeypatch):
    client = _client()
    monkeypatch.setattr(db, "get_client", lambda: client)
    recs = db.replace_person_recommendations("u1", [{"person_id": "p1", "why_note": "w", "rank": 0}])
    client.table.return_value.delete.assert_called_once()
    inserted = client.table.return_value.insert.call_args.args[0]
    assert inserted[0]["user_id"] == "u1" and inserted[0]["person_id"] == "p1"
    assert recs[0].name == "Bing Si"  # round-trips through get_person_recommendations
