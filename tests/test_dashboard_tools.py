# tests/test_dashboard_tools.py
from collagent import dashboard_tools


def _tools():
    return {t.name: t for t in dashboard_tools.make_dashboard_tools("u1")}


def test_refresh_events_runs_pipeline_user_scoped(monkeypatch):
    calls = []
    monkeypatch.setattr(dashboard_tools, "fetch_upcoming_events", lambda: [{"id": "e1"}])
    monkeypatch.setattr(dashboard_tools.db, "upsert_events", lambda rows: calls.append("upsert"))
    monkeypatch.setattr(dashboard_tools, "curate_events", lambda uid, focus=None: calls.append(uid) or [1, 2])
    out = _tools()["refresh_events"].invoke({})
    assert calls == ["upsert", "u1"]
    assert "2" in out


def test_refresh_people_runs_pipeline_user_scoped(monkeypatch):
    calls = []
    monkeypatch.setattr(dashboard_tools.db, "get_profile", lambda uid: None)
    monkeypatch.setattr(dashboard_tools, "query_terms", lambda p: ["x"])
    monkeypatch.setattr(dashboard_tools, "fetch_faculty", lambda terms: [{"id": "p1"}])
    monkeypatch.setattr(dashboard_tools.db, "upsert_people", lambda rows: calls.append("upsert"))
    monkeypatch.setattr(dashboard_tools, "curate_people", lambda uid, focus=None: calls.append(uid) or [1])
    out = _tools()["refresh_people"].invoke({})
    assert calls == ["upsert", "u1"]
    assert "1" in out


def test_merge_focus_prepends_dedupes_caps():
    out = dashboard_tools._merge_focus(["a", "b", "c"], ["c", "z"], cap=3)
    assert out == ["c", "z", "a"]


def test_refresh_people_with_focus_merges_terms_and_forwards(monkeypatch):
    captured = {}
    monkeypatch.setattr(dashboard_tools.db, "get_profile", lambda uid: None)
    monkeypatch.setattr(dashboard_tools, "query_terms", lambda p: ["robotics"])
    monkeypatch.setattr(dashboard_tools, "fetch_faculty",
                        lambda terms: captured.update(terms=terms) or [{"id": "p1"}])
    monkeypatch.setattr(dashboard_tools.db, "upsert_people", lambda rows: None)
    monkeypatch.setattr(dashboard_tools, "curate_people",
                        lambda uid, focus=None: captured.update(focus=focus) or [1])
    out = _tools()["refresh_people"].invoke({"focus": ["quantum computing"]})
    assert captured["terms"][0] == "quantum computing"  # focus prepended into search
    assert "robotics" in captured["terms"]
    assert captured["focus"] == ["quantum computing"]   # forwarded to ranking
    assert "quantum computing" in out                    # status mentions the focus


def test_refresh_events_with_focus_forwards_to_curate(monkeypatch):
    captured = {}
    monkeypatch.setattr(dashboard_tools, "fetch_upcoming_events", lambda: [{"id": "e1"}])
    monkeypatch.setattr(dashboard_tools.db, "upsert_events", lambda rows: None)
    monkeypatch.setattr(dashboard_tools, "curate_events",
                        lambda uid, focus=None: captured.update(focus=focus) or [1])
    out = _tools()["refresh_events"].invoke({"focus": ["quantum computing"]})
    assert captured["focus"] == ["quantum computing"]
    assert "quantum computing" in out


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


from collagent.models import CalendarItem, NewsItem


def test_get_news_lists_ids_and_titles(monkeypatch):
    item = NewsItem(id="n1", title="ASU grant", url="https://x", summary="big news")
    monkeypatch.setattr(dashboard_tools.db, "get_recent_news", lambda **k: [item])
    out = _tools()["get_news"].invoke({})
    assert "n1" in out and "ASU grant" in out


def test_get_news_empty(monkeypatch):
    monkeypatch.setattr(dashboard_tools.db, "get_recent_news", lambda **k: [])
    out = _tools()["get_news"].invoke({})
    assert "refresh_news" in out


def test_get_deadlines_lists_items(monkeypatch):
    c = CalendarItem(id="c1", term="Summer 2026", title="Drop deadline",
                     date_start="2026-07-01", category="deadline")
    monkeypatch.setattr(dashboard_tools.db, "get_upcoming_calendar_items", lambda: [c])
    out = _tools()["get_deadlines"].invoke({})
    assert "Drop deadline" in out


def test_remove_event_recommendation_scopes_to_user(monkeypatch):
    captured = {}
    monkeypatch.setattr(dashboard_tools.db, "delete_event_recommendation",
                        lambda uid, rid: captured.update(uid=uid, rid=rid))
    out = _tools()["remove_event_recommendation"].invoke({"recommendation_id": "r1"})
    assert captured == {"uid": "u1", "rid": "r1"} and "r1" in out


def test_remove_person_recommendation_scopes_to_user(monkeypatch):
    captured = {}
    monkeypatch.setattr(dashboard_tools.db, "delete_person_recommendation",
                        lambda uid, rid: captured.update(uid=uid, rid=rid))
    out = _tools()["remove_person_recommendation"].invoke({"recommendation_id": "r2"})
    assert captured == {"uid": "u1", "rid": "r2"}


def test_save_dashboard_brief_resolves_news_and_persists(monkeypatch):
    item = NewsItem(id="n1", title="ASU grant", url="https://x", summary="s")
    monkeypatch.setattr(dashboard_tools.db, "get_recent_news", lambda **k: [item])
    captured = {}
    monkeypatch.setattr(dashboard_tools.db, "upsert_dashboard_snapshot",
                        lambda uid, brief, news: captured.update(uid=uid, brief=brief, news=news))
    out = _tools()["save_dashboard_brief"].invoke({
        "brief_md": "# Today",
        "news": [{"id": "n1", "why_note": "relevant"}, {"id": "ghost", "why_note": "x"}],
    })
    assert captured["uid"] == "u1" and captured["brief"] == "# Today"
    assert len(captured["news"]) == 1  # unknown id dropped
    assert captured["news"][0]["url"] == "https://x"
    assert captured["news"][0]["why_note"] == "relevant"
    assert "1" in out
