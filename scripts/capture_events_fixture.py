# scripts/capture_events_fixture.py
"""Smoke-capture: fetch a real events window and print a summary. Network required.
Run manually to verify ingestion works against the live site."""
from collagent.asu.events import fetch_upcoming_events

if __name__ == "__main__":
    rows = fetch_upcoming_events(max_events=10)
    print(f"fetched {len(rows)} events")
    for r in rows[:5]:
        print(f"  - {r['title']} @ {r['starts_at']} ({r['location']})")
