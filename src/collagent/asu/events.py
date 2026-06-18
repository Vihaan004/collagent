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


def parse_gcal_link(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    a = soup.find("a", href=_GCAL_HREF)
    if not a:
        return {}
    q = parse_qs(urlparse(a["href"]).query)  # parse_qs URL-decodes and maps + -> space
    tz = ZoneInfo((q.get("ctz") or ["America/Phoenix"])[0])
    starts_at = ends_at = None
    if q.get("dates"):
        parts = q["dates"][0].split("/")
        starts_at = _parse_gcal_dt(parts[0], tz)
        if len(parts) > 1:
            ends_at = _parse_gcal_dt(parts[1], tz)
    details_html = (q.get("details") or [""])[0]
    description = BeautifulSoup(details_html, "html.parser").get_text(" ", strip=True) or None
    return {
        "title": (q.get("text") or [None])[0],
        "starts_at": starts_at,
        "ends_at": ends_at,
        "description": description,
        "location": (q.get("location") or [None])[0],
    }
