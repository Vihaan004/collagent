from collagent.api.routes import majormap as mm_routes
from collagent.asu.majormap import ExtractedCourse, ExtractedMajorMap
from collagent.models import MajorMapCourse
from tests.conftest import TEST_USER

COURSE = MajorMapCourse(
    id="c1", user_id=TEST_USER, term_number=1, course_code="CSE 110",
    title="Programming", status="remaining",
)


def test_get_major_map(client, monkeypatch):
    monkeypatch.setattr(mm_routes.db, "get_major_map_courses", lambda uid: [COURSE])
    res = client.get("/api/major-map")
    assert res.status_code == 200 and res.json()[0]["course_code"] == "CSE 110"


def test_generate_major_map(client, monkeypatch):
    monkeypatch.setattr(mm_routes.settings, "major_map_enabled", True)  # default is off
    extracted = ExtractedMajorMap(
        program_name="Computer Science, BS",
        courses=[ExtractedCourse(term_number=1, course_code="CSE 110", title="Programming")],
    )
    monkeypatch.setattr(mm_routes, "build_major_map", lambda code, year: extracted)
    captured = {}

    def fake_replace(uid, rows):
        captured["rows"] = rows
        return [COURSE]

    monkeypatch.setattr(mm_routes.db, "replace_major_map_courses", fake_replace)
    res = client.post("/api/major-map/generate", json={"acad_plan_code": "ESCSEBS", "catalog_year": "2025"})
    assert res.status_code == 200
    assert captured["rows"][0]["course_code"] == "CSE 110"
    assert captured["rows"][0]["sort_order"] == 0


def test_generate_disabled_returns_503(client, monkeypatch):
    # When the feature flag is off, the route must not invoke Playwright-backed
    # extraction at all (keeps the demo host RAM-light; no Chromium launch).
    monkeypatch.setattr(mm_routes.settings, "major_map_enabled", False)

    def boom(code, year):
        raise AssertionError("build_major_map must not run when the feature is disabled")

    monkeypatch.setattr(mm_routes, "build_major_map", boom)
    res = client.post("/api/major-map/generate", json={"acad_plan_code": "ESCSEBS", "catalog_year": "2024"})
    assert res.status_code == 503


def test_update_statuses(client, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        mm_routes.db, "update_course_statuses",
        lambda uid, updates: captured.setdefault("updates", updates),
    )
    res = client.put("/api/major-map/statuses", json={"updates": [{"id": "c1", "status": "taken"}]})
    assert res.status_code == 200
    assert captured["updates"] == [("c1", "taken")]
