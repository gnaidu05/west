#!/usr/bin/env python3
"""Probe official NAAC sources for a machine-readable accreditation list.
Writes findings to probe/naac_probe.txt (committed by the probe workflow)."""
import os
import re
import requests

UA = {"User-Agent": "Mozilla/5.0 (college-priority-dashboard NAAC probe)"}
out = []

def probe(url, note, grab=None, post=None, data=None):
    out.append(f"\n=== {note}\n{url}")
    try:
        r = (requests.post(url, headers=UA, data=data, timeout=60) if post
             else requests.get(url, headers=UA, timeout=60))
        out.append(f"HTTP {r.status_code} | {r.headers.get('content-type','?')} | {len(r.content)} bytes")
        if r.status_code != 200:
            return None
        text = r.text
        if grab == "links":
            links = re.findall(r'href="([^"]+)"[^>]*>([^<]{0,80})', text)
            hits = [(u, t.strip()) for u, t in links
                    if re.search(r"xls|xlsx|csv|accredit|assessmentonline|status", u, re.I)]
            for u, t in hits[:60]:
                out.append(f"  LINK {u}  |  {t}")
        elif grab == "ajax":
            for pat in (r'"ajax"\s*:\s*["\']([^"\']+)', r"ajax\s*:\s*[\"']([^\"']+)",
                        r'url\s*:\s*["\']([^"\']+)', r'action="([^"]+)"'):
                for h in re.findall(pat, text)[:10]:
                    out.append(f"  AJAX/FORM {h}")
            for h in re.findall(r'<select[^>]*name="([^"]+)"', text)[:15]:
                out.append(f"  SELECT {h}")
            out.append("  EXCERPT: " + re.sub(r"\s+", " ", text[:1500]))
        elif grab == "raw":
            out.append("  EXCERPT: " + re.sub(r"\s+", " ", text[:2500]))
        return r
    except Exception as exc:
        out.append(f"ERROR {exc}")
        return None

probe("http://www.naac.gov.in/index.php/en/2-uncategorised/32-accreditation-status",
      "accreditation status page (plain http)", grab="links")
probe("http://assessmentonline.naac.gov.in/public/index.php/accreditationresults",
      "assessmentonline results (plain http)", grab="ajax")
probe("https://www.ugc.gov.in/pdfnews/0646280_State-wise-list--of-colleges-accredited-by-NAAC.pdf",
      "UGC official state-wise NAAC list (pdf)")
probe("https://www.data.gov.in/backend/dms/v1/ogdp/resource/search?query=naac%20accredited&size=10",
      "data.gov.in resource search API", grab="raw")
probe("https://www.data.gov.in/search?title=naac",
      "data.gov.in search page", grab="links")
probe("https://api.data.gov.in/lists?format=json&notfilters[source]=visualize.data.gov.in&filters[title]=naac",
      "api.data.gov.in lists", grab="raw")

os.makedirs("probe", exist_ok=True)
with open("probe/naac_probe.txt", "w") as f:
    f.write("\n".join(out) + "\n")
print("\n".join(out))
