# src/collagent/asu/calendar.py
"""ASU academic-calendar ingestion: current term only, deterministic (no LLM).
Pure parsers over the registrar HTML + a resilient network fetch. Mirrors the
BeautifulSoup pattern in asu/events.py."""
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

URL = "https://registrar.asu.edu/academic-calendar"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

_FULL_DATE = re.compile(r"[A-Z][a-z]+ \d{1,2}, \d{4}")
_MDY = re.compile(r"\d{1,2}/\d{1,2}/\d{4}")
_SESSION = re.compile(r"Session ([ABC])")
_SESSION_SPAN = re.compile(r"Session ([ABC]):\D*?(\d{1,2}/\d{1,2}/\d{4})\D+?(\d{1,2}/\d{1,2}/\d{4})")


def parse_date(text: str) -> str | None:
    """'February 5, 2026' -> '2026-02-05'. Returns None if not a full month-day-year date."""
    m = _FULL_DATE.search(text or "")
    if not m:
        return None
    try:
        return datetime.strptime(m.group(0), "%B %d, %Y").date().isoformat()
    except ValueError:
        return None


def cell_dates(text: str) -> tuple[str | None, str | None]:
    """Extract (start, end) from a table-cell's text. End is None unless the cell
    contains a second full date (a range like 'March 8, 2027 – March 14, 2027')."""
    found = _FULL_DATE.findall(text or "")
    if not found:
        return (None, None)
    start = parse_date(found[0])
    end = parse_date(found[1]) if len(found) > 1 else None
    return (start, end)


def categorize(title: str) -> str:
    t = (title or "").lower()
    if any(w in t for w in ("deadline", "last day", "due")):
        return "deadline"
    if any(w in t for w in ("holiday", "observed", "no classes", "break", "recess")):
        return "holiday"
    if any(w in t for w in ("registration", "enroll", "schedule of classes")):
        return "registration"
    if any(w in t for w in ("classes begin", "classes end", "commencement", "final exam", "convocation")):
        return "academic"
    return "other"
