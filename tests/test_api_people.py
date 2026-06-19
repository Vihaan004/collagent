# tests/test_api_people.py
from collagent.api.routes import people as people_routes
from collagent.models import PersonRecommendation

REC = PersonRecommendation(
    id="r1", person_id="p1", name="Bing Si", title="Associate Professor",
    departments=["SCAI"], expertise_areas=["Machine Learning"],
    email="bing.si@asu.edu", profile_url="https://search.asu.edu/profile/123",
    why_note="Matches your ML interest.", rank=0,
)


def test_get_people(client, monkeypatch):
    monkeypatch.setattr(people_routes.db, "get_person_recommendations", lambda uid: [REC])
    res = client.get("/api/people")
    assert res.status_code == 200
    assert res.json()[0]["name"] == "Bing Si"
    assert res.json()[0]["why_note"] == "Matches your ML interest."


def test_refresh_people_ingests_then_curates(client, monkeypatch):
    calls = []
    monkeypatch.setattr(people_routes.db, "get_profile", lambda uid: None)
    monkeypatch.setattr(people_routes.db, "get_major_map_courses", lambda uid: [])
    monkeypatch.setattr(people_routes, "query_terms", lambda profile: ["robotics"])
    monkeypatch.setattr(people_routes, "fetch_faculty", lambda terms: calls.append("fetch") or [{"x": 1}])
    monkeypatch.setattr(people_routes.db, "upsert_people", lambda rows: calls.append("upsert"))
    monkeypatch.setattr(people_routes, "curate_people", lambda uid: calls.append("curate") or [REC])
    res = client.post("/api/people/refresh", json={})
    assert res.status_code == 200
    assert calls == ["fetch", "upsert", "curate"]  # ingest before curate
    assert res.json()[0]["person_id"] == "p1"


def test_people_unauthenticated_401():
    from fastapi.testclient import TestClient

    from collagent.api.main import app

    assert TestClient(app).get("/api/people").status_code == 401
