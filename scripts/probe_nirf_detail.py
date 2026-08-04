#!/usr/bin/env python3
"""Dump NIRF 2025 data-PDF text for a few West institutes so the
intake / median-salary / placement extraction can be designed."""
import os, re, io, requests
from pypdf import PdfReader

UA = {"User-Agent": "Mozilla/5.0 (college-priority-dashboard NIRF probe)"}
Y = 2025
PDF = "https://www.nirfindia.org/nirfpdfcdn/{y}/pdf/Engineering/{ir}.pdf"
out = []
def log(m): out.append(str(m)); print(m)

html = requests.get(f"https://www.nirfindia.org/Rankings/{Y}/EngineeringRanking.html",
                    headers=UA, timeout=90).text

# parse rows: IR id + institute name + ... + city + state + score + rank
rows = []
for part in re.split(r"(?=<tr[^>]*>\s*<td[^>]*>\s*IR-)", html)[1:]:
    m = re.match(r"<tr[^>]*>\s*<td[^>]*>\s*(IR-E-[A-Za-z0-9-]+)\s*</td>\s*<td[^>]*>\s*([^<]+)", part)
    if not m: continue
    ir, name = m.group(1), re.sub(r"\s+", " ", m.group(2)).strip()
    tails = re.findall(r"<td[^>]*>\s*([^<>]+?)\s*</td>\s*<td[^>]*>\s*([^<>]+?)\s*</td>"
                       r"\s*<td[^>]*>\s*([\d.]+)\s*</td>\s*<td[^>]*>\s*(\d+)\s*</td>\s*</tr>", part)
    if not tails: continue
    city, state, _s, rank = tails[-1]
    rows.append((ir, name, city.strip(), state.strip(), int(rank)))

west = [r for r in rows if r[3] in ("Maharashtra", "Gujarat", "Goa")]
log(f"ranked institutes: {len(rows)} | West: {len(west)}")
for r in west: log(f"  {r[4]:>3}  {r[0]}  {r[1][:48]}  ({r[2]}, {r[3]})")

# dump text for the two highest-ranked West institutes
for ir, name, city, state, rank in sorted(west, key=lambda x: x[4])[:2]:
    log(f"\n===== #{rank} {name} [{ir}] =====")
    rr = requests.get(PDF.format(y=Y, ir=ir), headers=UA, timeout=60)
    log(f"pdf HTTP {rr.status_code} {rr.headers.get('content-type')} {len(rr.content)}B")
    if rr.status_code != 200: continue
    txt = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(rr.content)).pages)
    lines = [re.sub(r"\s+", " ", l).strip() for l in txt.splitlines() if l.strip()]
    # print lines around intake / salary / placement keywords
    for i, l in enumerate(lines):
        if re.search(r"intake|median salary|placement|higher stud|total student|graduat", l, re.I):
            ctx = " ⏎ ".join(lines[i:i+3])
            log(f"  L{i}: {ctx[:160]}")

os.makedirs("probe", exist_ok=True)
open("probe/nirf_detail_probe.txt", "w").write("\n".join(out) + "\n")
