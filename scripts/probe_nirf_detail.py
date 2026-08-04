#!/usr/bin/env python3
"""Extract intake + median salary + placement from NIRF 2025 data PDFs for
the West ranked institutes; write structured JSON for review/apply."""
import os, re, io, json, requests
from pypdf import PdfReader
UA = {"User-Agent": "Mozilla/5.0 (nirf details)"}
Y = 2025
out, data = [], {}
def log(m): out.append(str(m)); print(m)

html = requests.get(f"https://www.nirfindia.org/Rankings/{Y}/EngineeringRanking.html", headers=UA, timeout=90).text
rows = []
for part in re.split(r"(?=<tr[^>]*>\s*<td[^>]*>\s*IR-)", html)[1:]:
    m = re.match(r"<tr[^>]*>\s*<td[^>]*>\s*(IR-E-[A-Za-z0-9-]+)\s*</td>\s*<td[^>]*>\s*([^<]+)", part)
    if not m: continue
    t = re.findall(r"<td[^>]*>\s*([^<>]+?)\s*</td>\s*<td[^>]*>\s*([^<>]+?)\s*</td>\s*<td[^>]*>\s*([\d.]+)\s*</td>\s*<td[^>]*>\s*(\d+)\s*</td>\s*</tr>", part)
    if t: rows.append((m.group(1), re.sub(r"\s+"," ",m.group(2)).strip(), t[-1][0].strip(), t[-1][1].strip(), int(t[-1][3])))
west = [r for r in rows if r[3] in ("Maharashtra","Gujarat","Goa")]

def latest_int(s):
    for tok in s.split():
        if tok.isdigit(): return int(tok)
    return None

def parse_pdf(txt):
    lines = [re.sub(r"[ \t]+"," ",x).strip() for x in txt.splitlines() if x.strip()]
    joined = "\n".join(lines)
    # intake rows
    intake = []
    m = re.search(r"Sanctioned \(Approved\) Intake(.*?)Total Actual Student Strength", joined, re.S)
    if m:
        for line in m.group(1).splitlines():
            mm = re.match(r"((?:UG|PG|Integrated|Ph\.?D)\s*\[[^\]]*\])\s+([\d\s\-]+)$", line)
            if mm:
                v = latest_int(mm.group(2))
                if v: intake.append([re.sub(r"\s+"," ",mm.group(1)), v])
    # placement blocks
    def block(tag):
        m = re.search(re.escape(tag) + r"(.*?)(?:PG \[|Ph\.D Student Details|$)", joined, re.S)
        return m.group(1) if m else ""
    def last_row(b):
        # rows end with  <graduating> <placed> <median>(words)
        rs = re.findall(r"(\d+)\s+(\d+)\s+(\d{4,8})\(", b)
        return rs[-1] if rs else None
    ug = last_row(block("UG [4 Years Program(s)]: Placement"))
    pg = last_row(block("PG [2 Years Program(s)]: Placement"))
    return intake, ug, pg

for ir, name, city, state, rank in sorted(west, key=lambda x: x[4]):
    rr = requests.get(f"https://www.nirfindia.org/nirfpdfcdn/{Y}/pdf/Engineering/{ir}.pdf", headers=UA, timeout=60)
    if rr.status_code != 200: log(f"{name}: pdf {rr.status_code}"); continue
    txt = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(rr.content)).pages)
    intake, ug, pg = parse_pdf(txt)
    rec = {"ir": ir, "name": name, "city": city, "state": state, "rank": rank, "intake": intake,
           "ug": {"grad": int(ug[0]), "placed": int(ug[1]), "median": int(ug[2])} if ug else None,
           "pg": {"grad": int(pg[0]), "placed": int(pg[1]), "median": int(pg[2])} if pg else None}
    data[name] = rec
    log(f"#{rank} {name[:44]} | intake={intake} | UG={rec['ug']} | PG={rec['pg']}")

os.makedirs("probe", exist_ok=True)
open("probe/nirf_details.json","w").write(json.dumps(data, indent=1, ensure_ascii=False))
open("probe/nirf_detail_probe.txt","w").write("\n".join(out)+"\n")
