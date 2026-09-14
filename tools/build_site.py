#!/usr/bin/env python3
"""Assemble the GitHub Pages site into docs/.

Copies the two generated pages under URL-friendly names and rewrites the
cross-links, then writes a small landing page.

Usage:
    python3 tools/build_site.py [docs]
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

REPO = "SenihD/sabanci-psir-prereq"
TITLE = "Sabancı PSIR — Prerequisite Map & Graduation Check"

LANDING = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>__TITLE__</title>
<style>
  :root { --ink:#22252f; --muted:#666c7a; --line:#e4e7ee; }
  * { box-sizing:border-box; }
  body { margin:0; font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
         color:var(--ink); background:#f6f7fa; }
  header { background:#1f2430; color:#fff; padding:44px 24px 40px; }
  .wrap { max-width:900px; margin:0 auto; }
  h1 { margin:0 0 10px; font-size:27px; letter-spacing:-.01em; }
  header p { margin:0; color:#b9c0d0; max-width:640px; font-size:14.5px; }
  main { max-width:900px; margin:-22px auto 0; padding:0 24px 60px; }
  .cards { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
  @media (max-width:760px) { .cards { grid-template-columns:1fr; } }
  a.card { display:block; background:#fff; border:1px solid var(--line); border-radius:14px;
           padding:20px 22px 22px; text-decoration:none; color:inherit;
           box-shadow:0 8px 24px #1f24300d; transition:transform .12s, box-shadow .12s; }
  a.card:hover { transform:translateY(-2px); box-shadow:0 12px 30px #1f243017; }
  .card h2 { margin:0 0 6px; font-size:17px; }
  .card .tag { display:inline-block; font-size:11px; font-weight:700; letter-spacing:.04em;
               text-transform:uppercase; color:#3b6fd4; margin-bottom:8px; }
  .card p { margin:0 0 12px; color:var(--muted); font-size:13.5px; }
  .card .go { font-size:13px; font-weight:600; color:#3b6fd4; }
  .notes { margin-top:26px; background:#fff; border:1px solid var(--line); border-radius:14px; padding:18px 22px; }
  .notes h3 { margin:0 0 8px; font-size:14px; }
  .notes ul { margin:0; padding-left:18px; color:var(--muted); font-size:13.5px; }
  .notes li { margin-bottom:5px; }
  footer { max-width:900px; margin:0 auto; padding:0 24px 60px; color:var(--muted); font-size:12.5px; }
  footer a { color:#3b6fd4; }
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>Sabancı PSIR — prerequisite map &amp; graduation check</h1>
    <p>Two tools for the B.A. Political Science and International Relations programme,
       built from the Sabancı University course catalog and the BAPSIR degree requirements.</p>
  </div>
</header>
<main>
  <div class="cards">
    <a class="card" href="prereq.html">
      <span class="tag">Prerequisite map</span>
      <h2>The prerequisite tree</h2>
      <p>64 courses with their prerequisite chains drawn out — AND edges, OR groups, and the
         HUM 2xx → 3xx block. Each course is labelled with the semester it actually runs, plus
         notes for the ones that have not been offered in years.</p>
      <span class="go">Open the map →</span>
    </a>
    <a class="card" href="checker.html">
      <span class="tag">Graduation check</span>
      <h2>Can I graduate?</h2>
      <p>Tick the courses you have taken. It checks every requirement — required courses,
         core electives I and II, area electives, university courses, free electives, faculty
         courses, 125 SU credits and 240 ECTS — and flags prerequisites you have skipped.</p>
      <span class="go">Open the checker →</span>
    </a>
  </div>
  <div class="notes">
    <h3>Where the data comes from</h3>
    <ul>
      <li>Requirement pools: the BAPSIR “Diploma Alanı” page from the SIS.</li>
      <li>Prerequisites and credits: the Sabancı Banner course catalog.</li>
      <li>Semesters: the class schedule search, Fall 2016-2017 → Fall 2026-2027.</li>
      <li>Everything is scraped and rebuilt by the scripts in the repository, so a new
          catalog term is one rerun away.</li>
    </ul>
  </div>
</main>
<footer>
  <p>Unofficial student tool — always confirm against
     <a href="https://suis.sabanciuniv.edu/">SUIS</a> and the Information System degree
     evaluation. Source: <a href="https://github.com/__REPO__">__REPO__</a>.</p>
</footer>
</body>
</html>
"""


def main():
    outdir = os.path.join(ROOT, sys.argv[1] if len(sys.argv) > 1 else "docs")
    os.makedirs(outdir, exist_ok=True)

    prereq = open(os.path.join(ROOT, "psir prereq.html"), encoding="utf-8").read()
    checker = open(os.path.join(ROOT, "psir graduation checker.html"), encoding="utf-8").read()

    # rewrite the cross-links to the URL-friendly file names used on the site
    prereq = prereq.replace("psir%20graduation%20checker.html", "checker.html")
    checker = checker.replace("psir%20prereq.html", "prereq.html")

    landing = LANDING.replace("__TITLE__", TITLE).replace("__REPO__", REPO)

    for name, body in (("index.html", landing), ("prereq.html", prereq), ("checker.html", checker)):
        with open(os.path.join(outdir, name), "w", encoding="utf-8") as fh:
            fh.write(body)
        print(f"{outdir}/{name} ({len(body) // 1024} KB)")

    open(os.path.join(outdir, ".nojekyll"), "w").close()


if __name__ == "__main__":
    main()
