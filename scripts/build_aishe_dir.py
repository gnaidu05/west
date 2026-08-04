#!/usr/bin/env python3
"""Replace the stale EC-sourced NAAC_DIRECTORY with a clean, current directory
built directly from the AISHE workbook (West-zone institutions + latest NAAC
grade, validity and declaration date). Single source, no fuzzy matching."""
import openpyxl, json, re, sys, datetime, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XL = os.path.join(ROOT, "probe", "aishe", "aishe_west.xlsx")
HTML = os.path.join(ROOT, "index.html")
TODAY = "2026-08-04"

wb = openpyxl.load_workbook(XL, read_only=True, data_only=True)
irows = list(wb["Institutions"].iter_rows(min_row=1, values_only=True))
ih = {h: i for i, h in enumerate(irows[0])}
STATE_FIX = {"The Dadra and Nagar Haveli and Daman and Diu": "Dadra & Nagar Haveli and Daman & Diu"}
def g_(v):
    v = (v or "").strip().upper(); return "" if v in ("", "N/A", "NA", "-", "NONE") else v
def date_(v):
    if not v: return ""
    if isinstance(v, datetime.datetime): return v.strftime("%d/%m/%Y")
    s = str(v).strip().replace("-", "/")
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", s)
    return f"{m.group(1)}/{m.group(2)}/{m.group(3)}" if m else ""

recs = []
for r in irows[1:]:
    name = (r[ih["Institute Name"]] or "").strip()
    name = re.sub(r"^\d{4,8}\s*-\s*", "", name)   # strip AISHE code prefixes like "100007-"
    if not name: continue
    st = (r[ih["State"]] or "").strip(); st = STATE_FIX.get(st, st)
    if not st: continue
    itype = (r[ih["Institute Type"]] or "")
    rec = {"n": name, "s": st, "dist": (r[ih["District"]] or "").strip(),
           "ty": "University" if "univ" in itype.lower() else "College",
           "g": g_(r[ih["Latest NAAC Grade"]]),
           "val": (r[ih["NAAC Validity"]] or "").strip().replace("N/A", ""),
           "d": date_(r[ih["Date of Declaration"]])}
    recs.append(rec)

recs.sort(key=lambda x: (x["s"], x["n"].lower()))
graded = sum(1 for x in recs if x["g"])
from collections import Counter
print(f"AISHE West institutions: {len(recs)} | accredited (with grade): {graded}")
print("by state:", Counter(x["s"] for x in recs).most_common())
print("by grade:", Counter(x["g"] or "—" for x in recs).most_common())

if "--apply" in sys.argv:
    src = open(HTML, encoding="utf-8").read()
    payload = json.dumps(recs, ensure_ascii=False, separators=(",", ":"))
    meta = (f'const NAAC_META = "NAAC accreditation directory — {len(recs)} West-zone '
            f'institutions ({graded} accredited), latest grades from AISHE, fetched {TODAY}";')
    src = re.sub(r'const NAAC_META = "[^"]*";', meta, src, count=1)
    src = re.sub(r"const NAAC_DIRECTORY = \[.*?\];",
                 "const NAAC_DIRECTORY = " + payload + ";", src, count=1, flags=re.S)
    open(HTML, "w", encoding="utf-8").write(src)
    print(f"\nAPPLIED: NAAC_DIRECTORY replaced with {len(recs)} AISHE records")
