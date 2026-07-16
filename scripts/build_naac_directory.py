#!/usr/bin/env python3
"""Build the NAAC accreditation directory from NAAC's EC all-cycles list.

Source: http://218.248.45.212/naac_EC/NAAC_allcycles_accrlist.aspx — NAAC's
public "Accreditation Status" search (ASP.NET WebForms). For each of the
West-zone states (Maharashtra, Gujarat, Goa) and both institute types the
form is posted and every page of the results grid is collected.

Writes the records between NAAC_DIRECTORY_START/END markers in index.html
(added on first run) and a diagnostic report to probe/naac_fetch_report.txt.
"""
import datetime
import json
import os
import re
import sys

import requests

URL = "http://218.248.45.212/naac_EC/NAAC_allcycles_accrlist.aspx"
UA = {"User-Agent": "Mozilla/5.0 (college-priority-dashboard NAAC directory builder)"}
STATES = ["Maharashtra", "Gujarat", "Goa"]
TYPES = ["College", "University"]

report = []


def log(msg):
    report.append(msg)
    print(msg)


def parse_inputs(html):
    fields = {}
    for tag in re.findall(r"<input[^>]+>", html):
        name = re.search(r'name="([^"]+)"', tag)
        if not name:
            continue
        typ = (re.search(r'type="([^"]+)"', tag) or [None, ""])[1]
        val = (re.search(r'value="([^"]*)"', tag) or [None, ""])[1]
        fields[name.group(1)] = {"type": typ, "value": val}
    return fields


def state_codes(html):
    m = re.search(r'<select[^>]*name="ddl_state"[^>]*>(.*?)</select>', html, re.S)
    codes = {}
    for v, t in re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)', m.group(1)):
        codes[t.strip()] = v
    return codes


def strip_cells(row_html):
    return [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", td)).strip()
            for td in re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S)]


def parse_grid(html):
    """headers + data rows of the largest table in the response"""
    best = None
    for table in re.findall(r"<table[^>]*>(.*?)</table>", html, re.S):
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S)
        if best is None or len(rows) > len(best):
            best = rows
    if not best:
        return [], []
    headers = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)).strip()
               for h in re.findall(r"<th[^>]*>(.*?)</th>", "".join(best[:2]), re.S)]
    data = [c for c in (strip_cells(r) for r in best) if len(c) >= 3]
    return headers, data


def pager_targets(html):
    """__doPostBack targets for further grid pages"""
    return sorted(set(re.findall(
        r"__doPostBack\('([^']+)','(Page\$\d+)'\)", html)), key=lambda x: int(x[1].split("$")[1]))


def post(sess, page_html, extra, drop_buttons=True):
    data = {}
    for name, f in parse_inputs(page_html).items():
        if drop_buttons and f["type"] in ("submit", "button", "image"):
            continue
        data[name] = f["value"]
    data.setdefault("__EVENTTARGET", "")
    data.setdefault("__EVENTARGUMENT", "")
    data.update(extra)
    r = sess.post(URL, headers=UA, data=data, timeout=90)
    r.raise_for_status()
    return r.text


def main():
    sess = requests.Session()
    r = sess.get(URL, headers=UA, timeout=90)
    r.raise_for_status()
    landing = r.text
    codes = state_codes(landing)
    log(f"landing ok ({len(landing)} bytes); states parsed: {len(codes)}")
    buttons = {n: f for n, f in parse_inputs(landing).items() if f["type"] == "submit"}
    log(f"submit buttons: {buttons}")
    btn = next(iter(buttons), None)

    records, headers_seen = [], []
    for st in STATES:
        code = codes.get(st) or codes.get(st + " ")
        if not code:
            log(f"!! no state code for {st}; options: {list(codes)[:40]}")
            continue
        for typ in TYPES:
            extra = {"ddl_institype": typ, "ddl_state": code, "txt_Instnm": ""}
            if btn:
                extra[btn] = buttons[btn]["value"] or "Search"
            html = post(sess, landing, extra)
            headers, data = parse_grid(html)
            if headers and headers not in headers_seen:
                headers_seen.append(headers)
                log(f"GRID HEADERS ({st}/{typ}): {headers}")
            page = 1
            total_rows = 0
            while True:
                for cells in data:
                    if len(cells) < 5 or not cells[0].strip().isdigit():
                        continue
                    status = cells[2].split()
                    dates = re.findall(r"\d{2}/\d{2}/\d{4}", cells[3])
                    records.append({
                        "n": cells[1], "s": st, "ty": typ,
                        "g": status[-1] if status else None,
                        "d": dates[-1] if dates else None,
                        "hist": (cells[2] + " | " + cells[4]).strip(),
                    })
                total_rows += len(data)
                targets = [t for t in pager_targets(html)
                           if int(t[1].split("$")[1]) == page + 1]
                if not targets:
                    break
                page += 1
                gv, arg = targets[0]
                html = post(sess, html, {"__EVENTTARGET": gv, "__EVENTARGUMENT": arg,
                                         "ddl_institype": typ, "ddl_state": code,
                                         "txt_Instnm": ""})
                headers, data = parse_grid(html)
            log(f"{st} / {typ}: {total_rows} rows over {page} page(s)")
            if total_rows:
                for rec in records[-min(3, total_rows):]:
                    log(f"  SAMPLE: {rec}")

    log(f"total raw rows: {len(records)}")
    os.makedirs("probe", exist_ok=True)
    with open("probe/naac_fetch_report.txt", "w") as f:
        f.write("\n".join(report) + "\n")

    if len(records) < 100:
        log("SANITY FAIL: too few rows; not touching index.html")
        sys.exit(0)  # keep the report committable

    payload = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    stamp = datetime.date.today().isoformat()
    ec_dates = sorted((r["d"] for r in records if r["d"]),
                      key=lambda d: d[-4:] + d[3:5] + d[:2])
    span = f"EC dates {ec_dates[0]} to {ec_dates[-1]}" if ec_dates else "no EC dates"
    with open("index.html", encoding="utf-8") as f:
        src = f.read()
    block = (f"/* NAAC_DIRECTORY_START */\n"
             f"const NAAC_META = \"official NAAC EC all-cycles accreditation list ({span}), fetched {stamp}\";\n"
             f"const NAAC_DIRECTORY = {payload};\n"
             f"/* NAAC_DIRECTORY_END */")
    if "/* NAAC_DIRECTORY_START */" in src:
        src = re.sub(r"/\* NAAC_DIRECTORY_START \*/[\s\S]*?/\* NAAC_DIRECTORY_END \*/",
                     lambda _m: block, src, count=1)
    else:
        src = src.replace("/* NIRF_DIRECTORY_END */",
                          "/* NIRF_DIRECTORY_END */\n\n" + block, 1)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(src)
    log(f"index.html updated with {len(records)} NAAC records ({stamp})")


if __name__ == "__main__":
    main()
