# src/collagent/asu/news.py
"""Open-web ASU news ingestion via the Tavily Search API. Global cache (news_items);
per-student tuning happens later in the orchestrator. Pure parser + resilient fetch."""
from datetime import datetime
from email.utils import parsedate_to_datetime

import httpx

from collagent.config import settings

SEARCH_URL = "https://api.tavily.com/search"
DEFAULT_QUERIES = [
    "Arizona State University news",
    "ASU research announcement",
    "ASU student opportunities",
]


def _parse_published(value: str | None) -> str | None:
    """Best-effort: ISO or RFC-2822 -> ISO string; None if absent/unparseable."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(value).isoformat()
    except (ValueError, TypeError):
        return None


def parse_news_results(data: dict) -> list[dict]:
    """Map a Tavily response into news_items rows. Drops results missing title/url."""
    rows: list[dict] = []
    for r in data.get("results", []):
        url = r.get("url")
        title = r.get("title")
        if not url or not title:
            continue
        rows.append({
            "source": "tavily",
            "source_key": url,
            "title": title,
            "url": url,
            "summary": r.get("content"),
            "published_at": _parse_published(r.get("published_date")),
            "raw": r,
        })
    return rows


def fetch_news(
    queries: list[str] | None = None,
    max_results: int = 5,
    api_key: str | None = None,
) -> list[dict]:
    """Query Tavily for recent ASU news across `queries`, dedupe by URL. Returns []
    when no API key is configured or on HTTP error (graceful, never raises)."""
    api_key = api_key if api_key is not None else settings.tavily_api_key
    if not api_key:
        return []
    queries = queries or DEFAULT_QUERIES
    by_url: dict[str, dict] = {}
    try:
        with httpx.Client(timeout=20) as client:
            for q in queries:
                resp = client.post(
                    SEARCH_URL,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"query": q, "topic": "news", "time_range": "week",
                          "max_results": max_results},
                )
                if resp.status_code != 200:
                    continue
                for row in parse_news_results(resp.json()):
                    by_url[row["source_key"]] = row
    except httpx.HTTPError:
        return list(by_url.values())
    return list(by_url.values())
