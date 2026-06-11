from collagent.api.routes import profile as profile_routes
from collagent.models import Profile
from tests.conftest import TEST_USER

PROFILE = Profile(id=TEST_USER, email="a@asu.edu")


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_get_profile(client, monkeypatch):
    monkeypatch.setattr(profile_routes.db, "get_profile", lambda uid: PROFILE)
    res = client.get("/api/profile")
    assert res.status_code == 200 and res.json()["email"] == "a@asu.edu"


def test_get_profile_404(client, monkeypatch):
    monkeypatch.setattr(profile_routes.db, "get_profile", lambda uid: None)
    assert client.get("/api/profile").status_code == 404


def test_put_profile(client, monkeypatch):
    captured = {}

    def fake_update(uid, update):
        captured["fields"] = update.model_dump(exclude_unset=True)
        return PROFILE.model_copy(update=captured["fields"])

    monkeypatch.setattr(profile_routes.db, "update_profile", fake_update)
    res = client.put("/api/profile", json={"major_name": "Computer Science"})
    assert res.status_code == 200
    assert captured["fields"] == {"major_name": "Computer Science"}


def test_unauthenticated_401():
    from fastapi.testclient import TestClient

    from collagent.api.main import app

    assert TestClient(app).get("/api/profile").status_code == 401
