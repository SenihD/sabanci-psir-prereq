#!/usr/bin/env python3
"""Scrape which courses were actually offered in each term.

The catalog (`bwckctlg`) lists a subject's entire catalog, not what runs, so
this uses the class schedule search (`bwckschd.p_get_crse_unsec`), which only
returns sections that were actually scheduled that term.

Usage:
    python3 tools/scrape_offerings.py build/codes.txt build/cache [FIRST_YEAR]

Writes build/cache/offerings.json: {term: [course codes]}. Raw HTML is cached
per term, so reruns are offline.
"""

import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

URL = "https://suis.sabanciuniv.edu/prod/bwckschd.p_get_crse_unsec"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
SECTION_RE = re.compile(r"-\s*([A-Z]{2,6})\s+(\d{3}[A-Z]*)\s+-\s+[A-Z0-9]+</a>")


def terms(first_year):
    """Fall/Spring term codes from first_year up to the current term."""
    out = []
    for year in range(first_year, 2027):
        for half, _ in (("01", "Fall"), ("02", "Spring")):
            code = f"{year}{half}"
            if code > "202601":  # do not ask about terms that have not started
                continue
            out.append(code)
    return out


def search(opener, term, subjects):
    fields = [("term_in", term), ("call_proc_in", "bwckschd.p_disp_dyn_sched")]
    fields += [("sel_subj", "dummy")] + [("sel_subj", s) for s in subjects]
    for key in ("sel_day", "sel_schd", "sel_insm", "sel_camp", "sel_levl",
                "sel_sess", "sel_instr", "sel_ptrm", "sel_attr"):
        fields += [(key, "dummy"), (key, "%")]
    fields += [("sel_crse", ""), ("sel_title", ""), ("begin_hh", "0"),
               ("begin_mi", "0"), ("begin_ap", "a"), ("end_hh", "0"),
               ("end_mi", "0"), ("end_ap", "a")]
    req = urllib.request.Request(URL, data=urllib.parse.urlencode(fields).encode())
    with opener.open(req, timeout=90) as resp:
        return resp.read().decode("utf-8", "replace")


def main():
    codes_file, outdir = sys.argv[1], sys.argv[2]
    first_year = int(sys.argv[3]) if len(sys.argv) > 3 else 2016
    os.makedirs(outdir, exist_ok=True)

    subjects = sorted(
        {
            m.group(1)
            for line in open(codes_file, encoding="utf-8")
            if (m := re.match(r"^([A-Z]{2,6})\s*\d{3}", line.strip()))
        }
    )
    print("subjects:", " ".join(subjects))

    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [("User-Agent", UA), ("Accept-Language", "en-US,en;q=0.9")]

    offerings = {}
    for term in terms(first_year):
        cache = os.path.join(outdir, f"schedule.{term}.html")
        if os.path.exists(cache):
            body = open(cache, encoding="utf-8", errors="replace").read()
        else:
            try:
                body = search(opener, term, subjects)
            except Exception as exc:  # noqa: BLE001
                print(f"! {term}: {exc}", file=sys.stderr)
                continue
            open(cache, "w", encoding="utf-8").write(body)
            time.sleep(0.3)
        codes = sorted({f"{s}{n}" for s, n in SECTION_RE.findall(body)})
        offerings[term] = codes
        label = re.search(r"Associated Term:\s*</SPAN>\s*([^<]+)", body)
        print(f"{term}  {label.group(1).strip() if label else '?':<18} {len(codes):>4} courses")

    with open(os.path.join(outdir, "offerings.json"), "w", encoding="utf-8") as fh:
        json.dump(offerings, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"\nwrote {outdir}/offerings.json ({len(offerings)} terms)")


if __name__ == "__main__":
    main()
