#!/usr/bin/env python3
"""Generate GitHub-style contribution graphs (dark + light) with month and
weekday labels, as standalone SVG files. Standard library only."""

import html
import os
import re
import sys
import urllib.request
from datetime import date

USER = os.environ.get("GITHUB_USER", "Dann-coder21")
OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else "dist"

CELL, GAP, RADIUS = 11, 3, 2
STEP = CELL + GAP
LEFT, TOP = 34, 44
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

THEMES = {
    "dark": {
        "levels": ["#151b23", "#033a16", "#196c2e", "#2ea043", "#56d364"],
        "stroke": "#ffffff",
        "text": "#9198a1",
        "title": "#e6edf3",
    },
    "light": {
        "levels": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
        "stroke": "#1f2328",
        "text": "#57606a",
        "title": "#24292f",
    },
}


def fetch(user, year):
    url = (f"https://github.com/users/{user}/contributions"
           f"?from={year}-01-01&to={year}-12-31")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def parse(page):
    # Tooltip text per cell id, e.g. "3 contributions on October 12th."
    counts = {}
    for cell_id, text in re.findall(
        r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]*)</tool-tip>', page
    ):
        m = re.match(r"(\d+) contribution", text.strip())
        counts[cell_id] = int(m.group(1)) if m else 0

    cells = []
    for tag in re.findall(r"<td [^>]*ContributionCalendar-day[^>]*>", page):
        d = re.search(r'data-date="([^"]+)"', tag)
        lvl = re.search(r'data-level="(\d)"', tag)
        cid = re.search(r'id="([^"]+)"', tag)
        if not (d and lvl and cid):
            continue
        row, col = re.search(r"-(\d+)-(\d+)$", cid.group(1)).groups()
        cells.append({
            "date": date.fromisoformat(d.group(1)),
            "level": int(lvl.group(1)),
            "row": int(row),
            "col": int(col),
            "count": counts.get(cid.group(1), 0),
        })

    total = re.search(
        r"([\d,]+)\s+contributions?\s+in\s+(?:the last year|\d{4})", page)
    total = int(total.group(1).replace(",", "")) if total else sum(
        c["count"] for c in cells)
    return cells, total


def render(cells, total, theme, year):
    t = THEMES[theme]
    cols = max(c["col"] for c in cells) + 1
    width = LEFT + cols * STEP + 12
    height = TOP + 7 * STEP + 40

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{total} contributions in {year}">',
        '<style>text{font-family:-apple-system,BlinkMacSystemFont,'
        '"Segoe UI",Helvetica,Arial,sans-serif}</style>',
        f'<text x="{LEFT}" y="22" font-size="15" fill="{t["title"]}">'
        f'{total:,} contributions in {year}</text>',
    ]

    # Month labels: first column whose Sunday falls in a new month.
    first_by_col = {}
    for c in sorted(cells, key=lambda c: (c["col"], c["row"])):
        first_by_col.setdefault(c["col"], c["date"])
    labels, prev = [], None
    for col in sorted(first_by_col):
        month = first_by_col[col].month
        if month != prev:
            labels.append((col, MONTHS[month - 1]))
            prev = month
    # Drop a leading label that would collide with the next one.
    if len(labels) > 1 and labels[1][0] - labels[0][0] < 3:
        labels.pop(0)
    for col, name in labels:
        out.append(
            f'<text x="{LEFT + col * STEP}" y="{TOP - 8}" font-size="11" '
            f'fill="{t["text"]}">{name}</text>')

    # Weekday labels (Mon / Wed / Fri).
    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        out.append(
            f'<text x="0" y="{TOP + row * STEP + CELL - 1}" font-size="11" '
            f'fill="{t["text"]}">{name}</text>')

    # Cells.
    for c in cells:
        x, y = LEFT + c["col"] * STEP, TOP + c["row"] * STEP
        label = html.escape(
            f'{c["count"]} contribution{"s" if c["count"] != 1 else ""} '
            f'on {c["date"].isoformat()}')
        out.append(
            f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" '
            f'rx="{RADIUS}" ry="{RADIUS}" fill="{t["levels"][c["level"]]}" '
            f'stroke="{t["stroke"]}" stroke-opacity="0.05"><title>{label}</title></rect>')

    # Legend.
    ly = TOP + 7 * STEP + 18
    lx = LEFT + cols * STEP - (5 * STEP + 70)
    out.append(f'<text x="{lx}" y="{ly + CELL - 1}" font-size="11" '
               f'fill="{t["text"]}">Less</text>')
    for i, colour in enumerate(t["levels"]):
        out.append(
            f'<rect x="{lx + 32 + i * STEP}" y="{ly}" width="{CELL}" '
            f'height="{CELL}" rx="{RADIUS}" fill="{colour}" '
            f'stroke="{t["stroke"]}" stroke-opacity="0.05"/>')
    out.append(f'<text x="{lx + 32 + 5 * STEP + 4}" y="{ly + CELL - 1}" '
               f'font-size="11" fill="{t["text"]}">More</text>')

    out.append("</svg>")
    return "\n".join(out)


def main():
    this_year = date.today().year
    years = [int(y) for y in os.environ.get(
        "YEARS", f"{this_year},{this_year - 1}").split(",")]
    os.makedirs(OUT_DIR, exist_ok=True)
    for year in years:
        cells, total = parse(fetch(USER, year))
        if not cells:
            sys.exit(f"No contribution cells found for {year}; "
                     "GitHub markup may have changed.")
        for theme in THEMES:
            path = os.path.join(OUT_DIR, f"contributions-{year}-{theme}.svg")
            with open(path, "w", encoding="utf-8") as f:
                f.write(render(cells, total, theme, year))
            print("wrote", path, f"({total} contributions)")


if __name__ == "__main__":
    main()
