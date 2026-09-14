#!/usr/bin/env python3
"""Build a prerequisite-map JSON (same schema as "cs prereq.json") for a program.

Usage:
    python3 tools/build_graph.py build/degree.json build/cache/courses.json out.json

The output mirrors the layout of Sabancı's CS prerequisite map: one page, a
title node, a container node holding every course/legend cell, course nodes
carrying `label`/`html`/`metadata.tooltip`, and prerequisite edges. Nested
expressions such as `A and (B or C)` get an intermediate `OR__B__C` node, which
is how the CS map encodes them.
"""

import hashlib
import json
import os
import re
import sys

PROGRAM = "BAPSIR"
PAGE_ID = f"{PROGRAM}_Prerequisites"
TITLE = "Prerequisite Map for Political Science and International Relations Program"
VERSION = "30.3.11"

# anchor -> (legend key, legend label, fill colour)
CATEGORIES = {
    "UC_FASS": ("UNIVERSITY", "University\nCourses", "#DAE8FC", "University Courses"),
    "BAPSIR_REQ": ("REQUIRED", "Required\nCourses", "#F8CECC", "Required Courses"),
    "BAPSIR_C1": (
        "CORE1",
        "Core Elective I\n(Political Science)",
        "#FFE6CC",
        "Core Elective I - Political Science",
    ),
    "BAPSIR_C2": (
        "CORE2",
        "Core Elective II\n(International Relations)",
        "#FFF2CC",
        "Core Elective II - International Relations",
    ),
    "BAPSIR_AEL": ("AREA", "Area\nElectives", "#E1D5E7", "Area Electives"),
    "BAPSIR_FEL": ("FREE", "Free\nElectives", "#D5E8D4", "Free Electives"),
    "FC_FASS": ("FACULTY", "Faculty\nCourses", "#F5F5F5", "Faculty Courses"),
    "OTHER": ("OTHER", "Other\nCourses", "#D5D5D5", "Other Courses"),
}

# First-year university courses that are not prerequisites of anything PSIR
# specific. Keeping them turns the map into a star with SPS 101/102 in the
# middle, so they are dropped from the tree and summarised in a note instead.
HIDDEN_COURSES = {
    "SPS101",
    "SPS102",
    "IF100",
    "MATH101",
    "MATH102",
    "NS101",
    "NS102",
    "TLL101",
    "TLL102",
    "HIST191",
    "HIST192",
    "AL102",
    "CIP101N",
}

NOTES = [
    (
        "SEASON",
        "How to read the semester strip",
        [
            "The coloured strip and the label under each course name show when",
            "it actually ran in the last 4 academic years (Fall 2023-2024 to",
            "Fall 2026-2027, 7 semesters). 'Rarely offered' means 2 or fewer of",
            "those semesters; a red 'Not offered recently' strip means the",
            "course did not run at all in the window, with the last time it did",
            "run shown underneath. Summer terms are not counted.",
        ],
    ),
    (
        "SPS",
        "Mandatory: SPS 101 & SPS 102",
        [
            "SPS 101 and SPS 102 (Humanity and Society I-II) are mandatory",
            "university courses for every PSIR student, so they are left out",
            "of this map to stop them fanning out into every single course.",
            "Every course whose tooltip lists them as a prerequisite",
            "(most POLS / IR / CONF / SOC courses, and the HUM block)",
            "assumes both have been completed.",
        ],
    ),
    (
        "OMITTED",
        "Other courses left out as prerequisites",
        [
            "Mandatory first-year university courses that are not",
            "prerequisites of anything in this map: IF 100, MATH 101-102,",
            "NS 101-102, TLL 101-102, HIST 191-192, AL 102, CIP 101N.",
            "Their course nodes still exist in psir degree.htm; they simply",
            "carry no prerequisite relationships inside PSIR.",
        ],
    ),
]

# ---- semester categorisation -------------------------------------------
# Terms the schedule data covers are scanned back to FIRST_YEAR; a course counts
# as "current" if it ran in any of the last RECENT_YEARS academic years.
RECENT_YEARS = 4
SEASON_COLORS = {
    "Fall": "#F6C177",
    "Spring": "#8CCB8C",
    "Fall & Spring": "#7FA9E8",
    "Not offered recently": "#D98C8C",
}


def term_label(code):
    year = code[:4]
    half = "Fall" if code.endswith("01") else "Spring" if code.endswith("02") else "Summer"
    return f"{half} {year}-{int(year) + 1}"


def recent_terms(offerings):
    """The Fall/Spring terms of the last RECENT_YEARS academic years."""
    falls = sorted(t for t in offerings if t.endswith("01"))
    cutoff = sorted({t[:4] for t in falls})[-RECENT_YEARS:]
    return sorted(t for t in offerings if t[:4] in cutoff and t.endswith(("01", "02")))


def offering_of(code, offerings, recent):
    """(season, box note, metadata) for one course."""
    offered = sorted(t for t in offerings if code in offerings[t])
    in_recent = [t for t in offered if t in recent]
    fall = any(t.endswith("01") for t in in_recent)
    spring = any(t.endswith("02") for t in in_recent)
    if fall and spring:
        season = "Fall & Spring"
    elif fall:
        season = "Fall"
    elif spring:
        season = "Spring"
    else:
        season = "Not offered recently"

    note = None
    if season == "Not offered recently":
        note = f"Last offered {term_label(offered[-1])}" if offered else "Not offered in the last 10+ years"
    elif len(in_recent) <= 2:
        note = f"Rarely offered ({len(in_recent)} of last {len(recent)} semesters)"

    meta = {
        "season": season,
        "season_color": SEASON_COLORS[season],
        "semesters_offered_recently": len(in_recent),
        "last_offered": term_label(offered[-1]) if offered else None,
    }
    return season, note, meta


def hashed_id(seed, length=32):
    return hashlib.md5(seed.encode("utf-8")).hexdigest()[:length]


def credits_note(rec):
    """'Needs min N SU credits' when Banner gates the course on a credit total."""
    credits = rec.get("prerequisite_credits")
    return f"Needs min {int(credits)} SU credits" if credits else None


def spaced(code):
    """'POLS250' -> 'POLS 250'."""
    m = re.match(r"^([A-Z]+)([0-9].*)$", code)
    return f"{m.group(1)} {m.group(2)}" if m else code


def compact(code):
    return code.replace(" ", "")


def expr_to_text(expr):
    """Render an expression tree the way the CS map writes tooltips."""
    if expr is None:
        return "NONE"
    if isinstance(expr, str):
        return compact(expr)
    parts = [expr_to_text(a) for a in expr["args"]]
    joiner = " AND " if expr["op"] == "and" else " OR "
    return "(" + joiner.join(parts) + ")"


def load_courses(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def build(degree, catalog, offerings=None):
    nodes, edges = [], []
    recent = recent_terms(offerings) if offerings else []

    container = "c" + hashed_id("container:" + PAGE_ID, 21)

    def add_node(cell):
        nodes.append(cell)

    def add_edge(source, target, tooltip=None, source_port=None, target_port=None):
        source, target = compact(source), compact(target)
        eid = hashed_id(f"edge:{source}->{target}:{tooltip}")
        meta = {}
        if tooltip:
            meta["tooltip"] = tooltip
            meta["label_position"] = "center"
            meta["label_align"] = "center"
        meta["source"] = source
        meta["target"] = target
        cell = {"id": eid, "type": "edge", "parent": container,
                "source": source, "target": target, "metadata": meta}
        edges.append(cell)
        return cell

    # ---- courses, grouped by degree-requirement category ----------------
    course_cat = {}      # code -> anchor
    order = []
    for section in degree["sections"]:
        anchor = section["anchor"]
        if anchor not in CATEGORIES:
            continue
        for course in section["courses"]:
            code = compact(course["code"])
            if code in course_cat or code in HIDDEN_COURSES:
                continue
            course_cat[code] = anchor
            order.append(code)

    # prerequisite-only courses that are not listed in the degree page
    referenced = set()
    for code, rec in catalog.items():
        for other in rec.get("prerequisite_codes") or []:
            referenced.add(compact(other))
    for code in sorted(referenced):
        if code in course_cat or code in HIDDEN_COURSES:
            continue
        if code not in catalog:
            print(f"! no catalog record for prerequisite course {spaced(code)}", file=sys.stderr)
            continue
        course_cat[code] = "OTHER"
        order.append(code)

    # ---- course nodes ---------------------------------------------------
    for code in order:
        rec = catalog.get(code, {})
        anchor = course_cat[code]
        _key, _label, color, category = CATEGORIES[anchor]
        name = rec.get("title") or spaced(code)
        season, season_note, season_meta = (
            offering_of(code, offerings, recent) if offerings else ("", None, {})
        )
        label = f"{spaced(code)} \n {name} \n {season}"
        html = f"<b>{spaced(code)}</b> <br/> {name}<br/>{season}"
        for extra in (season_note, credits_note(rec)):
            if extra:
                label += f"\n-\n{extra}"
                html += f"<br/>-<br/><i>{extra}</i>"

        tooltip_lines = [
            f"Course: {code}",
            f"Prerequisites: {expr_to_text(rec.get('prerequisite'))}",
            "Corequisites: "
            + (
                ",".join(compact(c) for c in (rec.get("corequisite_codes") or [])) or "nan"
            ),
            f"SU Credits: {fmt(rec.get('su_credits'))}",
            f"ECTS Credits: {fmt(rec.get('ects'))}",
            f"Category: {category}",
        ]
        if offerings:
            tooltip_lines += [
                f"Semester: {season}",
                f"Offered: {season_meta['semesters_offered_recently']} of last {len(recent)} semesters",
                f"Last offered: {season_meta['last_offered'] or 'unknown'}",
            ]
        tooltip = (
            '<div style="font-size: 14pt;">' + "&#xa;".join(tooltip_lines) + "&#xa;</div>"
        )
        add_node(
            {
                "id": code,
                "type": "node",
                "parent": container,
                "label": label,
                "html": html,
                "metadata": {
                    "tooltip": tooltip,
                    "category": category,
                    "color": color,
                    "season": season,
                    "season_color": season_meta.get("season_color"),
                    "semesters_offered_recently": season_meta.get("semesters_offered_recently"),
                    "last_offered": season_meta.get("last_offered"),
                },
            }
        )

    # ---- prerequisite edges --------------------------------------------
    intermediates = {}
    used_ids = set()

    def intermediate_id(expr):
        key = json.dumps(expr, sort_keys=True)
        if key in intermediates:
            return intermediates[key]
        node_id = ("OR__" if expr["op"] == "or" else "AND__") + "__".join(
            compact(a) if isinstance(a, str) else ("OR" if a["op"] == "or" else "AND")
            for a in expr["args"]
        )
        node_id = re.sub(r"[^A-Za-z0-9_]", "", node_id)
        if node_id in used_ids:  # keep distinct groups distinct
            node_id = f"{node_id}_{hashed_id(key, 4)}"
        used_ids.add(node_id)
        intermediates[key] = node_id
        add_node(
            {
                "id": node_id,
                "type": "node",
                "parent": container,
                "label": node_id,
                "metadata": {
                    "tooltip": "("
                    + ", ".join(
                        [expr["op"].upper()]
                        + [
                            compact(a) if isinstance(a, str) else expr_to_text(a)
                            for a in expr["args"]
                        ]
                    )
                    + ")"
                },
            }
        )
        for arg in expr["args"]:
            if isinstance(arg, str):
                add_edge(arg, node_id)
            else:
                add_edge(intermediate_id(arg), node_id)
        return node_id

    for code in order:
        rec = catalog.get(code, {})
        expr = rec.get("prerequisite")
        if not expr:
            continue
        if isinstance(expr, str):
            add_edge(expr, code, f"Prerequisite for {code}")
            continue
        op = expr["op"].upper()
        rendered = ", ".join(
            compact(a) if isinstance(a, str) else expr_to_text(a) for a in expr["args"]
        )
        tooltip = f"{op} operator for ({op}, {rendered})"
        for arg in expr["args"]:
            if isinstance(arg, str):
                add_edge(arg, code, tooltip)
            else:
                add_edge(intermediate_id(arg), code, tooltip)

    # ---- legend ---------------------------------------------------------
    legend = [
        {"id": f"{PROGRAM}_LEGEND_BOX", "type": "node", "parent": container,
         "label": f"{PROGRAM}_LEGEND_BOX"},
        {"id": f"{PROGRAM}_LEGEND_HEADER", "type": "node", "parent": container,
         "label": "Color Legend", "html": "<b>Color Legend</b>"},
    ]
    for anchor in ("UC_FASS", "BAPSIR_REQ", "BAPSIR_C1", "BAPSIR_C2",
                   "BAPSIR_AEL", "BAPSIR_FEL", "FC_FASS", "OTHER"):
        key, label, color, _cat = CATEGORIES[anchor]
        legend.append(
            {
                "id": f"{PROGRAM}_LEGEND_{key}",
                "type": "node",
                "parent": container,
                "label": label,
                "metadata": {"color": color},
            }
        )
    for kind in ("AND", "OR"):
        for end in ("SRC", "TGT"):
            legend.append(
                {
                    "id": f"{PROGRAM}_LEGEND_EDGE_{kind}_{end}",
                    "type": "node",
                    "parent": container,
                    "label": f"{PROGRAM}_LEGEND_EDGE_{kind}_{end}",
                }
            )
    legend.append(
        {
            "id": f"{PROGRAM}_LEGEND_SEMESTER_HEADER",
            "type": "node",
            "parent": container,
            "label": "Semester Legend",
            "html": "<b>Semester Legend</b>",
        }
    )
    for season, palette in SEASON_COLORS.items():
        legend.append(
            {
                "id": f"{PROGRAM}_LEGEND_{re.sub(r'[^A-Z]', '', season.upper())}",
                "type": "node",
                "parent": container,
                "label": season,
                "metadata": {"color": palette, "season": season},
            }
        )
    for kind in ("AND", "OR"):
        src = f"{PROGRAM}_LEGEND_EDGE_{kind}_SRC"
        tgt = f"{PROGRAM}_LEGEND_EDGE_{kind}_TGT"
        edges.append(
            {
                "id": hashed_id(f"legend:{src}->{tgt}"),
                "type": "edge",
                "parent": container,
                "source": src,
                "target": tgt,
                "label": kind,
                "metadata": {"source": src, "target": tgt},
            }
        )

    # ---- explanatory notes ----------------------------------------------
    notes = []
    for key, title, lines in NOTES:
        notes.append(
            {
                "id": f"{PROGRAM}_NOTE_{key}",
                "type": "node",
                "parent": container,
                "label": f"{title}\n" + "\n".join(lines),
                "html": f"<b>{title}</b><br/>" + "<br/>".join(f"<i>{l}</i>" for l in lines),
                "metadata": {
                    "kind": "note",
                    "color": "#FFF6C8",
                    "tooltip": f"<b>{title}</b><br/>" + "<br/>".join(lines),
                },
            }
        )

    # ---- prune: edges into hidden courses, and any orphaned OR/AND nodes --
    known = {n["id"] for n in nodes} | {l["id"] for l in legend} | {f"{PROGRAM}_TITLE", container}
    edges = [e for e in edges if e["source"] in known and e["target"] in known]
    while True:
        indegree = {}
        for e in edges:
            indegree[e["target"]] = indegree.get(e["target"], 0) + 1
        orphans = {
            n["id"]
            for n in nodes
            if n["id"].startswith(("OR__", "AND__")) and not indegree.get(n["id"])
        }
        if not orphans:
            break
        nodes = [n for n in nodes if n["id"] not in orphans]
        known -= orphans
        edges = [e for e in edges if e["source"] in known and e["target"] in known]

    cells = (
        [{"id": "1", "type": "layer"}]
        + [
            {
                "id": f"{PROGRAM}_TITLE",
                "type": "node",
                "parent": "1",
                "label": TITLE,
                "html": f"<b>{TITLE}</b>",
            },
            {"id": container, "type": "node", "parent": "1"},
        ]
        + notes
        + nodes
        + edges
        + legend
    )
    return {"version": VERSION, "pages": [{"id": PAGE_ID, "name": PAGE_ID, "cells": cells}]}


def fmt(value):
    if value is None:
        return "nan"
    return str(int(value)) if float(value).is_integer() else str(value)


def main():
    degree = json.load(open(sys.argv[1], encoding="utf-8"))
    catalog = load_courses(sys.argv[2])
    out = sys.argv[3]
    offerings_path = sys.argv[4] if len(sys.argv) > 4 else "build/cache/offerings.json"
    offerings = None
    if os.path.exists(offerings_path):
        offerings = json.load(open(offerings_path, encoding="utf-8"))
        print(f"semesters: {len(recent_terms(offerings))} recent terms from {offerings_path}")
    else:
        print(f"! no offering data at {offerings_path} - semester labels skipped")
    graph = build(degree, catalog, offerings)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(graph, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    cells = graph["pages"][0]["cells"]
    print(f"{out}: {sum(1 for c in cells if c['type'] == 'node')} nodes, "
          f"{sum(1 for c in cells if c['type'] == 'edge')} edges")


if __name__ == "__main__":
    main()
