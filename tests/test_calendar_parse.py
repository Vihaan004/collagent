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
