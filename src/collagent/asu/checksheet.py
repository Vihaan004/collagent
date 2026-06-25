"""Fetch an ASU checksheet URL and render its requirement tables to clean
markdown, cached in-memory. No Playwright, no structured schema — the page's
own text is the source of truth (see the 2026-06-24 spec)."""
from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
_WS = re.compile(r"\s+")
_CACHE: dict[str, str] = {}
# Requirements offering more alternatives than this are elective/specialization
# pools — collapse them to a count instead of dumping every option (the dumps
# were hundreds of duplicated courses, useless as agent context).
_POOL_THRESHOLD = 8


def _clean(text: str) -> str:
    return _WS.sub(" ", text.replace("\xa0", " ")).strip()


def render_checksheet_markdown(html: str) -> str:
    """Render a checksheet to a lean course list: section headers + each
    requirement's course(s). Courses come only from `a.ttCourse` anchors (each
    is "CODE Title"), so prose notes, regulations, and GPA rules — which live in
    sibling elements with no anchor — are dropped. Large pools collapse to a
    count. The goal is to highlight a program's courses, not reproduce the page."""
    soup = BeautifulSoup(html, "html.parser")
    out: list[str] = []
    section: str | None = None
    section_emitted = False
    for tr in soup.find_all("tr"):
        sub = tr.find("td", class_="subsection-name")
        if sub is not None:
            section = _clean(sub.get_text())
            section_emitted = False
            continue
        if "checksheet-requirement" not in (tr.get("class") or []):
            continue
        courses: list[str] = []
        for a in tr.select("a.ttCourse"):
            c = _clean(a.get_text())
            if c and c not in courses:  # dedupe within the row
                courses.append(c)
        if not courses:
            continue  # note / regulation / placement row — no course, skip
        tds = tr.find_all("td", recursive=False)
        credits = _clean(tds[2].get_text()) if len(tds) > 2 else ""
        cr = f" — {credits} cr" if credits else ""
        if len(courses) > _POOL_THRESHOLD:
            line = f"- Elective — choose from {len(courses)} courses{cr}"
        else:
            line = f"- {' OR '.join(courses)}{cr}"
        if section is not None and not section_emitted:
            out.append(f"\n## {section}")
            section_emitted = True
        out.append(line)
    return "\n".join(out).strip()


def fetch_curriculum(url: str) -> str:
    if url not in _CACHE:
        resp = httpx.get(url, headers=UA, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        _CACHE[url] = render_checksheet_markdown(resp.text)
    return _CACHE[url]


def prewarm(urls: list[str]) -> None:
    """Optional: fetch a set of checksheets ahead of a demo. Best-effort."""
    for u in urls:
        try:
            fetch_curriculum(u)
        except Exception:
            pass
