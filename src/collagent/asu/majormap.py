from __future__ import annotations

from pydantic import BaseModel, Field

from collagent.graph import get_model

ROADMAP_URL = "https://webapp4.asu.edu/programs/t5/roadmaps/ASU00/{code}/null/ALL/{year}"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


class ExtractedCourse(BaseModel):
    term_number: int = Field(description="Term/semester number on the map, 1-8")
    course_code: str | None = Field(
        default=None, description='Catalog code like "CSE 110"; null for non-course requirements'
    )
    title: str = Field(description="Course or requirement title")
    credits: float | None = Field(default=None, description="Credit hours")
    requirement_note: str | None = Field(
        default=None, description='Notes like "Critical course" or "General Studies: HU"'
    )


class ExtractedMajorMap(BaseModel):
    program_name: str
    courses: list[ExtractedCourse]


_EXTRACT_PROMPT = """You are given the visible text of an ASU major map (degree roadmap) page.
Extract every course and requirement row into structured data.

Rules:
- term_number: the term/semester block the row appears under (Term 1 = 1, ... Term 8 = 8).
- course_code: the catalog code (e.g. "CSE 110", "MAT 265"). If the row is a generic
  requirement (e.g. "Humanities, Arts and Design (HU)", "Elective"), set it to null.
- title: the course/requirement name without the code.
- credits: the credit hours number for the row, if shown.
- requirement_note: flags like "Critical course", General Studies codes, or "Minimum 2.00 GPA" notes.
- Include electives and general-studies placeholder rows. Do not invent rows.
"""


def render_roadmap_text(code: str, year: str) -> str:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright

    url = ROADMAP_URL.format(code=code, year=year)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto(url, wait_until="networkidle", timeout=60_000)
        # Wait for actual course codes to appear (JS-loaded content)
        try:
            page.wait_for_selector("text=/[A-Z]{3} [0-9]{3}/", timeout=30_000)
        except PlaywrightTimeoutError:
            pass  # Proceed even if the selector times out; fallback below
        try:
            text = page.inner_text("#roadmap_middle_section")
        except PlaywrightError:
            # Fallback: selector missing — use full body text
            text = page.inner_text("body")
        browser.close()
    return text


def extract_major_map(roadmap_text: str) -> ExtractedMajorMap:
    llm = get_model().with_structured_output(ExtractedMajorMap)
    return llm.invoke(
        [("system", _EXTRACT_PROMPT), ("user", roadmap_text)]
    )


def build_major_map(code: str, year: str) -> ExtractedMajorMap:
    return extract_major_map(render_roadmap_text(code, year))
