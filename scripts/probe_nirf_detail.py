#!/usr/bin/env python3
"""Dump the FULL text of two West NIRF-2025 data PDFs to design parsing."""
import os, re, io, requests
from pypdf import PdfReader
UA = {"User-Agent": "Mozilla/5.0 (nirf probe)"}
out = []
def log(m): out.append(str(m)); print(m)
for ir, tag in [("IR-E-U-1257", "COEP #90"), ("IR-E-U-0147", "PDEU #98")]:
    rr = requests.get(f"https://www.nirfindia.org/nirfpdfcdn/2025/pdf/Engineering/{ir}.pdf",
                      headers=UA, timeout=60)
    log(f"\n########## {tag} [{ir}] HTTP {rr.status_code} ##########")
    if rr.status_code != 200: continue
    txt = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(rr.content)).pages)
    for i, l in enumerate([re.sub(r"[ \t]+", " ", x).strip() for x in txt.splitlines() if x.strip()]):
        log(f"{i:>3}: {l}")
os.makedirs("probe", exist_ok=True)
open("probe/nirf_detail_probe.txt", "w").write("\n".join(out) + "\n")
