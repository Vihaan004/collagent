# tests/test_dashboard_tools.py
from collagent import dashboard_tools


def _tools():
    return {t.name: t for t in dashboard_tools.make_dashboard_tools("u1")}


def test_refresh_events_runs_pipeline_user_scoped(monkeypatch):
    calls = []
    monkeypatch.setattr(dashboard_tools, "fetch_upcoming_events", lambda: [{"id": "e1"}])
    monkeypatch.setattr(dashboard_tools.db, "upsert_events", lambda rows: calls.append("upsert"))
    monkeypatch.setattr(dashboard_tools, "curate_events", lambda uid: calls.append(uid) or [1, 2])
    out = _tools()["refresh_events"].invoke({})
    assert calls == ["upsert", "u1"]
    assert "2" in out


def test_refresh_people_runs_pipeline_user_scoped(monkeypatch):
    calls = []
    monkeypatch.setattr(dashboard_tools.db, "get_profile", lambda uid: None)
    monkeypatch.setattr(dashboard_tools, "query_terms", lambda p: ["x"])
    monkeypatch.setattr(dashboard_tools, "fetch_faculty", lambda terms: [{"id": "p1"}])
    monkeypatch.setattr(dashboard_tools.db, "upsert_people", lambda rows: calls.append("upsert"))
    monkeypatch.setattr(dashboard_tools, "curate_people", lambda uid: calls.append(uid) or [1])
    out = _tools()["refresh_people"].invoke({})
    assert calls == ["upsert", "u1"]
    assert "1" in out


def test_refresh_news_fetches_then_upserts(monkeypatch):
    calls = []
    monkeypatch.setattr(dashboard_tools, "fetch_news", lambda: [{"url": "u"}])
    monkeypatch.setattr(dashboard_tools.db, "upsert_news_items", lambda rows: calls.append("upsert"))
    out = _tools()["refresh_news"].invoke({})
    assert calls == ["upsert"] and "1" in out


def test_refresh_news_noop_without_results(monkeypatch):
    def boom(rows):
        raise AssertionError("should not upsert on empty fetch")
    monkeypatch.setattr(dashboard_tools, "fetch_news", lambda: [])
    monkeypatch.setattr(dashboard_tools.db, "upsert_news_items", boom)
    out = _tools()["refresh_news"].invoke({})
    assert "0" in out


def test_update_calendar_fetches_then_upserts(monkeypatch):
    calls = []
    monkeypatch.setattr(dashboard_tools, "fetch_calendar", lambda: [{"title": "x"}])
    monkeypatch.setattr(dashboard_tools.db, "upsert_calendar_items", lambda rows: calls.append("upsert"))
    out = _tools()["update_calendar"].invoke({})
    assert calls == ["upsert"] and "1" in out
