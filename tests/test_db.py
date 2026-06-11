import pytest
from unittest.mock import MagicMock

from collagent import db
from collagent.models import ProfileUpdate

PROFILE_ROW = {"id": "u1", "email": "a@asu.edu", "major_name": None}
COURSE_ROW = {
    "id": "c1", "user_id": "u1", "term_number": 1,
    "course_code": "CSE 110", "title": "Programming", "status": "remaining",
}


def _client_returning(data):
    client = MagicMock()
    # terminal .execute() on any chained call returns an object with .data
    client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = data
    client.table.return_value.select.return_value.eq.return_value.order.return_value.order.return_value.execute.return_value.data = data
    client.table.return_value.update.return_value.eq.return_value.execute.return_value.data = data
    client.table.return_value.insert.return_value.execute.return_value.data = data
    client.table.return_value.delete.return_value.eq.return_value.execute.return_value.data = []
    return client


def test_get_profile_found(monkeypatch):
    monkeypatch.setattr(db, "get_client", lambda: _client_returning([PROFILE_ROW]))
    p = db.get_profile("u1")
    assert p is not None and p.email == "a@asu.edu"


def test_get_profile_missing(monkeypatch):
    monkeypatch.setattr(db, "get_client", lambda: _client_returning([]))
    assert db.get_profile("u1") is None


def test_update_profile_sends_only_set_fields(monkeypatch):
    client = _client_returning([PROFILE_ROW])
    monkeypatch.setattr(db, "get_client", lambda: client)
    db.update_profile("u1", ProfileUpdate(major_name="CS"))
    client.table.return_value.update.assert_called_once_with({"major_name": "CS"})


def test_get_major_map_courses(monkeypatch):
    monkeypatch.setattr(db, "get_client", lambda: _client_returning([COURSE_ROW]))
    courses = db.get_major_map_courses("u1")
    assert len(courses) == 1 and courses[0].course_code == "CSE 110"


def test_replace_major_map_courses_deletes_then_inserts(monkeypatch):
    client = _client_returning([COURSE_ROW])
    monkeypatch.setattr(db, "get_client", lambda: client)
    rows = [{"term_number": 1, "title": "Programming", "course_code": "CSE 110"}]
    result = db.replace_major_map_courses("u1", rows)
    client.table.return_value.delete.assert_called_once()
    inserted = client.table.return_value.insert.call_args.args[0]
    assert inserted[0]["user_id"] == "u1"
    assert result[0].id == "c1"


def test_replace_major_map_courses_rejects_empty(monkeypatch):
    client = _client_returning([COURSE_ROW])
    monkeypatch.setattr(db, "get_client", lambda: client)
    with pytest.raises(ValueError):
        db.replace_major_map_courses("u1", [])
    client.table.return_value.delete.assert_not_called()


def test_update_course_statuses_patches_each(monkeypatch):
    client = _client_returning([COURSE_ROW])
    monkeypatch.setattr(db, "get_client", lambda: client)
    db.update_course_statuses("u1", [("c1", "taken")])
    client.table.return_value.update.assert_called_once_with({"status": "taken"})
