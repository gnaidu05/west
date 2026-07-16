#!/usr/bin/env python3
"""Probe NAAC's EC all-cycles accreditation list page (raw-IP server the
team can reach) and report its form/table structure."""
import os
import re
import requests

UA = {"User-Agent": "Mozilla/5.0 (college-priority-dashboard NAAC probe)"}
URL = "http://218.248.45.212/naac_EC/NAAC_allcycles_accrlist.aspx"
out = [f"URL: {URL}"]
try:
    r = requests.get(URL, headers=UA, timeout=90)
    out.append(f"HTTP {r.status_code} | {r.headers.get('content-type','?')} | {len(r.content)} bytes")
    t = r.text
    out.append("TITLE: " + "".join(re.findall(r"<title>(.*?)</title>", t, re.S))[:120])
    out.append("FORM actions: " + str(re.findall(r'<form[^>]*action="([^"]*)"', t)[:3]))
    out.append("VIEWSTATE present: " + str("__VIEWSTATE" in t)
               + " | EVENTVALIDATION: " + str("__EVENTVALIDATION" in t))
    for name, sel in re.findall(r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>', t, re.S)[:6]:
        opts = re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)', sel)
        out.append(f"SELECT {name}: {len(opts)} options; first: {opts[:8]}")
    inputs = re.findall(r'<input[^>]*name="([^"]+)"[^>]*type="([^"]+)"', t)[:20]
    out.append("INPUTS: " + str(inputs))
    ths = re.findall(r"<th[^>]*>\s*(.*?)\s*</th>", t, re.S)[:20]
    out.append("TABLE HEADERS: " + str([re.sub(r"<[^>]+>|\s+", " ", h).strip() for h in ths]))
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S)
    out.append(f"TR count: {len(rows)}")
    for row in rows[1:4]:
        tds = [re.sub(r"<[^>]+>|\s+", " ", td).strip() for td in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        out.append("  ROW: " + str(tds[:10]))
    out.append("HEAD EXCERPT: " + re.sub(r"\s+", " ", t[:1500]))
except Exception as exc:
    out.append(f"ERROR {exc}")

os.makedirs("probe", exist_ok=True)
open("probe/naac_probe.txt", "w").write("\n".join(out) + "\n")
print("\n".join(out[:8]))
