# src/collagent/asu/events.py
import re
from datetime import datetime
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

BASE = "https://asuevents.asu.edu"
LIST_URL = BASE + "/?page={page}"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
_EVENT_HREF = re.compile(r"^/event/([a-z0-9-]+)\?eventDate=(\d{4}-\d{2}-\d{2})")
_GCAL_HREF = re.compile(r"calendar\.google\.com/calendar/render")


def parse_event_links(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    found: dict[tuple[str, str], dict] = {}
    for a in soup.find_all("a", href=True):
        m = _EVENT_HREF.match(a["href"])
        if not m:
            continue
        slug, date = m.groups()
        key = (slug, date)
        if key not in found:
            found[key] = {"slug": slug, "event_date": date, "url": BASE + a["href"]}
    return list(found.values())


def _parse_gcal_dt(value: str, tz: ZoneInfo) -> str:
    fmt = "%Y%m%dT%H%M%S" if "T" in value else "%Y%m%d"
    return datetime.strptime(value, fmt).replace(tzinfo=tz).isoformat()


def parse_gcal_link(html: str) -> dict[str, str | None]:
    soup = BeautifulSoup(html, "html.parser")
    a = soup.find("a", href=_GCAL_HREF)
    if not a:
        return {}
    q = parse_qs(urlparse(a["href"]).query)  # parse_qs URL-decodes and maps + -> space
    try:
        tz = ZoneInfo((q.get("ctz") or ["America/Phoenix"])[0])
    except KeyError:  # ZoneInfoNotFoundError subclasses KeyError
        tz = ZoneInfo("America/Phoenix")
    starts_at = ends_at = None
    dates = (q.get("dates") or [""])[0]
    if dates:
        parts = dates.split("/")
        try:
            starts_at = _parse_gcal_dt(parts[0], tz)
            if len(parts) > 1:
                ends_at = _parse_gcal_dt(parts[1], tz)
        except ValueError:  # malformed/empty date token
            starts_at = ends_at = None
    details_html = (q.get("details") or [""])[0]
    description = BeautifulSoup(details_html, "html.parser").get_text(" ", strip=True) or None
    return {
        "title": (q.get("text") or [None])[0],
        "starts_at": starts_at,
        "ends_at": ends_at,
        "description": description,
        "location": (q.get("location") or [None])[0],
    }


def fetch_upcoming_events(max_events: int = 40) -> list[dict]:
    """Crawl listing pages, then fetch each detail page and parse its gcal link.
    Network-bound; pure parsing logic lives in parse_event_links/parse_gcal_link.
    Resilient: a single failing page is skipped rather than aborting the crawl."""
    rows: list[dict] = []
    seen: set[str] = set()
    with httpx.Client(headers=UA, timeout=15, follow_redirects=True) as client:
        links: list[dict] = []
        for page in range(0, 5):
            try:
                resp = client.get(LIST_URL.format(page=page))
            except httpx.HTTPError:
                break
            if resp.status_code != 200:
                break
            page_links = parse_event_links(resp.text)
            if not page_links:
                break
            links.extend(page_links)
            if len(links) >= max_events:
                break
        for link in links[:max_events]:
            key = f"{link['slug']}:{link['event_date']}"
            if key in seen:
                continue
            seen.add(key)
            try:
                detail = client.get(link["url"])
            except httpx.HTTPError:
                continue
            if detail.status_code != 200:
                continue
            g = parse_gcal_link(detail.text)
            if not g.get("title"):
                continue
            rows.append({
                "source": "asu_events",
                "source_event_key": key,
                "title": g["title"],
                "description": g.get("description"),
                "starts_at": g.get("starts_at"),
                "ends_at": g.get("ends_at"),
                "location": g.get("location"),
                "url": link["url"],
            })
    return rows
