#!/usr/bin/env python3
"""Scrape Sabancı University (Banner) course catalog for prerequisites.

Usage:
    python3 tools/scrape_prereqs.py CODES.txt OUTDIR [TERM]

CODES.txt holds one course per line, e.g. "POLS 250" or "POLS250".
Raw HTML is cached under OUTDIR so reruns are free.

Output: OUTDIR/courses.json mapping "POLS250" -> record with the parsed
prerequisite expression tree, English title and credit info.
"""

import html
import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.request

BASE = "https://suis.sabanciuniv.edu/prod/bwckctlg.p_disp_course_detail"
FALLBACK_TERMS = ["202502", "202402", "202301"]
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124 Safari/537.36"
)

COURSE_RE = re.compile(r"^([A-Z]{2,6})\s*([0-9]{3}[A-Z0-9]*)$")
GRADE_RE = re.compile(
    r"(?:Undergraduate|Graduate|Doctorate|Masters|Special Student|Undeclared) level"
    r"|Minimum Grade of [A-Z][+-]?"
    r"|Must be enrolled in one of the following [A-Za-z ]+"
)
TOKEN_RE = re.compile(
    r"(?P<course>[A-Z]{2,6}\s*[0-9]{3}[A-Z0-9]*)|(?P<paren>[()])|(?P<op>\band\b|\bor\b)",
    re.I,
)
# Course codes are read from the link URL rather than its text: some Banner
# templates render the code as "SPS<br/>101", splitting the anchor text.
LINK_RE = re.compile(
    r'<a[^>]*\bone_subj=([A-Z]{2,6})\b[^>]*\bsel_crse_strt=(\d{3}[A-Za-z0-9]*)\b[^>]*>.*?</a>',
    re.I | re.S,
)
PLACEHOLDER_RE = re.compile(r"@@C(\d+)@@")


def make_opener():
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [("User-Agent", UA), ("Accept-Language", "en-US,en;q=0.9")]
    return opener


def fetch(opener, code, term, outdir):
    """Fetch one course page, falling back to older catalog terms.

    Courses that were retired from the current catalog (CULT 384, for example)
    still exist in older terms, so walk back through the fallbacks until a page
    with real content shows up.
    """
    subj, num = code
    last = None
    for candidate in [term] + [t for t in FALLBACK_TERMS if t != term]:
        cache = os.path.join(outdir, f"{subj}{num}.{candidate}.html")
        if os.path.exists(cache):
            with open(cache, encoding="utf-8", errors="replace") as fh:
                body = fh.read()
        else:
            url = f"{BASE}?cat_term_in={candidate}&subj_code_in={subj}&crse_numb_in={num}"
            with opener.open(url, timeout=60) as resp:
                body = resp.read().decode("utf-8", "replace")
            with open(cache, "w", encoding="utf-8") as fh:
                fh.write(body)
            time.sleep(0.3)
        last = body
        if "No course to display" not in body:
            return body, candidate
    return last, None


def strip_tags(fragment):
    fragment = re.sub(r"<(?:br|/tr|/td|/table|/p)[^>]*>", "\n", fragment, flags=re.I)
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    return html.unescape(fragment)


def slice_block(doc, label, stops):
    """Return raw HTML of the block beginning at `label`, cut at the first stop."""
    m = re.search(re.escape(label) + r"\s*:?\s*</SPAN>(.*)", doc, re.S | re.I)
    if not m:
        return None
    body = m.group(1)
    cut = len(body)
    for stop in list(stops) + ["</TD>", "</table>"]:
        i = body.find(stop)
        if i != -1:
            cut = min(cut, i)
    return body[:cut]


CREDITS_RE = re.compile(r"General Requirements:\s*([0-9][0-9,\.]*)\s*credits", re.I)
SU_CREDIT_RE = re.compile(r"([0-9]+\.[0-9]+)\s+Credit hours", re.I)
ECTS_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s+ECTS\b", re.I)
COLLEGE_RE = re.compile(r"Must be enrolled in one of the following Colleges:\s*(.+)", re.I)

# Boilerplate that must go before the boolean operators are read, otherwise the
# "or" inside "Course or Test:" would be mistaken for an OR operator.
BOILERPLATE = [
    re.compile(r"General Requirements:.*?credits", re.I | re.S),
    re.compile(r"Course or Test\s*:", re.I),
    re.compile(r"(?:Course|Test)\s*:", re.I),
    re.compile(r"May not be taken concurrently\.?", re.I),
    re.compile(
        r"(?:Undergraduate|Graduate|Doctorate|Masters|Special Student|Undeclared) level",
        re.I,
    ),
    re.compile(r"Minimum Grade of\s+[A-Z][+-]?", re.I),
    re.compile(r"\b\d+(?:[\.,]\d+)?\s+to\s+\d+\b"),
    re.compile(r"Pre-requisites?:?|Pre-requiste", re.I),
]


def tokenize(raw_html):
    """Turn a Banner prerequisite block into a token list.

    Only course links are treated as courses, so free text like
    "58.000 credits" or "CREDITS000 to 9999" cannot leak in.
    """
    courses = []

    def swap(match):
        courses.append((match.group(1).upper(), match.group(2).upper()))
        return f" @@C{len(courses) - 1}@@ "

    marked = LINK_RE.sub(swap, raw_html)
    text = strip_tags(marked)
    for pattern in BOILERPLATE:
        text = pattern.sub(" ", text)
    tokens = []
    for m in re.finditer(r"@@C(\d+)@@|[()]|\band\b|\bor\b", text, re.I):
        chunk = m.group(0)
        if chunk.startswith("@@C"):
            subj, num = courses[int(chunk[3:-2])]
            tokens.append(("course", f"{subj} {num}"))
        elif chunk in "()":
            tokens.append((chunk, chunk))
        else:
            tokens.append(("op", chunk.lower()))
    readable = PLACEHOLDER_RE.sub(lambda m: " ".join(courses[int(m.group(1))]), text)
    return tokens, " ".join(readable.split())


def parse_expr(tokens):
    """expr := or ; or := and ('or' and)* ; and := term ('and' term)* ;
    term := '(' expr ')' | course."""

    def term(pos):
        if pos >= len(tokens):
            return None, pos
        kind, val = tokens[pos]
        if kind == "(":
            node, pos = parse_or(pos + 1)
            if pos < len(tokens) and tokens[pos][0] == ")":
                pos += 1
            return node, pos
        if kind == "course":
            return val, pos + 1
        return None, pos + 1

    def parse_and(pos):
        args = []
        node, pos = term(pos)
        if node is not None:
            args.append(node)
        while pos < len(tokens) and tokens[pos] == ("op", "and"):
            node, pos = term(pos + 1)
            if node is not None:
                args.append(node)
        return combine("and", args), pos

    def parse_or(pos):
        args = []
        node, pos = parse_and(pos)
        if node is not None:
            args.append(node)
        while pos < len(tokens) and tokens[pos] == ("op", "or"):
            node, pos = parse_and(pos + 1)
            if node is not None:
                args.append(node)
        return combine("or", args), pos

    return parse_or(0)


def combine(op, args):
    if not args:
        return None
    if len(args) == 1:
        return args[0]
    return {"op": op, "args": args}


def collect_codes(expr):
    if expr is None:
        return []
    if isinstance(expr, str):
        return [expr]
    out = []
    for arg in expr["args"]:
        out.extend(collect_codes(arg))
    return out


def parse_page(doc, code, term):
    subj, num = code
    plain = strip_tags(doc)
    title = None
    m = re.search(rf"^\s*{subj}\s+{num}\s+-\s+(.*?)\s*$", plain, re.M)
    if m:
        title = m.group(1).strip()

    prereq_html = slice_block(
        doc,
        "Prerequisites",
        ["Co-requisites", "Corequisites"],
    )
    coreq_html = slice_block(doc, "Co-requisites", []) or slice_block(doc, "Corequisites", [])

    rec = {"code": f"{subj}{num}", "subj": subj, "num": num, "term": term, "title": title}
    su = SU_CREDIT_RE.search(plain)
    ects = ECTS_RE.search(plain)
    college = COLLEGE_RE.search(plain)
    rec["su_credits"] = float(su.group(1)) if su else None
    rec["ects"] = float(ects.group(1)) if ects else None
    rec["college"] = college.group(1).split("\n")[0].strip() if college else None
    for key, raw in (("prerequisite", prereq_html), ("corequisite", coreq_html)):
        if raw is None:
            rec[key] = None
            rec[key + "_text"] = ""
            rec[key + "_codes"] = []
            rec[key + "_credits"] = None
            continue
        credits = CREDITS_RE.search(strip_tags(raw))
        rec[key + "_credits"] = float(credits.group(1).replace(",", "")) if credits else None
        tokens, text = tokenize(raw)
        # Banner repeats the course itself as a group label ("SPS 303>Pre-requisite")
        tokens = [t for t in tokens if not (t[0] == "course" and t[1] == f"{subj} {num}")]
        expr, _ = parse_expr(tokens)
        rec[key] = expr
        rec[key + "_text"] = text
        rec[key + "_codes"] = sorted(set(collect_codes(expr)))
    return rec


def main():
    codefile, outdir = sys.argv[1], sys.argv[2]
    term = sys.argv[3] if len(sys.argv) > 3 else "202601"
    os.makedirs(outdir, exist_ok=True)

    codes = []
    with open(codefile, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = COURSE_RE.match(line)
            if not m:
                print(f"! skipping unparsable line: {line!r}", file=sys.stderr)
                continue
            codes.append((m.group(1), m.group(2)))

    opener = make_opener()
    records, seen, queue = {}, set(), list(codes)
    while queue:
        code = queue.pop(0)
        if code in seen:
            continue
        seen.add(code)
        try:
            doc, used_term = fetch(opener, code, term, outdir)
        except Exception as exc:  # noqa: BLE001
            print(f"! {code[0]} {code[1]}: {exc}", file=sys.stderr)
            continue
        if used_term is None:
            print(f"! {code[0]} {code[1]}: not found in any catalog term", file=sys.stderr)
            continue
        rec = parse_page(doc, code, used_term)
        records[rec["code"]] = rec
        print(f"{rec['code']:<9} {rec['title']}\n          prereq: {rec['prerequisite_text']}")
        for other in rec["prerequisite_codes"]:
            m = COURSE_RE.match(other)
            if m and (m.group(1), m.group(2)) not in seen:
                queue.append((m.group(1), m.group(2)))

    out = os.path.join(outdir, "courses.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"\nwrote {out} ({len(records)} courses)")


if __name__ == "__main__":
    main()
