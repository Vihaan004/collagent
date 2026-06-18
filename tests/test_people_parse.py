# tests/test_people_parse.py
from collagent.asu import people
from collagent.models import Profile

# Trimmed to the fields parse_people reads; mirrors the real iSearch faculty-staff
# response shape where every value is wrapped in {"raw": ...}.
SAMPLE = {
    "results": [
        {  # faculty with expertise -> kept
            "asurite_id": {"raw": "bingsi"},
            "eid": {"raw": "123456"},
            "display_name": {"raw": "Bing Si"},
            "email_address": {"raw": "Bing.Si@asu.edu"},
            "primary_title": {"raw": ["Associate Professor"]},
            "departments": {"raw": ["School of Computing and Augmented Intelligence"]},
            "expertise_areas": {"raw": ["Machine Learning", "Data Mining"]},
            "research_interests": {"raw": None},
            "short_bio": {"raw": None},
            "photo_url": {"raw": "https://webapp4.asu.edu/photo-ws/directory_photo/123456"},
            "simplified_empl_classes": {"raw": ["Faculty"]},
        },
        {  # student worker, no expertise -> dropped
            "asurite_id": {"raw": "phjiang"},
            "eid": {"raw": "999"},
            "display_name": {"raw": "Patrick Jiang"},
            "email_address": {"raw": "phjiang@asu.edu"},
            "primary_title": {"raw": ["Student Worker IV"]},
            "departments": {"raw": None},
            "expertise_areas": {"raw": None},
            "simplified_empl_classes": {"raw": ["Student Worker"]},
        },
        {  # missing name -> skipped
            "asurite_id": {"raw": "noname"},
            "display_name": {"raw": None},
        },
    ]
}


def test_parse_people_keeps_faculty_unwraps_envelope():
    rows = people.parse_people(SAMPLE)
    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "asu_isearch"
    assert row["source_person_key"] == "bingsi"
    assert row["name"] == "Bing Si"
    assert row["email"] == "Bing.Si@asu.edu"
    assert row["title"] == "Associate Professor"
    assert row["departments"] == ["School of Computing and Augmented Intelligence"]
    assert row["expertise_areas"] == ["Machine Learning", "Data Mining"]
    assert row["profile_url"] == "https://search.asu.edu/profile/123456"


def test_parse_people_drops_staff_without_expertise():
    rows = people.parse_people(SAMPLE)
    keys = {r["source_person_key"] for r in rows}
    assert "phjiang" not in keys
    assert "noname" not in keys


def test_query_terms_from_interests_and_major():
    profile = Profile(
        id="u1", email="a@asu.edu", major_name="Computer Systems Engineering",
        interests=["FPGA", "CUDA", "FPGA"],  # duplicate collapses
    )
    terms = people.query_terms(profile)
    assert terms[0] == "FPGA"
    assert "CUDA" in terms
    assert "Computer Systems Engineering" in terms
    assert len(terms) == len(set(t.lower() for t in terms))  # deduped


def test_query_terms_no_profile_is_empty():
    assert people.query_terms(None) == []
