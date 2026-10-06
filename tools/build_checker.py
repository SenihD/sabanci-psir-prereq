#!/usr/bin/env python3
"""Build a standalone HTML graduation checker for the PSIR degree.

Usage:
    python3 tools/build_checker.py "psir graduation checker.html"

Reads build/degree.json (requirement pools and credits), build/cache/courses.json
(credits, ECTS and prerequisite expressions) and build/cache/offerings.json
(semester history), then inlines everything into tools/checker_template.html.
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_graph as bg  # noqa: E402

GROUP_OF_ANCHOR = {
    "BAPSIR_REQ": "REQ",
    "BAPSIR_C1": "C1",
    "BAPSIR_C2": "C2",
    "BAPSIR_AEL": "AEL",
    "UC_FASS": "UC",
}

GROUPS = [
    {
        "key": "REQ",
        "title": "Required Courses",
        "tr": "Zorunlu Dersler",
        "min_credits": 24,
        "min_courses": 7,
        "rule": "All nine listed courses are mandatory.",
    },
    {
        "key": "C1",
        "title": "Core Elective I — Political Science",
        "tr": "Cekirdek Secmeli I",
        "min_credits": 12,
        "min_courses": 4,
        "rule": "At least 12 SU credits from this pool.",
    },
    {
        "key": "C2",
        "title": "Core Elective II — International Relations",
        "tr": "Cekirdek Secmeli II",
        "min_credits": 12,
        "min_courses": 4,
        "rule": "At least 12 SU credits from this pool.",
    },
    {
        "key": "AEL",
        "title": "Area Electives",
        "tr": "Alan Secmeli Dersler",
        "min_credits": 15,
        "min_courses": 5,
        "rule": "At least 15 SU credits from this pool.",
    },
    {
        "key": "UC",
        "title": "University Courses",
        "tr": "Universite Dersleri",
        "min_credits": 44,
        "min_courses": 17,
        "rule": "17 courses / 44 SU credits. Every 1XX course, PROJ 201 and "
                "SPS 303 is mandatory, plus two HUM courses: a 2xx first, then a 3xx.",
    },
    {
        "key": "OTHER",
        "title": "Other courses you may have taken",
        "tr": "",
        "min_credits": 0,
        "min_courses": 0,
        "rule": "Not on the degree page, but they are prerequisites of listed "
                "courses and count as free electives.",
    },
]

EXTRA_COURSES = ["PROJ102", "ECON201", "ECON204"]


def as_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "psir graduation checker.html"
    degree = json.load(open("build/degree.json", encoding="utf-8"))
    catalog = json.load(open("build/cache/courses.json", encoding="utf-8"))
    offerings = json.load(open("build/cache/offerings.json", encoding="utf-8"))
    recent = bg.recent_terms(offerings)

    courses, seen = [], set()

    def add(code, group, listed=None):
        code = code.replace(" ", "")
        if code in seen:
            return
        seen.add(code)
        rec = catalog.get(code, {})
        season, _, _ = bg.offering_of(code, offerings, recent)
        credits = as_int(listed["su_credits"]) if listed else None
        ects = as_int(listed["ects"]) if listed else None
        if credits is None:
            credits = int(rec.get("su_credits") or 0)
        if ects is None:
            ects = int(rec.get("ects") or 0)
        match = re.match(r"^([A-Z]+)(\d+[A-Z]*)$", code)
        num = listed["num"] if listed else (match.group(2) if match else "")
        courses.append(
            {
                "code": code,
                "name": rec.get("title") or (listed or {}).get("name_tr") or code,
                "subject": (listed or {}).get("subj") or "".join(c for c in code if c.isalpha()),
                "num": num,
                "group": group,
                "credits": credits,
                "ects": ects,
                "season": season,
                "faculty_course": bool((listed or {}).get("faculty_course")),
                "mandatory": bool(
                    group == "UC"
                    and listed
                    and (str(num).startswith("1") or code in ("PROJ201", "SPS303"))
                ),
                "prereq": rec.get("prerequisite"),
                "prereq_text": bg.expr_to_text(rec.get("prerequisite")),
                "prereq_credits": rec.get("prerequisite_credits"),
            }
        )

    for section in degree["sections"]:
        group = GROUP_OF_ANCHOR.get(section["anchor"])
        if not group:
            continue
        for listed in section["courses"]:
            add(listed["code"], group, listed)

    for code in EXTRA_COURSES:
        add(code, "OTHER")

    data = {
        "program": "BAPSIR",
        "title": "Political Science and International Relations — Graduation Check",
        "totals": {"credits": 125, "ects": 240},
        "groups": GROUPS,
        "courses": courses,
    }

    template = open(os.path.join(HERE, "checker_template.html"), encoding="utf-8").read()
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace(
        "</script", "<\\/script"
    )
    html = template.replace("__DATA__", payload).replace("__TITLE__", data["title"])
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"{out_path}: {len(courses)} courses across {len(GROUPS)} groups")


if __name__ == "__main__":
    main()
