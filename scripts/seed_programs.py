"""One-shot: crawl ASU interest-area listings into data/asu_programs.json."""
import json

from collagent.asu.programs import DATA_PATH, fetch_all_programs

if __name__ == "__main__":
    programs = fetch_all_programs()
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(programs, indent=1), encoding="utf-8")
    print(f"wrote {len(programs)} programs to {DATA_PATH}")
