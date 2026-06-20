# tests/test_api_news.py
from collagent.api.routes import news as news_routes
from collagent.models import NewsItem

ITEM = NewsItem(id="n1", title="ASU lands grant", url="https://news.asu.edu/chip",
                summary="snippet")


def test_get_news(client, monkeypatch):
    monkeypatch.setattr(news_routes.db, "get_recent_news", lambda **k: [ITEM])
    res = client.get("/api/news")
    assert res.status_code == 200
    assert res.json()[0]["title"] == "ASU lands grant"


def test_refresh_news_fetches_then_upserts(client, monkeypatch):
    calls = []
    monkeypatch.setattr(news_routes, "fetch_news",
                        lambda: calls.append("fetch") or [{"source": "tavily",
                        "source_key": "https://news.asu.edu/chip", "title": "ASU lands grant",
                        "url": "https://news.asu.edu/chip", "summary": "snippet",
                        "published_at": None, "raw": {}}])
    monkeypatch.setattr(news_routes.db, "upsert_news_items", lambda rows: calls.append("upsert"))
    monkeypatch.setattr(news_routes.db, "get_recent_news", lambda **k: [ITEM])
    res = client.post("/api/news/refresh", json={})
    assert res.status_code == 200
    assert calls == ["fetch", "upsert"]
    assert res.json()[0]["title"] == "ASU lands grant"


def test_news_unauthenticated_401():
    from fastapi.testclient import TestClient

    from collagent.api.main import app

    assert TestClient(app).get("/api/news").status_code == 401
