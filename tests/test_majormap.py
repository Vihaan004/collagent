import os
from pathlib import Path

import pytest

from collagent.asu.majormap import ExtractedMajorMap, extract_major_map

# Note: year 2025 ASU major map requires CAS authentication — fixture uses 2024 catalog
# which has identical structure and is publicly accessible.
FIXTURE = Path("tests/fixtures/roadmap_escsebs_2024.txt")


def test_extracted_schema_round_trip():
    m = ExtractedMajorMap(
        program_name="Computer Science, BS",
        courses=[{"term_number": 1, "title": "Programming", "course_code": "CSE 110"}],
    )
    assert m.courses[0].credits is None and m.courses[0].term_number == 1


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") and not os.getenv("LLM_API_KEY"),
    reason="integration: needs LLM key",
)
def test_extraction_on_real_fixture():
    result = extract_major_map(FIXTURE.read_text(encoding="utf-8"))
    assert len(result.courses) >= 20
    codes = {c.course_code for c in result.courses if c.course_code}
    assert "CSE 110" in codes
    assert {c.term_number for c in result.courses} >= {1, 2, 3, 4}
