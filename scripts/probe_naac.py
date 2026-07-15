#!/usr/bin/env python3
"""Download the UGC-hosted official NAAC-accredited colleges list (PDF) and
commit a text extract so its vintage/columns can be reviewed."""
import os
import re
import requests
from pypdf import PdfReader

UA = {"User-Agent": "Mozilla/5.0 (college-priority-dashboard NAAC probe)"}
URL = "https://www.ugc.gov.in/pdfnews/0646280_State-wise-list--of-colleges-accredited-by-NAAC.pdf"

r = requests.get(URL, headers=UA, timeout=120)
r.raise_for_status()
open("/tmp/naac.pdf", "wb").write(r.content)
reader = PdfReader("/tmp/naac.pdf")
out = [f"pages: {len(reader.pages)} | bytes: {len(r.content)}", ""]

out.append("== first page ==")
out.append(reader.pages[0].extract_text()[:2500])

# find pages mentioning the West-zone states and sample them
hits = {"Maharashtra": None, "Gujarat": None, "Goa": None}
for i, page in enumerate(reader.pages):
    t = page.extract_text() or ""
    for st in hits:
        if hits[st] is None and re.search(st, t, re.I):
            hits[st] = i
    if all(v is not None for v in hits.values()):
        break
for st, i in hits.items():
    out.append(f"\n== first page mentioning {st}: {i} ==")
    if i is not None:
        out.append((reader.pages[i].extract_text() or "")[:2500])

os.makedirs("probe", exist_ok=True)
open("probe/naac_probe.txt", "w").write("\n".join(out) + "\n")
print("\n".join(out[:6]))
