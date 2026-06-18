# tests/test_events_parse.py
from collagent.asu import events

LISTING_SNIPPET = """
<html><body>
<a href="/event/intro-to-fpgas?eventDate=2026-06-20&id=3">Intro to FPGAs</a>
<a href="/event/intro-to-fpgas?eventDate=2026-06-20&id=3">Intro to FPGAs (dup)</a>
<a href="/event/career-fair?eventDate=2026-06-22&id=0">Career Fair</a>
<a href="/about">Not an event</a>
</body></html>
"""

DETAIL_SNIPPET = """
<html><body>
<a href="https://calendar.google.com/calendar/render?action=TEMPLATE&dates=20260620T140000/20260620T160000&ctz=America/Phoenix&text=Intro+to+FPGAs&details=%3Cp%3ELearn+about+FPGAs%3C%2Fp%3E&location=Tempe+Campus">Add to Google Calendar</a>
</body></html>
"""

ALLDAY_SNIPPET = """
<a href="https://calendar.google.com/calendar/render?dates=20260620/20260621&text=Art+Show">x</a>
"""


def test_parse_event_links_dedupes_and_filters():
    result = events.parse_event_links(LISTING_SNIPPET)
    keys = {(p["slug"], p["event_date"]) for p in result}
    assert ("intro-to-fpgas", "2026-06-20") in keys
    assert ("career-fair", "2026-06-22") in keys
    assert len(result) == 2  # dup collapsed, /about ignored
    assert result[0]["url"] == "https://asuevents.asu.edu/event/intro-to-fpgas?eventDate=2026-06-20&id=3"


def test_parse_gcal_link_extracts_fields():
    g = events.parse_gcal_link(DETAIL_SNIPPET)
    assert g["title"] == "Intro to FPGAs"
    assert g["starts_at"] == "2026-06-20T14:00:00-07:00"
    assert g["ends_at"] == "2026-06-20T16:00:00-07:00"
    assert g["description"] == "Learn about FPGAs"
    assert g["location"] == "Tempe Campus"


def test_parse_gcal_link_handles_all_day():
    g = events.parse_gcal_link(ALLDAY_SNIPPET)
    assert g["title"] == "Art Show"
    assert g["starts_at"] == "2026-06-20T00:00:00-07:00"
    assert g["ends_at"] == "2026-06-21T00:00:00-07:00"


def test_parse_gcal_link_missing_returns_empty():
    assert events.parse_gcal_link("<html><body>no link</body></html>") == {}


def test_parse_gcal_link_unknown_timezone_falls_back_to_phoenix():
    html = (
        '<a href="https://calendar.google.com/calendar/render'
        '?dates=20260620T140000/20260620T160000&ctz=Not/AZone&text=X">x</a>'
    )
    g = events.parse_gcal_link(html)
    assert g["starts_at"] == "2026-06-20T14:00:00-07:00"  # fell back to America/Phoenix


def test_parse_gcal_link_empty_dates_yields_none():
    html = '<a href="https://calendar.google.com/calendar/render?dates=&text=X">x</a>'
    g = events.parse_gcal_link(html)
    assert g["title"] == "X"
    assert g["starts_at"] is None and g["ends_at"] is None
