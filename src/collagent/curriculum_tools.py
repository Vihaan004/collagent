"""Per-user tool: read an ASU program's official curriculum on demand."""
from langchain.tools import tool

from collagent import db
from collagent.asu.checksheet import fetch_curriculum
from collagent.asu.programs import get_checksheet_url


def make_curriculum_tools(user_id: str) -> list:
    @tool("read_curriculum")
    def read_curriculum(program_code: str | None = None) -> str:
        """Read an ASU bachelor's program's official course requirements
        (the degree checksheet) as text. Omit program_code to use the student's
        own major; pass a program_code (e.g. 'ESCSEBS') to inspect another
        program. To turn a program name into a code, use the program search tool."""
        code = program_code
        if code is None:
            profile = db.get_profile(user_id)
            code = profile.acad_plan_code if profile else None
            if not code:
                return ("No major on file yet — ask the student which program "
                        "they're in, then look up its code with program search.")
        url = get_checksheet_url(code)
        if not url:
            return f"No published curriculum found for program '{code}'."
        try:
            return fetch_curriculum(url)
        except Exception:
            return ("Couldn't load that curriculum right now (the ASU page was "
                    "unavailable). Try again in a moment.")

    return [read_curriculum]
