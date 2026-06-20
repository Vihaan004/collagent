# tests/test_calendar_parse.py
import pathlib

from collagent.asu import calendar as cal

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "registrar_calendar.html"


def test_parse_date_full_month():
    assert cal.parse_date("February 5, 2026") == "2026-02-05"
    assert cal.parse_date("  May 18, 2026 ") == "2026-05-18"
    assert cal.parse_date("TBD") is None


def test_cell_dates_single_and_range():
    assert cal.cell_dates("Session A May 18, 2026") == ("2026-05-18", None)
    assert cal.cell_dates("March 8, 2027 – March 14, 2027") == ("2027-03-08", "2027-03-14")
    assert cal.cell_dates("\xa0") == (None, None)  # &nbsp;


def test_categorize():
    assert cal.categorize("Drop Deadline") == "deadline"
    assert cal.categorize("Last day to add") == "deadline"
    assert cal.categorize("Memorial Day Observed") == "holiday"
    assert cal.categorize("Spring Break") == "holiday"
    assert cal.categorize("Registration Dates Begin") == "registration"
    assert cal.categorize("Classes Begin") == "academic"
    assert cal.categorize("Schedule of Classes Available") == "registration"
    assert cal.categorize("Some random note") == "other"


def test_parse_session_spans():
    spans = cal.parse_session_spans(
        "Session A: Monday, 5/18/2026 – Friday, 6/26/2026  "
        "Session B: 7/1/2026 – 8/11/2026  Session C: 5/18/2026 – 7/10/2026"
    )
    assert spans["A"] == ("2026-05-18", "2026-06-26")
    assert spans["B"] == ("2026-07-01", "2026-08-11")
    assert spans["C"] == ("2026-05-18", "2026-07-10")


def test_parse_terms_from_fixture():
    terms = cal.parse_terms(FIXTURE.read_text(encoding="utf-8"))
    names = [t["term"] for t in terms]
    assert "Summer 2026" in names
    summer = next(t for t in terms if t["term"] == "Summer 2026")
    assert summer["span"][0] == "2026-05-18"
    assert summer["span"][1] >= "2026-08-11"


def test_select_current_term_in_session():
    spans = {"Summer 2026": ("2026-05-18", "2026-08-11"),
             "Fall 2026": ("2026-08-20", "2026-12-18")}
    assert cal.select_current_term(spans, "2026-06-20") == "Summer 2026"


def test_select_current_term_between_picks_next():
    spans = {"Summer 2026": ("2026-05-18", "2026-08-11"),
             "Fall 2026": ("2026-08-20", "2026-12-18")}
    assert cal.select_current_term(spans, "2026-08-15") == "Fall 2026"


def test_select_current_term_after_all_picks_last():
    spans = {"Summer 2026": ("2026-05-18", "2026-08-11")}
    assert cal.select_current_term(spans, "2027-01-01") == "Summer 2026"


def test_parse_term_items_from_fixture():
    terms = cal.parse_terms(FIXTURE.read_text(encoding="utf-8"))
    summer = next(t for t in terms if t["term"] == "Summer 2026")
    items = cal.parse_term_items(summer)
    by_title = {}
    for it in items:
        by_title.setdefault(it["title"], []).append(it)

    # single-date row -> one 'whole' item
    sched = by_title["Schedule of Classes Available"]
    assert len(sched) == 1
    assert sched[0]["session"] == "whole" and sched[0]["date_start"] == "2026-02-05"

    # per-session row -> one item per session with its own date
    begins = {it["session"]: it["date_start"] for it in by_title["Classes Begin"]}
    assert begins["A"] == "2026-05-18"
    assert begins["B"] == "2026-07-01"
    assert begins["C"] == "2026-05-18"

    # every item carries term + a category
    assert all(it["term"] == "Summer 2026" for it in items)
    assert all(it["category"] for it in items)


def test_fetch_calendar_assembles_current_term(monkeypatch):
    html = FIXTURE.read_text(encoding="utf-8")

    class _Resp:
        status_code = 200
        text = html
        encoding = "utf-8"

    class _Client:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, *a, **k): return _Resp()

    monkeypatch.setattr(cal.httpx, "Client", _Client)
    rows = cal.fetch_calendar(today="2026-06-20")
    assert rows, "should return current-term items"
    assert {r["term"] for r in rows} == {"Summer 2026"}  # only the current term
    titles = {r["title"] for r in rows}
    assert "Classes Begin" in titles
    assert all("session" in r and "title" in r and "category" in r for r in rows)
