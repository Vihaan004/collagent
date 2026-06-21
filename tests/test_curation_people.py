# tests/test_curation_people.py
from collagent.curation import people as curation
from collagent.curation.people import PersonRanking, RankedPerson
from collagent.models import Profile


def test_curate_drops_hallucinated_ids_and_reranks(monkeypatch):
    profile = Profile(id="u1", email="a@asu.edu", interests=["robotics"])
    monkeypatch.setattr(curation.db, "get_profile", lambda uid: profile)
    monkeypatch.setattr(curation.db, "get_major_map_courses", lambda uid: [])
    monkeypatch.setattr(
        curation.db, "get_people",
        lambda limit=60: [{"id": "p1", "name": "Prof A"}, {"id": "p2", "name": "Prof B"}],
    )
    monkeypatch.setattr(
        curation, "_rank",
        lambda profile, courses, ppl, focus=None: PersonRanking(picks=[
            RankedPerson(person_id="p9", why_note="ghost"),
            RankedPerson(person_id="p1", why_note="works on robotics"),
        ]),
    )
    captured = {}
    monkeypatch.setattr(
        curation.db, "replace_person_recommendations",
        lambda uid, rows: captured.setdefault("rows", rows) or [],
    )
    curation.curate_people("u1")
    assert captured["rows"] == [{"person_id": "p1", "why_note": "works on robotics", "rank": 0}]


def test_curate_people_forwards_focus_to_rank(monkeypatch):
    profile = Profile(id="u1", email="a@asu.edu", interests=["robotics"])
    monkeypatch.setattr(curation.db, "get_profile", lambda uid: profile)
    monkeypatch.setattr(curation.db, "get_major_map_courses", lambda uid: [])
    monkeypatch.setattr(curation.db, "get_people", lambda limit=60: [{"id": "p1", "name": "A"}])
    captured = {}
    monkeypatch.setattr(
        curation, "_rank",
        lambda profile, courses, ppl, focus=None: captured.update(focus=focus)
        or PersonRanking(picks=[]),
    )
    monkeypatch.setattr(curation.db, "replace_person_recommendations", lambda uid, rows: [])
    curation.curate_people("u1", focus=["quantum computing"])
    assert captured["focus"] == ["quantum computing"]


def test_rank_injects_focus_into_prompt(monkeypatch):
    captured = {}

    class _Structured:
        def invoke(self, messages):
            captured["messages"] = messages
            return PersonRanking(picks=[])

    class _Model:
        def with_structured_output(self, schema):
            return _Structured()

    monkeypatch.setattr(curation, "get_model", lambda: _Model())
    curation._rank(None, [], [{"id": "p1", "name": "A"}], focus=["quantum computing"])
    user_text = captured["messages"][1][1]
    assert "quantum computing" in user_text


def test_curate_with_no_people_clears_recs(monkeypatch):
    monkeypatch.setattr(curation.db, "get_profile", lambda uid: None)
    monkeypatch.setattr(curation.db, "get_major_map_courses", lambda uid: [])
    monkeypatch.setattr(curation.db, "get_people", lambda limit=60: [])
    monkeypatch.setattr(
        curation, "_rank",
        lambda *a: (_ for _ in ()).throw(AssertionError("_rank must not run when people is empty")),
    )
    captured = {}
    monkeypatch.setattr(
        curation.db, "replace_person_recommendations",
        lambda uid, rows: captured.setdefault("rows", rows) or [],
    )
    curation.curate_people("u1")
    assert captured["rows"] == []
