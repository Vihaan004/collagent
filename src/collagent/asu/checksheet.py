"""Fetch an ASU checksheet URL and render its requirement tables to clean
markdown, cached in-memory. No Playwright, no structured schema — the page's
own text is the source of truth (see the 2026-06-24 spec)."""
from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
# "3 Credit Hours Minimum Grade:C" trails every requirement label — drop it.
_CREDIT_TAIL = re.compile(r"\s*\d+(?:\.\d+)?\s*Credit Hours.*$", re.IGNORECASE | re.DOTALL)
_WS = re.compile(r"\s+")
_CACHE: dict[str, str] = {}


def _clean(text: str) -> str:
    return _WS.sub(" ", text.replace("\xa0", " ")).strip()


def render_checksheet_markdown(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    lines: list[str] = []
    for tr in soup.find_all("tr"):
        sub = tr.find("td", class_="subsection-name")
        if sub is not None:
            lines.append(f"\n## {_clean(sub.get_text())}")
            continue
        if "checksheet-requirement" not in (tr.get("class") or []):
            continue
        tds = tr.find_all("td", recursive=False)
        if not tds:
            continue
        label = _clean(_CREDIT_TAIL.sub("", tds[0].get_text()))
        if not label:
            continue
        credits = _clean(tds[2].get_text()) if len(tds) > 2 else ""
        lines.append(f"- {label}" + (f" — {credits} cr" if credits else ""))
    return "\n".join(lines).strip()


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
