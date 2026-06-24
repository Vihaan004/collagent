import json
import re
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "asu_programs.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
LIST_URL = "https://degrees.apps.asu.edu/bachelors/major-list/interest-area/{n:02d}"
MAJOR_HREF = re.compile(r"^/bachelors/major/ASU00/([A-Z0-9]+)/([a-z0-9-]+)$")


def parse_major_links(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, dict] = {}
    for a in soup.find_all("a", href=True):
        m = MAJOR_HREF.match(a["href"])
        if not m:
            continue
        code, slug = m.groups()
        name = a.get_text(strip=True)
        if name and code not in found:
            found[code] = {"code": code, "slug": slug, "name": name}
    return list(found.values())


def fetch_all_programs() -> list[dict]:
    found: dict[str, dict] = {}
    with httpx.Client(headers=UA, timeout=30, follow_redirects=True) as client:
        for n in range(1, 16):
            resp = client.get(LIST_URL.format(n=n))
            if resp.status_code != 200:
                continue
            for p in parse_major_links(resp.text):
                found.setdefault(p["code"], p)
    return sorted(found.values(), key=lambda p: p["name"])


def load_programs() -> list[dict]:
    # Tiny catalog (~450 rows); cache keyed on path so tests can swap DATA_PATH.
    return _load_programs_cached(DATA_PATH)


@lru_cache(maxsize=2)
def _load_programs_cached(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def search_programs(query: str, limit: int = 10) -> list[dict]:
    q = query.lower().strip()

    def score(p: dict) -> float:
        name = p["name"].lower()
        if q in name:
            return 1.0 + len(q) / len(name)
        return SequenceMatcher(None, q, name).ratio()

    return sorted(load_programs(), key=score, reverse=True)[:limit]


def get_checksheet_url(code: str) -> str | None:
    for p in load_programs():
        if p.get("code") == code:
            return p.get("checksheet_url")
    return None
