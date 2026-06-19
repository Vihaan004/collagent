# src/collagent/asu/people.py
"""iSearch faculty/staff ingestion. Pure parsing (parse_people) is unit-tested;
fetch_faculty/search_faculty are network-bound and verified via the capture script.
Source: GET https://search.asu.edu/api/v1/webdir-profiles/faculty-staff?query=...
Every API field is wrapped in a {"raw": <value>} envelope."""
import re

import httpx

from collagent.models import Profile

API_URL = "https://search.asu.edu/api/v1/webdir-profiles/faculty-staff"
PROFILE_BASE = "https://search.asu.edu/profile/"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "application/json"}
_FACULTY_HINT = re.compile(r"faculty|professor|lecturer", re.I)


def _raw(field):
    return field.get("raw") if isinstance(field, dict) else field


def _as_list(value) -> list[str]:
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    return [str(x).strip() for x in items if x is not None and str(x).strip()]


def _first(value) -> str | None:
    items = _as_list(value)
    return items[0] if items else None


def _text(value) -> str | None:
    items = _as_list(value)
    return "; ".join(items) if items else None


def _looks_like_faculty(empl_classes: list[str], title: str | None, expertise: list[str]) -> bool:
    if any(_FACULTY_HINT.search(c) for c in empl_classes):
        return True
    if title and _FACULTY_HINT.search(title):
        return True
    return bool(expertise)


def parse_people(payload: dict, faculty_only: bool = True) -> list[dict]:
    """Map the iSearch response to the `people` row shape, deduping by asurite_id.
    Pure: no network. When faculty_only is True (ingestion, for mentor curation) rows
    that don't look like faculty/mentors are dropped; live name/topic lookups pass
    faculty_only=False so a directly-named person is never hidden by the filter."""
    rows: dict[str, dict] = {}
    for item in payload.get("results", []):
        def g(key):
            return _raw(item.get(key))

        asurite = g("asurite_id")
        name = g("display_name")
        if not asurite or not name:
            continue
        empl = _as_list(g("simplified_empl_classes"))
        title = _first(g("primary_title")) or _first(g("working_title"))
        expertise = _as_list(g("expertise_areas"))
        if faculty_only and not _looks_like_faculty(empl, title, expertise):
            continue
        eid = g("eid")
        profile_url = (
            f"{PROFILE_BASE}{eid}" if eid
            else f"https://search.asu.edu/?query={asurite}&searchType=people"
        )
        rows[asurite] = {
            "source": "asu_isearch",
            "source_person_key": asurite,
            "name": name,
            "email": g("email_address"),
            "title": title,
            "departments": _as_list(g("departments")),
            "expertise_areas": expertise,
            "research_interests": _text(g("research_interests")),
            "short_bio": _text(g("short_bio")),
            "profile_url": profile_url,
            "photo_url": g("photo_url"),
        }
    return list(rows.values())


def query_terms(profile: Profile | None) -> list[str]:
    """Seed iSearch queries from the student's interests + major (deduped, capped)."""
    if profile is None:
        return []
    raw = list(profile.interests)
    if profile.major_name:
        raw.append(profile.major_name)
    seen: set[str] = set()
    out: list[str] = []
    for term in raw:
        t = term.strip()
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
        if len(out) >= 6:
            break
    return out


def _get_profiles(
    client: httpx.Client, query: str, size: int, faculty_only: bool = True
) -> list[dict]:
    resp = client.get(
        API_URL,
        params={"sort-by": "", "query": query, "page": 1, "size": size, "client": "asuis"},
    )
    if resp.status_code != 200:
        return []
    return parse_people(resp.json(), faculty_only=faculty_only)


def fetch_faculty(query_list: list[str], per_term: int = 10) -> list[dict]:
    """Query the iSearch API once per term, parse, and dedupe by asurite_id.
    Resilient: a failing term is skipped rather than aborting ingestion."""
    rows: dict[str, dict] = {}
    with httpx.Client(headers=UA, timeout=15, follow_redirects=True) as client:
        for term in query_list:
            try:
                parsed = _get_profiles(client, term, per_term)
            except httpx.HTTPError:
                continue
            for row in parsed:
                rows[row["source_person_key"]] = row
    return list(rows.values())


# Filler/question words the LLM tends to forward from the user's phrasing. The iSearch
# API matches query tokens conjunctively, so a stray "who"/"is" yields zero rows even
# for a valid name — we strip these and retry. Domain words (professor, robotics) are
# intentionally kept; they often match a title/expertise field.
_QUERY_STOPWORDS = frozenset({
    "who", "whos", "is", "are", "was", "the", "a", "an", "me", "my", "about", "tell",
    "find", "what", "whats", "search", "for", "please", "can", "could", "you", "show",
    "of", "to", "do", "does", "know", "any", "someone", "person", "people", "professor",
    # Org words: the directory is ASU-only, so these never narrow a match — they only
    # break the conjunctive token search when the agent appends them to a name.
    "asu", "arizona", "state", "university",
})


def _clean_query(query: str) -> str:
    """Drop filler/question/org words and punctuation, leaving likely name/topic tokens."""
    tokens = re.findall(r"[A-Za-z0-9'-]+", query)
    kept = [t for t in tokens if t.lower() not in _QUERY_STOPWORDS]
    return " ".join(kept)


def _query_candidates(query: str) -> list[str]:
    """Ordered, deduped query variants to try against the AND-matching iSearch API.
    The chat agent often appends the org name or a guessed topic to a person's name;
    since iSearch matches every token conjunctively, a single noisy token yields zero
    rows. We progressively relax: raw -> filler/org-stripped -> the first two tokens
    (a directed person lookup puts the name first), stopping at the first non-empty hit."""
    candidates = [query.strip()]
    cleaned = _clean_query(query)
    if cleaned:
        candidates.append(cleaned)
        tokens = cleaned.split()
        if len(tokens) > 2:
            candidates.append(" ".join(tokens[:2]))
    seen: set[str] = set()
    out: list[str] = []
    for c in candidates:
        key = c.lower()
        if c and key not in seen:
            seen.add(key)
            out.append(c)
    return out


def search_faculty(query: str, size: int = 8) -> list[dict]:
    """Single live directory query for the chat search_people tool. Returns whoever the
    directory matches (faculty_only=False) — a directly-named person must never be hidden
    by the mentor filter. The iSearch API AND-matches query tokens, so a noisy query
    ("Aman Arora cybersecurity ASU") returns nothing; we try progressively relaxed
    variants (see _query_candidates) and return the first non-empty result."""
    with httpx.Client(headers=UA, timeout=15, follow_redirects=True) as client:
        try:
            for candidate in _query_candidates(query):
                results = _get_profiles(client, candidate, size, faculty_only=False)
                if results:
                    return results
            return []
        except httpx.HTTPError:
            return []
