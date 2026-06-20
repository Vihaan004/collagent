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


def _mdy(text: str) -> str:
    return datetime.strptime(text, "%m/%d/%Y").date().isoformat()


def parse_session_spans(text: str) -> dict[str, tuple[str, str]]:
    """From a term's session-summary text, map 'A'/'B'/'C' -> (start_iso, end_iso)."""
    out: dict[str, tuple[str, str]] = {}
    for sess, start, end in _SESSION_SPAN.findall(text or ""):
        out[sess] = (_mdy(start), _mdy(end))
    return out


def parse_terms(html: str) -> list[dict]:
    """Each term -> {term, term_id, span (start_iso, end_iso), table (bs4 Tag|None)}.
    `span` is the earliest session start .. latest session end (used to pick the
    current term). Terms with no parseable session dates get span (None, None)."""
    soup = BeautifulSoup(html, "html.parser")
    terms: list[dict] = []
    for h2 in soup.select("h2.calhd"):
        anchor = h2.find("a")
        term_id = anchor.get("id") if anchor else None
        term_name = h2.get_text(" ", strip=True)
        sessions_text = ""
        table = None
        for sib in h2.next_siblings:
            name = getattr(sib, "name", None)
            if name == "h2" and "calhd" in (sib.get("class") or []):
                break
            if name == "div" and "Session" in sib.get_text():
                sessions_text += " " + sib.get_text(" ", strip=True)
            if name == "table" and "acad" in (sib.get("class") or []):
                table = sib
                break
        spans = parse_session_spans(sessions_text)
        if spans:
            starts = [s for s, _ in spans.values()]
            ends = [e for _, e in spans.values()]
            span = (min(starts), max(ends))
        else:
            span = (None, None)
        terms.append({"term": term_name, "term_id": term_id, "span": span, "table": table})
    return terms


def select_current_term(spans: dict[str, tuple[str, str]], today: str) -> str:
    """Pick the term whose span contains `today`; else the earliest upcoming term;
    else the last listed term. `spans` preserves page order."""
    for term, (start, end) in spans.items():
        if start and end and start <= today <= end:
            return term
    upcoming = sorted((start, term) for term, (start, _e) in spans.items() if start and start > today)
    if upcoming:
        return upcoming[0][1]
    return list(spans)[-1]
