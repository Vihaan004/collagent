# tests/test_people_tools.py
from collagent import people_tools
from collagent.models import PersonRecommendation

REC = PersonRecommendation(
    id="r1", person_id="p1", name="Bing Si", title="Associate Professor",
    departments=["SCAI"], expertise_areas=["Machine Learning"],
    email="bing.si@asu.edu", profile_url="https://search.asu.edu/profile/123",
    why_note="Matches your ML interest.", rank=0,
)

FOUND = {
    "source_person_key": "jdoe", "name": "Jane Doe", "title": "Professor",
    "departments": ["SCAI"], "expertise_areas": ["Robotics"],
    "email": "jane.doe@asu.edu", "profile_url": "https://search.asu.edu/profile/456",
}


def test_get_person_recommendations_renders_list(monkeypatch):
    monkeypatch.setattr(people_tools.db, "get_person_recommendations", lambda uid: [REC])
    tools = {t.name: t for t in people_tools.make_people_tools("u1")}
    out = tools["get_person_recommendations"].invoke({})
    assert "Bing Si" in out
    assert "Machine Learning" in out
    assert "Matches your ML interest." in out
    assert "bing.si@asu.edu" in out
    assert "https://search.asu.edu/profile/123" in out


def test_get_person_recommendations_empty(monkeypatch):
    monkeypatch.setattr(people_tools.db, "get_person_recommendations", lambda uid: [])
    tools = {t.name: t for t in people_tools.make_people_tools("u1")}
    out = tools["get_person_recommendations"].invoke({})
    assert "no people recommendations" in out.lower()


def test_search_people_renders_and_upserts(monkeypatch):
    upserted = {}
    monkeypatch.setattr(people_tools, "search_faculty", lambda q, **k: [FOUND])
    monkeypatch.setattr(people_tools.db, "upsert_people", lambda rows: upserted.setdefault("rows", rows))
    tools = {t.name: t for t in people_tools.make_people_tools("u1")}
    out = tools["search_people"].invoke({"query": "robotics"})
    assert "Jane Doe" in out
    assert "Robotics" in out
    assert upserted["rows"] == [FOUND]  # live results persisted to the shared index


def test_search_people_no_matches(monkeypatch):
    monkeypatch.setattr(people_tools, "search_faculty", lambda q, **k: [])
    tools = {t.name: t for t in people_tools.make_people_tools("u1")}
    out = tools["search_people"].invoke({"query": "zzz"})
    assert "no asu directory matches" in out.lower()
