# tests/test_news_parse.py
from collagent.asu import news

SAMPLE = {
    "results": [
        {"title": "ASU lands $10M chip grant", "url": "https://news.asu.edu/chip",
         "content": "ASU secured funding for...", "score": 0.96,
         "published_date": "Tue, 17 Jun 2026 00:00:00 GMT"},
        {"title": "Advent Lab researchers honored", "url": "https://news.asu.edu/advent",
         "content": "Two researchers...", "score": 0.91},
        {"title": "", "url": "https://x/empty"},          # missing title -> dropped
        {"title": "No URL", "url": ""},                    # missing url -> dropped
    ]
}


def test_parse_news_maps_and_drops_incomplete():
    rows = news.parse_news_results(SAMPLE)
    assert len(rows) == 2
    first = rows[0]
    assert first["source"] == "tavily"
    assert first["source_key"] == "https://news.asu.edu/chip"
    assert first["title"] == "ASU lands $10M chip grant"
    assert first["summary"] == "ASU secured funding for..."
    assert first["published_at"] == "2026-06-17T00:00:00+00:00"  # RFC-2822 -> ISO
    assert first["raw"]["score"] == 0.96
    # missing published_date tolerated
    assert rows[1]["published_at"] is None


def test_fetch_news_dedupes_by_url(monkeypatch):
    class _Resp:
        status_code = 200
        def json(self):
            return {"results": [
                {"title": "Dup", "url": "https://news.asu.edu/dup", "content": "a"},
            ]}

    class _Client:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, *a, **k): return _Resp()

    monkeypatch.setattr(news.httpx, "Client", _Client)
    rows = news.fetch_news(queries=["q1", "q2"], api_key="tvly-test")
    assert len(rows) == 1  # same url across both queries collapses
    assert rows[0]["url"] == "https://news.asu.edu/dup"


def test_fetch_news_no_key_returns_empty(monkeypatch):
    # No key -> graceful no-op (Tavily not configured yet)
    rows = news.fetch_news(queries=["q"], api_key="")
    assert rows == []
