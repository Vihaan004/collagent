from collagent import profile_tools
from collagent.models import MajorMapCourse


def test_update_profile_tool_writes_structured_fields(monkeypatch):
    captured = {}

    def fake_update(uid, update):
        captured["uid"] = uid
        captured["fields"] = update.model_dump(exclude_unset=True)
        return None

    monkeypatch.setattr(profile_tools.db, "update_profile", fake_update)
    tools = {t.name: t for t in profile_tools.make_profile_tools("u1")}
    result = tools["update_profile"].invoke({"interests": ["FPGAs"], "goals": "RTL design"})
    assert captured["uid"] == "u1"
    assert captured["fields"] == {"interests": ["FPGAs"], "goals": "RTL design"}
    assert "updated" in result.lower()


def test_set_course_status_matches_by_code(monkeypatch):
    course = MajorMapCourse(
        id="c9", user_id="u1", term_number=3, course_code="CSE 230",
        title="Assembly", status="remaining",
    )
    monkeypatch.setattr(profile_tools.db, "get_major_map_courses", lambda uid: [course])
    captured = {}
    monkeypatch.setattr(
        profile_tools.db, "update_course_statuses",
        lambda uid, updates: captured.setdefault("updates", updates),
    )
    tools = {t.name: t for t in profile_tools.make_profile_tools("u1")}
    result = tools["set_course_status"].invoke({"course_code": "cse 230", "status": "taken"})
    assert captured["updates"] == [("c9", "taken")]
    assert "CSE 230" in result


def test_set_course_status_unknown_code(monkeypatch):
    monkeypatch.setattr(profile_tools.db, "get_major_map_courses", lambda uid: [])
    tools = {t.name: t for t in profile_tools.make_profile_tools("u1")}
    result = tools["set_course_status"].invoke({"course_code": "XYZ 999", "status": "taken"})
    assert "not found" in result.lower()
