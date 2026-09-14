#!/usr/bin/env python3
"""Parse a Sabancı degree-requirements page into structured JSON.

Usage:
    python3 tools/parse_degree.py "psir degree.htm" out/degree.json

The pages are exported from the SIS "Diploma Alanı" screens: each category
section is introduced by `<a name="ANCHOR"></a><b>Title</b>` and followed by a
table whose rows link to `sabanci_www.p_get_courses?levl_code=..&subj_code=..`.
"""

import html
import json
import re
import sys


def clean(fragment):
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def parse(doc):
    doc = re.sub(r"<script.*?</script>", "", doc, flags=re.S | re.I)
    doc = re.sub(r"<style.*?</style>", "", doc, flags=re.S | re.I)

    headers = [
        (m.start(), m.group(1), clean(m.group(2)))
        for m in re.finditer(r'<a name="([A-Z_0-9]+)"></a><b>(.*?)</b>', doc, re.S)
    ]

    sections = []
    for pos, anchor, title in headers:
        sections.append({"anchor": anchor, "title": title, "pos": pos, "courses": []})

    def section_for(pos):
        current = None
        for sec in sections:
            if sec["pos"] <= pos:
                current = sec
            else:
                break
        return current

    for m in re.finditer(r"<tr>(.*?)</tr>", doc, re.S):
        row = m.group(1)
        link = re.search(
            r"p_get_courses\?levl_code=([A-Z]+)&subj_code=([A-Z]+)&crse_numb=([A-Za-z0-9]+)",
            row,
        )
        if not link:
            continue
        tds = [clean(t) for t in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        sec = section_for(m.start())
        if sec is None:
            continue
        code = f"{link.group(2)} {link.group(3)}"
        sec["courses"].append(
            {
                "code": code,
                "subj": link.group(2),
                "num": link.group(3),
                "level": link.group(1),
                "name_tr": tds[2] if len(tds) > 2 else None,
                "ects": tds[3] if len(tds) > 3 else None,
                "su_credits": tds[4] if len(tds) > 4 else None,
                "faculty": tds[5] if len(tds) > 5 else None,
                "faculty_course": tds[0].startswith("*") if tds else False,
            }
        )

    for sec in sections:
        sec.pop("pos")
    return {"sections": sections}


def main():
    src, dst = sys.argv[1], sys.argv[2]
    with open(src, encoding="utf-8", errors="replace") as fh:
        doc = fh.read()
    data = parse(doc)
    with open(dst, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    for sec in data["sections"]:
        print(f"{sec['anchor']:<14} {sec['title']:<48} {len(sec['courses'])} courses")


if __name__ == "__main__":
    main()
