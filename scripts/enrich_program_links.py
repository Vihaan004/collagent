"""One-time, offline: add `checksheet_url` to each program in
data/asu_programs.json by discovering it from the program's detail page.
Re-run when ASU publishes a new catalog year.

Run: uv run python scripts/enrich_program_links.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

DATA = Path(__file__).resolve().parents[1] / "data" / "asu_programs.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
DETAIL = "https://degrees.apps.asu.edu/bachelors/major/ASU00/{code}/{slug}"
CHECKSHEET_HREF = re.compile(r"/checksheet/\d{4}/[A-Z]+/[A-Z0-9]+/\w+")


def discover(client: httpx.Client, code: str, slug: str) -> str | None:
    r = client.get(DETAIL.format(code=code, slug=slug))
    if r.status_code != 200:
        return None
    m = CHECKSHEET_HREF.search(r.text)
    return f"https://degrees.apps.asu.edu{m.group(0)}" if m else None


def main() -> None:
    programs = json.loads(DATA.read_text(encoding="utf-8"))
    ok, failures = 0, []
    with httpx.Client(headers=UA, timeout=30, follow_redirects=True) as client:
        for p in programs:
            url = discover(client, p["code"], p["slug"])
            if url:
                p["checksheet_url"] = url
                ok += 1
            else:
                failures.append(p["code"])
            print(f"{p['code']:<12} {'OK' if url else 'FAIL'}")
    DATA.write_text(json.dumps(programs, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\n{ok}/{len(programs)} linked. failures: {failures}")


if __name__ == "__main__":
    main()
