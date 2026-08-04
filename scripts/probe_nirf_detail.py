#!/usr/bin/env python3
"""Probe NIRF 2025 per-institute data: find the institute-detail / data URL
pattern from the Engineering ranking page and report which fields
(intake, median salary, placement) are extractable. Report only."""
import os, re, requests

UA = {"User-Agent": "Mozilla/5.0 (college-priority-dashboard NIRF detail probe)"}
YEAR = 2025
BASE = f"https://www.nirfindia.org/Rankings/{YEAR}/EngineeringRanking.html"
out = []

def log(m): out.append(m); print(m)

r = requests.get(BASE, headers=UA, timeout=90)
log(f"ranking page: HTTP {r.status_code} | {len(r.content)} bytes")
html = r.text

# IR IDs present
irs = re.findall(r"IR-E-[A-Za-z0-9-]+", html)
log(f"IR IDs found: {len(set(irs))}; sample: {sorted(set(irs))[:6]}")

# any hrefs / onclick / data-* that reference a detail page or pdf
links = re.findall(r'(?:href|onclick|data-[a-z]+)\s*=\s*"([^"]*(?:pdf|Report|institute|Institute|detail|Detail|IR-E)[^"]*)"', html)
log(f"candidate detail links: {len(set(links))}")
for l in sorted(set(links))[:20]:
    log("  LINK " + l)

# pick a sample IR (prefer a West one if identifiable near 'Maharashtra'/'Gujarat')
sample = None
for m in re.finditer(r"(IR-E-[A-Za-z0-9-]+)(.{0,400})", html, re.S):
    if re.search(r"Maharashtra|Gujarat|Goa", m.group(2)):
        sample = m.group(1); break
sample = sample or (sorted(set(irs))[0] if irs else None)
log(f"\nsample IR for detail probe: {sample}")

# candidate detail/data URL patterns to try
cands = [
    f"https://www.nirfindia.org/nirfpdfcdn/{YEAR}/pdf/Engineering/{sample}.pdf",
    f"https://www.nirfindia.org/Rankings/{YEAR}/Report/{sample}.pdf",
    f"https://www.nirfindia.org/{YEAR}/Institutions/{sample}",
    f"https://www.nirfindia.org/DataCapture/Report/{sample}",
    f"https://www.nirfindia.org/Rankings/{YEAR}/Institutions/Institution.html?ID={sample}",
]
for u in cands:
    try:
        rr = requests.get(u, headers=UA, timeout=60)
        ct = rr.headers.get("content-type", "?")
        log(f"\nTRY {u}\n  HTTP {rr.status_code} | {ct} | {len(rr.content)} bytes")
        if rr.status_code == 200 and "pdf" in ct.lower():
            try:
                from pypdf import PdfReader
                import io
                txt = "".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(rr.content)).pages[:6])
                for kw in ["Intake", "Sanctioned", "Median salary", "Median Salary", "Placement", "Total Students", "salary"]:
                    hits = [s.strip()[:90] for s in txt.splitlines() if kw.lower() in s.lower()]
                    if hits: log(f"    [{kw}] " + " | ".join(hits[:2]))
            except Exception as e:
                log(f"    pdf parse error: {e}")
        elif rr.status_code == 200:
            log("    EXCERPT: " + re.sub(r"\s+", " ", rr.text[:400]))
    except Exception as e:
        log(f"TRY {u}\n  ERROR {e}")

os.makedirs("probe", exist_ok=True)
open("probe/nirf_detail_probe.txt", "w").write("\n".join(out) + "\n")
