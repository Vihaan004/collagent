# scripts/capture_people_fixture.py
"""Smoke-capture: query the iSearch faculty API and print a summary. Network required.
Run manually to verify ingestion works against the live API."""
from collagent.asu.people import fetch_faculty

if __name__ == "__main__":
    rows = fetch_faculty(["machine learning", "computer architecture"], per_term=5)
    print(f"fetched {len(rows)} people")
    for r in rows[:5]:
        print(f"  - {r['name']} — {r['title']} ({', '.join(r['departments'])})")
        print(f"    expertise: {', '.join(r['expertise_areas'])}")
