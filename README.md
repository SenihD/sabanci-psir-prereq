# PSIR prerequisite map

A prerequisite tree for Sabancı University's Political Science and
International Relations (BAPSIR) program, built to match the format of
`cs prereq.json`.

## Files

| File | What it is |
| --- | --- |
| `psir prereq.json` | The prerequisite map, same schema as `cs prereq.json` |
| `psir prereq.html` | Standalone viewer (graph is embedded, just open it) |
| `psir graduation checker.html` | Tick off courses and see whether you can graduate |
| `psir degree.htm` | Degree-requirements export from the SIS (input) |
| `cs prereq.json` | The CS map this format follows |
| `tools/` | Scripts below |
| `build/` | Intermediate output and a cache of scraped catalog pages |

## Regenerating

```sh
python3 tools/parse_degree.py "psir degree.htm" build/degree.json
python3 tools/scrape_prereqs.py build/codes.txt build/cache 202601   # network
python3 tools/scrape_offerings.py build/codes.txt build/cache 2016   # network
python3 tools/build_graph.py build/degree.json build/cache/courses.json "psir prereq.json"
python3 tools/build_viewer.py "psir prereq.json" "psir prereq.html"
python3 tools/build_checker.py "psir graduation checker.html"
python3 tools/build_site.py                 # assembles docs/ for GitHub Pages
```

The two pages are published at
<https://senihd.github.io/sabanci-psir-prereq/> — `docs/` holds URL-friendly
copies (`prereq.html`, `checker.html`) plus a landing page, and GitHub Pages
serves that folder from `main`.

The two scrapers cache every page they download under `build/cache/`, so reruns
after the first pass work offline. `build_graph.py` picks up
`build/cache/offerings.json` automatically and just skips the semester labels
if it is missing.

## Semesters

Every course carries a `Fall` / `Spring` / `Fall & Spring` label plus a
coloured strip, based on the terms it **actually ran** in the last four
academic years — Fall 2023-2024 through Fall 2026-2027, 7 semesters. Two extra
box notes come out of that:

* `Rarely offered (N of last 7 semesters)` when a course ran twice or less;
* `Not offered recently` with the last term it did run, for courses that did
  not run at all in the window.

Being listed in the degree page does not mean a course still runs. Nine
courses have not been scheduled in four years or more: HUM 371, IR 341,
POLS 351, POLS 366, POLS 403, POLS 422, SPS 394 (never, in ten years of
schedule data) and PROJ 102, SOC 301 (last seen Spring 2022-2023 and Spring
2020-2021). SPS 394 in particular looks like a re-coding of CULT 384, which
runs under the CULT subject.

## Graduation check

`psir graduation checker.html` lists all 77 courses the degree page mentions,
grouped by requirement, with a checkbox each. Ticks are saved in the browser
(`localStorage`), so the page can be closed and reopened.

It re-derives the rules from `psir degree.htm` on every tick:

| Requirement | Rule checked |
| --- | --- |
| Required Courses | all nine taken, ≥24 SU credits |
| Core Elective I / II | ≥12 SU credits each |
| Area Electives | ≥15 SU credits |
| University Courses | 17 courses, 44 SU credits, every 1XX course plus PROJ 201 and SPS 303, and two HUM courses — a 2xx then a 3xx |
| Free Electives | ≥18 SU credits (typed in, since the pool is the whole university) |
| Faculty Courses | ≥5 courses, ≥3 from SSBF areas, ≥3 distinct areas |
| Totals | 125 SU credits, 240 ECTS |

Those numbers reconcile: the 15 mandatory university courses are 38 SU credits
and adding the two HUM courses gives exactly 17 courses and 44 SU credits, and
the category minimums sum to 125.

It also evaluates the prerequisite expressions against what you ticked, so
ticking POLS 457 without POLS 250 — or ECON 320 without ECON 201/204 — is
reported under *Prerequisite problems*. The three extra courses (PROJ 102,
ECON 201, ECON 204) appear in their own group because they are prerequisites
that are not on the degree page, and their credits count towards free electives.

Approximations, so the verdict is not taken as gospel:

* **Faculty Courses** is estimated from the subjects you ticked (SSBF's six
  areas plus MDBF as the seventh), because the actual faculty-course pools are
  behind links on the degree page. There is an input for extra courses, and
  the row is labelled *estimated*.
* **Free electives** cannot be enumerated, so they are entered as SU credits;
  their ECTS contribution is estimated at 2 ECTS per SU credit.
* The course list is the degree page's own pools, so a course that counts for
  a requirement but is not listed there will not be counted.

## Where the data comes from

* **Degree structure** — `psir degree.htm`, the "Diploma Alanı" page from the
  SIS. `tools/parse_degree.py` reads one course row per
  `sabanci_www.p_get_courses` link and groups courses by their category
  anchors (`UC_FASS`, `BAPSIR_REQ`, `BAPSIR_C1`, `BAPSIR_C2`, `BAPSIR_AEL`,
  `BAPSIR_FEL`, `FC_FASS`).
* **Prerequisites** — the Sabancı Banner catalog,
  `suis.sabanciuniv.edu/prod/bwckctlg.p_disp_course_detail`, whose pages spell
  prerequisites out as a boolean expression, e.g.
  `(Undergraduate level MATH 201 … or MATH 212 …) and MATH 203 …`.
  `tools/scrape_prereqs.py` turns that into a tree and follows prerequisite
  courses recursively, so courses outside the degree lists (PROJ 102, ECON 201,
  ECON 204) are picked up as well.

## Format notes

The JSON is cell-based, exactly like the CS sample:

* one `layer` cell, a title node, and a container node that every course,
  legend and edge cell points at via `parent`;
* course nodes carry `label`, `html` and `metadata.tooltip` with
  `Course / Prerequisites / Corequisites / SU Credits / ECTS Credits`;
* the label is `CODE \n Name \n Semester`, followed by `\n-\n<note>` lines for
  the credit gate, the rarely-offered warning or the last-offered date;
* a plain prerequisite becomes one edge (`Prerequisite for X`), an AND becomes
  one edge per operand (`AND operator for (AND, …)`), and an OR is drawn the
  same way with `OR operator for (OR, …)`.
* Nested expressions get an intermediate node, mirroring how the CS map
  encodes `((MATH201 OR MATH212) AND MATH203)` — for example
  `OR__HUM201__HUM202__HUM207`, which both HUM 2xx courses feed into and which
  then feeds the HUM 3xx courses.

Two additions beyond the CS sample, because the sample keeps that information
only inside its colour legend:

* `metadata.category` and `metadata.color` on every course node (the legend
  node ids also gained `CORE1`, `CORE2`, `FREE` and `FACULTY`);
* `metadata.season`, `metadata.season_color`, `metadata.last_offered` and
  `metadata.semesters_offered_recently` on every course node, plus a
  `Semester Legend` block of legend nodes;
* the tooltip lists `Category:` as well.

## What is deliberately left out

First-year university courses are dropped from the tree, because SPS 101/102 in
particular are a prerequisite of most POLS / IR / CONF / SOC courses and turn
the map into a star with a single hub in the middle. The omitted list is
`HIDDEN_COURSES` in `tools/build_graph.py`:

> SPS 101, SPS 102, IF 100, MATH 101-102, NS 101-102, TLL 101-102,
> HIST 191-192, AL 102, CIP 101N

Anything they used to point at simply becomes a root, and the tooltips still
list them, so no information is lost — it just stops being drawn as edges.
Two note nodes (`BAPSIR_NOTE_SPS`, `BAPSIR_NOTE_OMITTED`) explain this on the
map itself. Note nodes carry `metadata.kind = "note"`; a renderer that does not
care about them can treat them as ordinary label-only nodes.

PROJ 201 and PROJ 102 are kept, because they are a genuine prerequisite of
PSIR 300, and SPS 303 is kept because of its credit gate.

## Known limitations

* Prerequisites are read from the **Fall 2026-2027 (202601)** catalog — the
  term current at the time of scraping. CULT 384 was retired from it and is
  filled in from Spring 2024-2025, which is noted by the `term` field in
  `build/cache/courses.json`.
* Semester data comes from the class schedule search
  (`bwckschd.p_get_crse_unsec`), not the catalog — the catalog lists a
  subject's whole offering (99 POLS courses for 202601) rather than what runs.
  Fall and Spring terms from 2016-2017 onward were scanned; **summer terms are
  not counted**, so a summer-only course would read as not offered.
* A section bearing a course code counts as "offered", so a course that runs
  but draws no students still counts, and cross-listed courses are only
  credited to the code that appears in the schedule.
* Two courses gate on credit totals rather than on a course. Banner reports
  those as `General Requirements`, so their nodes carry a
  `Needs min N SU credits` line the way `ENS 491` does in the CS map:
  SPS 303 (58 credits) and HUM 201/202/207 (23 credits).
* Free electives and faculty courses are open pools, so they have no course
  nodes — they exist only as legend entries.
