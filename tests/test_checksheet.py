from pathlib import Path

import httpx

from collagent.asu import checksheet

FIXTURE = Path(__file__).parent / "fixtures" / "checksheet_baaccbs.html"


def test_render_extracts_sections_and_courses():
    md = checksheet.render_checksheet_markdown(FIXTURE.read_text(encoding="utf-8"))
    assert "## Business Core" in md                       # subsection header
    assert "FIN 300 Fundamentals of Finance" in md        # course code + title
    assert "OR FIN 303" in md                             # OR-group kept
    assert "Expand all" not in md                         # page chrome dropped


def test_render_drops_prose_and_regulations():
    md = checksheet.render_checksheet_markdown(FIXTURE.read_text(encoding="utf-8"))
    assert "Career Navigation Course Sequence" not in md  # embedded note dropped
    assert "2.00 GPA" not in md                           # regulation row dropped
    assert "Mathematics Placement" not in md              # advisory note dropped
    assert "Credit Hours Minimum" not in md               # per-row boilerplate gone


def test_render_collapses_large_pools():
    anchors = "".join(f"<a class='ttCourse'>C{i} Course {i}</a>" for i in range(12))
    html = f"<tr class='checksheet-requirement'><td>{anchors}</td><td>C</td><td>3</td></tr>"
    md = checksheet.render_checksheet_markdown(html)
    assert "choose from 12 courses" in md
    assert "C0 Course 0" not in md   # individual pool options are not dumped


def test_render_skips_note_only_rows():
    html = "<tr class='checksheet-requirement'><td>Students must earn a 2.00 GPA.</td><td></td><td></td></tr>"
    assert checksheet.render_checksheet_markdown(html) == ""


def test_fetch_curriculum_caches(monkeypatch):
    checksheet._CACHE.clear()
    calls = {"n": 0}

    def fake_get(url, **kw):
        calls["n"] += 1
        html = "<tr class='checksheet-requirement'><td><a class='ttCourse'>X 100 Foo</a></td><td>C</td><td>3</td></tr>"
        return httpx.Response(200, text=html, request=httpx.Request("GET", url))

    monkeypatch.setattr(checksheet.httpx, "get", fake_get)
    first = checksheet.fetch_curriculum("http://example/cs")
    second = checksheet.fetch_curriculum("http://example/cs")
    assert calls["n"] == 1          # second call served from cache
    assert first == second
    assert "X 100 Foo" in first
