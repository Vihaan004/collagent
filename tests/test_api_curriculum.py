import types

from collagent.api.routes import curriculum as cur_routes


def test_curriculum_returns_markdown(client, monkeypatch):
    monkeypatch.setattr(
        cur_routes.db, "get_profile",
        lambda uid: types.SimpleNamespace(acad_plan_code="BAACCBS", major_name="Accountancy,BS"),
    )
    monkeypatch.setattr(cur_routes, "get_checksheet_url", lambda code: "http://x/BAACCBS")
    monkeypatch.setattr(cur_routes, "fetch_curriculum", lambda url: "## Core\n- ACC 231")
    res = client.get("/api/curriculum")
    assert res.status_code == 200
    body = res.json()
    assert body["program_name"] == "Accountancy,BS"
    assert body["markdown"].startswith("## Core")


def test_curriculum_empty_when_no_major(client, monkeypatch):
    monkeypatch.setattr(
        cur_routes.db, "get_profile",
        lambda uid: types.SimpleNamespace(acad_plan_code=None, major_name=None),
    )
    monkeypatch.setattr(cur_routes, "get_checksheet_url", lambda code: None)
    res = client.get("/api/curriculum")
    assert res.status_code == 200
    assert res.json()["markdown"] is None
