import types

from collagent import curriculum_tools


def _tools(uid="u1"):
    return {t.name: t for t in curriculum_tools.make_curriculum_tools(uid)}


def test_read_curriculum_uses_profile_major(monkeypatch):
    monkeypatch.setattr(curriculum_tools, "get_checksheet_url", lambda code: f"http://x/{code}")
    monkeypatch.setattr(curriculum_tools, "fetch_curriculum", lambda url: f"CURRIC {url}")
    monkeypatch.setattr(
        curriculum_tools.db, "get_profile",
        lambda uid: types.SimpleNamespace(acad_plan_code="BAACCBS"),
    )
    out = _tools()["read_curriculum"].invoke({})
    assert "CURRIC http://x/BAACCBS" in out


def test_read_curriculum_explicit_code(monkeypatch):
    monkeypatch.setattr(curriculum_tools, "get_checksheet_url", lambda code: f"http://x/{code}")
    monkeypatch.setattr(curriculum_tools, "fetch_curriculum", lambda url: "OK")
    out = _tools()["read_curriculum"].invoke({"program_code": "ESCSEBS"})
    assert out == "OK"


def test_read_curriculum_no_major(monkeypatch):
    monkeypatch.setattr(
        curriculum_tools.db, "get_profile",
        lambda uid: types.SimpleNamespace(acad_plan_code=None),
    )
    out = _tools()["read_curriculum"].invoke({})
    assert "no major" in out.lower()


def test_read_curriculum_no_url(monkeypatch):
    monkeypatch.setattr(curriculum_tools, "get_checksheet_url", lambda code: None)
    out = _tools()["read_curriculum"].invoke({"program_code": "ZZZ"})
    assert "no published curriculum" in out.lower()
