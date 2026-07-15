#!/usr/bin/env python3
"""Rebuild the NIRF directory embedded in index.html from nirfindia.org.

Downloads the official NIRF *Engineering* ranking pages for 2023-2025 -
ranks 1-100 plus the 101-150 / 151-200 / 201-300 rank-band pages - merges
them by institute, and rewrites the block between NIRF_DIRECTORY_START /
NIRF_DIRECTORY_END markers in index.html.

Run from the repo root:  python3 scripts/build_nirf_directory.py
(needs: requests)
"""
import datetime
import json
import re
import sys

import requests

YEARS = [2025, 2024, 2023]
PAGES = [  # (suffix, band label; None = ranked list with a Rank column)
    ("EngineeringRanking.html", None),
    ("EngineeringRanking150.html", "101-150"),
    ("EngineeringRanking200.html", "151-200"),
    ("EngineeringRanking300.html", "201-300"),
]
UA = {"User-Agent": "Mozilla/5.0 (college-priority-dashboard NIRF directory builder)"}

# Ranked rows look like:
#   <tr><td>IR-E-U-0456</td><td>NAME<div>...More Details...<nested table>...</div></td>
#   <td>City</td><td>State</td><td>Score</td><td>Rank</td></tr>
ROW_TAIL = re.compile(
    r"<td[^>]*>\s*([^<>]+?)\s*</td>\s*<td[^>]*>\s*([^<>]+?)\s*</td>"
    r"\s*<td[^>]*>\s*([\d.]+)\s*</td>\s*<td[^>]*>\s*(\d+)\s*</td>\s*</tr>", re.I)


def extract_pr(part):
    """Perception (PR) score from the row's nested parameter table.
    The details table has headers like "TLR (100)" ... "PERCEPTION (100)"
    followed by a row of values; take the value under the perception column."""
    ths = re.findall(r"<th[^>]*>\s*(.*?)\s*</th>", part, re.S)
    idx = next((i for i, t in enumerate(ths)
                if "PERCEPTION" in t.upper() or re.match(r"PR\s*\(", t.strip(), re.I)), None)
    if idx is None:
        return None
    m = re.search(r"</thead>\s*<tbody[^>]*>\s*<tr[^>]*>(.*?)</tr>", part, re.S)
    if not m:
        return None
    tds = re.findall(r"<td[^>]*>\s*([\d.]+)\s*</td>", m.group(1))
    if idx < len(tds):
        try:
            return float(tds[idx])
        except ValueError:
            return None
    return None


def parse_ranked(html):
    out = []
    parts = re.split(r"(?=<tr[^>]*>\s*<td[^>]*>\s*IR-)", html)
    first_diag = True
    for part in parts[1:]:
        m = re.match(r"<tr[^>]*>\s*<td[^>]*>\s*(IR-[A-Za-z0-9-]+)\s*</td>\s*<td[^>]*>\s*([^<]+)", part)
        if not m:
            continue
        name = re.sub(r"\s+", " ", m.group(2)).strip()
        tails = ROW_TAIL.findall(part)  # last match is the outer row's own tail
        if not name or not tails:
            continue
        city, state, _score, rank = tails[-1]
        pr = extract_pr(part)
        if pr is None and first_diag:
            first_diag = False
            print("    DIAG no PR in first row; excerpt: "
                  + re.sub(r"\s+", " ", part[:1200]))
        out.append((name, city.strip(), state.strip(), int(rank), pr))
    return out


def parse_band(html, band):
    out = []
    body = html.split("<tbody", 1)[-1]
    for m in re.finditer(
            r"<tr[^>]*>\s*<td[^>]*>\s*([^<>]+?)\s*</td>\s*<td[^>]*>\s*([^<>]+?)\s*</td>"
            r"\s*<td[^>]*>\s*([^<>]+?)\s*</td>\s*</tr>", body):
        name, city, state = (re.sub(r"\s+", " ", g).strip() for g in m.groups())
        if len(name) < 4 or name.replace(".", "").isdigit():
            continue
        out.append((name, city, state, band, None))
    return out


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s.lower())).strip()


def main():
    merged = {}
    counts = {}
    for year in YEARS:
        year_rows = 0
        for suffix, band in PAGES:
            url = f"https://www.nirfindia.org/Rankings/{year}/{suffix}"
            try:
                resp = requests.get(url, headers=UA, timeout=60)
            except requests.RequestException as exc:
                print(f"  {url} -> ERROR {exc}")
                continue
            if resp.status_code != 200:
                print(f"  {url} -> HTTP {resp.status_code} (skipped)")
                continue
            rows = parse_ranked(resp.text) if band is None else parse_band(resp.text, band)
            print(f"  {url} -> {len(rows)} rows")
            if not rows:
                body = resp.text.split("<tbody", 1)[-1]
                print("    DIAG tbody head: " + re.sub(r"\s+", " ", body[:600]))
            year_rows += len(rows)
            prs = sum(1 for r in rows if r[4] is not None)
            if band is None:
                print(f"    perception scores parsed: {prs}/{len(rows)}")
            for name, city, state, rank, pr in rows:
                key = norm(name) + "|" + norm(city)
                e = merged.setdefault(key, {"n": name, "c": city, "s": state,
                                            "r25": None, "r24": None, "r23": None,
                                            "p25": None, "p24": None, "p23": None})
                e[f"r{year % 100}"] = rank
                if pr is not None:
                    e[f"p{year % 100}"] = pr
        counts[year] = year_rows
        if year_rows < 95:
            print(f"SANITY FAIL: only {year_rows} rows parsed for {year}")
            sys.exit(1)
        if year_rows < 250:
            print(f"WARNING: only {year_rows} rows for {year} (bands may be missing)")

    entries = sorted(merged.values(), key=lambda e: norm(e["n"]))
    print(f"merged institutes: {len(entries)}")

    with open("index.html", encoding="utf-8") as f:
        src = f.read()
    payload = json.dumps(entries, ensure_ascii=False, separators=(",", ":"))
    stamp = datetime.date.today().isoformat()
    src = re.sub(
        r"/\* NIRF_DIRECTORY_START \*/[\s\S]*?/\* NIRF_DIRECTORY_END \*/",
        lambda _m: f"/* NIRF_DIRECTORY_START */\nconst NIRF_DIRECTORY = {payload};\n/* NIRF_DIRECTORY_END */",
        src, count=1)
    src = re.sub(
        r"/\* NIRF_DIRECTORY_META_START \*/[\s\S]*?/\* NIRF_DIRECTORY_META_END \*/",
        f'/* NIRF_DIRECTORY_META_START */\nconst NIRF_META = "official nirfindia.org engineering rankings, fetched {stamp}";\n/* NIRF_DIRECTORY_META_END */',
        src, count=1)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(src)
    print(f"index.html updated ({stamp}); per-year rows: {counts}")


if __name__ == "__main__":
    main()
