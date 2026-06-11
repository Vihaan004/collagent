"""Capture rendered roadmap text for tests. Run once (network + browser required).

Note: year 2025 returns "Major Map Unavailable" without authentication (CAS-gated).
      year 2024 is publicly accessible and has the same data structure.
"""
from pathlib import Path

from collagent.asu.majormap import render_roadmap_text

OUT = Path("tests/fixtures/roadmap_escsebs_2024.txt")

if __name__ == "__main__":
    text = render_roadmap_text("ESCSEBS", "2024")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {len(text)} chars to {OUT}")
