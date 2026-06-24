from pathlib import Path

import httpx

from collagent.asu import checksheet

FIXTURE = Path(__file__).parent / "fixtures" / "checksheet_baaccbs.html"


def test_render_extracts_sections_and_requirements():
    md = checksheet.render_checksheet_markdown(FIXTURE.read_text(encoding="utf-8"))
    assert "## Business Core" in md          # subsection header
    assert "FIN 300" in md and "OR FIN 303" in md  # OR-group kept as text
    assert "Expand all" not in md            # page chrome dropped
    assert "Credit Hours Minimum" not in md  # per-row boilerplate stripped


def test_fetch_curriculum_caches(monkeypatch):
    checksheet._CACHE.clear()
    calls = {"n": 0}

    def fake_get(url, **kw):
        calls["n"] += 1
        html = "<tr class='checksheet-requirement'><td>X 100 Foo</td><td>C</td><td>3</td></tr>"
        return httpx.Response(200, text=html, request=httpx.Request("GET", url))

    monkeypatch.setattr(checksheet.httpx, "get", fake_get)
    first = checksheet.fetch_curriculum("http://example/cs")
    second = checksheet.fetch_curriculum("http://example/cs")
    assert calls["n"] == 1          # second call served from cache
    assert first == second
    assert "X 100 Foo" in first
