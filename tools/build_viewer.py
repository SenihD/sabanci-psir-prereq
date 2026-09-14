#!/usr/bin/env python3
"""Inline a prerequisite-map JSON into a standalone HTML viewer.

Usage:
    python3 tools/build_viewer.py "psir prereq.json" "psir prereq.html"
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    graph_path, out_path = sys.argv[1], sys.argv[2]
    graph = json.load(open(graph_path, encoding="utf-8"))
    title = next(
        (
            c.get("label")
            for c in graph["pages"][0]["cells"]
            if c.get("id", "").endswith("_TITLE")
        ),
        "Prerequisite Map",
    )
    template = open(os.path.join(HERE, "viewer_template.html"), encoding="utf-8").read()
    payload = json.dumps(graph, ensure_ascii=False, separators=(",", ":")).replace(
        "</script", "<\\/script"
    )
    # link to the graduation checker when it sits next to this file
    checker = "psir graduation checker.html"
    nav = ""
    if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(out_path)), checker)):
        nav = f'<a href="{checker.replace(" ", "%20")}">Open the graduation checker →</a>'
    html = (
        template.replace("__TITLE__", title)
        .replace("__GRAPH_JSON__", payload)
        .replace("__NAV__", nav)
    )
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"{out_path} ({len(html) // 1024} KB, {len(graph['pages'][0]['cells'])} cells)")


if __name__ == "__main__":
    main()
