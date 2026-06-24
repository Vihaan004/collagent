import json

from collagent.asu import programs

LISTING_SNIPPET = """
<html><body>
<a href="/bachelors/major/ASU00/ESCSEBS/computer-science">Computer Science</a>
<a href="/bachelors/major/ASU00/ESCSEBS#accelerateDeg">Accelerated</a>
<a href="/bachelors/major/ASU00/ASPGSPPBS/psychology-positive-psychology">Psychology (Positive Psychology)</a>
<a href="/somewhere/else">Not a major</a>
</body></html>
"""


def test_parse_major_links_extracts_codes_and_names():
    result = programs.parse_major_links(LISTING_SNIPPET)
    codes = {p["code"]: p for p in result}
    assert codes["ESCSEBS"]["name"] == "Computer Science"
    assert codes["ESCSEBS"]["slug"] == "computer-science"
    assert "ASPGSPPBS" in codes
    assert len(result) == 2  # anchor-only and non-major links ignored


def test_search_programs_substring_beats_fuzzy(tmp_path, monkeypatch):
    data = [
        {"code": "ESCSEBS", "slug": "computer-science", "name": "Computer Science"},
        {"code": "ESCSEEBSE", "slug": "computer-systems-engineering", "name": "Computer Systems Engineering"},
        {"code": "ASPGSPPBS", "slug": "psychology", "name": "Psychology"},
    ]
    path = tmp_path / "programs.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(programs, "DATA_PATH", path)

    results = programs.search_programs("computer sys")
    assert results[0]["code"] == "ESCSEEBSE"
    results = programs.search_programs("psychology")
    assert results[0]["code"] == "ASPGSPPBS"


def test_search_endpoint(client, monkeypatch):
    monkeypatch.setattr(
        "collagent.api.routes.programs.search_programs",
        lambda q: [{"code": "ESCSEBS", "slug": "computer-science", "name": "Computer Science"}],
    )
    res = client.get("/api/programs/search?q=computer")
    assert res.status_code == 200 and res.json()[0]["code"] == "ESCSEBS"


def test_get_checksheet_url(tmp_path, monkeypatch):
    data = [
        {"code": "BAACCBS", "slug": "accountancy", "name": "Accountancy,BS",
         "checksheet_url": "https://degrees.apps.asu.edu/checksheet/2026/CBA/BAACCBS/null"},
        {"code": "ZZZ", "slug": "z", "name": "Z"},  # no checksheet_url
    ]
    path = tmp_path / "programs.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(programs, "DATA_PATH", path)
    programs._load_programs_cached.cache_clear()

    assert programs.get_checksheet_url("BAACCBS").endswith("/BAACCBS/null")
    assert programs.get_checksheet_url("ZZZ") is None    # present, no link
    assert programs.get_checksheet_url("NOPE") is None    # absent
