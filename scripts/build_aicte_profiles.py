#!/usr/bin/env python3
"""Auto-seed Programmes + Batch/Intake profile fields from AICTE's official
approved-intake data.

Source: AICTE's own approved-course endpoint
`facilities.aicte-india.org/dashboard/pages/php/approvedcourse.php` (2025-26),
reduced to clean per-state JSON by the open mirror
`github.com/anburocky3/indian-colleges-data` (data/states/<state>.json). Each
programme row carries programme/level/course/intake, which we aggregate by
(course, level) into the dashboard's `programs` ([name, level]) and `batch`
([name, intake]) profile shapes.

The 164-college West baseline is matched to AICTE institutions by fuzzy
name+district. Because this dashboard drives real hiring decisions, matches
are hand-reviewed: BLOCK excludes high-scoring but wrong namesakes / wrong
sub-entities (Polytechnic, Institute of Management, a different campus), ALLOW
promotes correct matches whose score was diluted by a long trust prefix, and a
collision guard drops any college that resolves to an entry already taken.
Only colleges with no programmes and no batch yet are touched (the NIRF-ranked
colleges and hand-built profiles are left alone).

Report-only by default; pass --apply to rewrite index.html.
The per-state JSON is fetched from the mirror on first run (cached under
probe/aicte/), or read from a local --data-dir.
"""
import json, re, sys, os, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, "index.html")
DATA = os.path.join(ROOT, "probe", "aicte")
MIRROR = ("https://raw.githubusercontent.com/anburocky3/indian-colleges-data/"
          "master/data/states/{}.json")
STATES = {"maharashtra": "Maharashtra", "gujarat": "Gujarat", "goa": "Goa"}
YEAR = "2025-26"
THRESH = 0.82


def state_path(key):
    os.makedirs(DATA, exist_ok=True)
    p = os.path.join(DATA, f"{key}.json")
    if not os.path.exists(p):
        url = MIRROR.format(key)
        print(f"fetching {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "west-aicte-seed"})
        with urllib.request.urlopen(req, timeout=120) as r, open(p, "wb") as f:
            f.write(r.read())
    return p

# ---- fuzzy matcher (same shape as official_sweep.py) --------------------
def norm(s): return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower())).strip()
STOP = {"of","and","the","for","institute","college","engineering","technology",
        "university","management","science","sciences","studies","s","trust",
        "education","society","societys","charitable"}
def sig(s): return [t for t in norm(s).split() if len(t) > 1]
def score(qn, qc, en, ec):
    qt = sig(qn); hay = norm(en + " " + (ec or ""))
    if not qt: return 0.0
    frac = sum(1 for t in qt if t in hay) / len(qt)
    qs = set(t for t in qt if t not in STOP); es = set(t for t in sig(en) if t not in STOP)
    s = len(qs & es) / max(len(qs), len(es)) if qs and es else 0.0
    return (frac + s) / 2 + (0.12 if qc and ec and norm(qc) in norm(ec) else 0.0)

# ---- name / level tidy --------------------------------------------------
LEVEL = {
    "UNDER GRADUATE": "UG", "UNDERGRADUATE": "UG",
    "POST GRADUATE": "PG", "POSTGRADUATE": "PG",
    "POST GRADUATE DIPLOMA": "PG Diploma", "PG DIPLOMA": "PG Diploma",
    "DIPLOMA": "Diploma", "POST DIPLOMA": "Post Diploma",
    "INTEGRATED": "Integrated", "DOCTORATE": "Doctoral", "PHD": "Doctoral",
}
LVL_RANK = {"UG": 0, "Integrated": 1, "PG": 2, "PG Diploma": 3,
            "Post Diploma": 4, "Diploma": 5, "Doctoral": 6}
ACR = {"cad","cam","it","ai","ml","iot","vlsi","cse","ece","eee","mba","mca",
       "ic","hvac","gis","vlsi","ev","rf"}
SMALL = {"and","or","in","of","for","to","with","the","a","an"}
def _cap(m):
    w = m.group(0)
    return w.upper() if w.lower() in ACR else w[:1].upper() + w[1:].lower()
def title(s):
    s = re.sub(r"\s+", " ", s).strip()
    out = []
    for i, tok in enumerate(s.split(" ")):
        # title-case the first letter of every alphabetic run (handles a leading
        # "(" or digit), keeping known acronyms upper-cased
        t = re.sub(r"[A-Za-z]+", _cap, tok)
        if i > 0 and t.isalpha() and t.lower() in SMALL:
            t = t.lower()
        out.append(t)
    return " ".join(out)
def lvl(s):
    s = (s or "").strip().upper()
    return LEVEL.get(s, title(s))

# ---- AICTE index --------------------------------------------------------
def aicte_institutions():
    insts = []
    for key, st in STATES.items():
        data = json.load(open(state_path(key)))
        for inst in data:
            agg = {}   # (course,level) -> intake
            for p in inst.get("programmes", []):
                c = (p.get("course") or "").strip()
                lv = lvl(p.get("level"))
                if not c:
                    continue
                try:
                    n = int(float(p.get("intake") or 0))
                except ValueError:
                    n = 0
                agg[(c, lv)] = agg.get((c, lv), 0) + n
            if not agg:
                continue
            # district as the "city" signal
            insts.append({
                "name": inst["institute_name"], "dist": inst.get("district", ""),
                "state": st, "agg": agg,
            })
    return insts

def build_fields(agg):
    # course-name -> set of levels (to detect ambiguity for batch labels)
    levels_by_course = {}
    for (c, lv) in agg:
        levels_by_course.setdefault(c, set()).add(lv)
    rows = sorted(agg.items(), key=lambda kv: (LVL_RANK.get(kv[0][1], 9), kv[0][0]))
    programs, batch = [], []
    for (c, lv), n in rows:
        name = title(c)
        programs.append([name, lv])
        label = name
        if len(levels_by_course[c]) > 1:
            label = f"{name} ({lv})"
        batch.append([label, n])
    return programs, batch

# ---- baseline colleges --------------------------------------------------
src = open(HTML, encoding="utf-8").read()
m = re.search(r"(const COLLEGES = \[\n)(.*?)(\n\];)", src, re.S)
lines = m.group(2).split("\n")
cols = []
for idx, ln in enumerate(lines):
    obj = json.loads(ln.rstrip(","))
    cols.append((idx, obj))

insts = aicte_institutions()
print(f"AICTE West institutions: {len(insts)} | baseline colleges: {len(cols)}\n")

def has(v): return bool(v) and (len(v) if isinstance(v, (list, str)) else True)

# Hand-reviewed exclusions: high-scoring but WRONG (namesakes / wrong sub-entity).
BLOCK = {
    "K. J. Somaiya College of Engineering",              # -> KJ Somaiya Inst of Tech, Sion (different)
    "Maharaja Sayajirao University of Baroda",            # -> MSU Polytechnic wing
    "SVKM's Narsee Monjee Institute of Management Studies",  # -> NMIMS Dhule/Shirpur campus
    "AISSMS College of Engineering",                     # -> AISSMS Institute of Management
    "Dr DY Patil School of Engineering, Pune",           # -> Ajeenkya DY Patil (different)
    "Maharshi Karve Stree Shikshan Samstha Cummins College of Engineering for Women, Nagpur",  # -> Pune Cummins
    "MIT School of Engineering, Pune",                   # -> MIT School of Distance Education
    "Modern Education Society's College of Engineering, Pune",  # -> PES Modern (different society)
    "Priyadarshini College of Engineering, Nagpur",      # -> Priyadarshini Bhagwati COE (different)
    "Sandip Foundation, Nashik",                         # -> Sandip Polytechnic
}
# Hand-reviewed inclusions: correct match whose fuzzy score fell below THRESH only
# because of a long trust prefix / punctuation. Trust the fuzzy best for these.
ALLOW = {
    "Sandip Institute of Technology and Research Center, Nashik",
    "SB Jain Institute of Technology Management and Research, Nagpur",
    "Bhivarabai Sawant Institute of Technology and Research, Wagholi, Pune",
    "Annasaheb Dange College of Engineering and Technology (ADCET), Sangli",
    "Thakur College of Engineering and Technology, Mumbai",
    "Sipna College of Engineering and Technology, Amravati",
    "Sandip Institute of Engineering and Management, Nashik",
    "Parul Institute of Engineering and Technology, Vadodara",
    "LDRP Institute of Technology and Research, Gandhinagar",
    "Sanjivani College of Engineering, Kopargaon",
    "RH Sapat College of Engineering, Management Studies and Research, Nashik",
    "New Horizon Institute of Technology and Management, Thane",
    "Atharva College of Engineering, Malad",
    "Tatyasaheb Kore Institute of Engineering & Technology, Warananagar",
    "KK Wagh Institute of Engineering Education and Research, Nashik",
    "Bhagwant Institute of Technology, Solapur",
    "Jawahar Education Society's AC Patil College of Engineering, Navi Mumbai",
    "Vidyavardhini's College of Engineering and Technology, Vasai",
    "SIES Graduate School of Technology, Navi Mumbai",
    "Terna Public Charitable Trust's Terna Engineering College, Navi Mumbai",
    "Dharmsinh Desai University - Engineering Department",
    "Goa College of Engineering, Farmagudi, Ponda",
    "Birla Vishvakarma Mahavidyalaya Engineering College (BVM)",
    "Dr JJ Magdum College of Engineering, Jaysingpur",
    "GS Mandal's Maharashtra Institute of Technology, Aurangabad",
    "AP Shah Institute of Technology, Thane",
}
BLOCK_N = {norm(x) for x in BLOCK}
ALLOW_N = {norm(x) for x in ALLOW}
# fail loud if a curated name no longer resolves to exactly one baseline college
base_norms = [norm(c["name"]) for _, c in cols]
for label, S in (("BLOCK", BLOCK_N), ("ALLOW", ALLOW_N)):
    for n in S:
        cnt = base_norms.count(n)
        if cnt != 1:
            print(f"!! {label} name resolves to {cnt} baseline colleges: {n}")
            sys.exit(1)

matches, skipped_have, no_match, low = [], [], [], []
for idx, c in cols:
    if has(c.get("programs")) or has(c.get("batch")):
        skipped_have.append(c["name"]); continue
    city = (c.get("loc") or "").split(",")[0].strip()
    sc, e = max(((score(c["name"], city, x["name"], x["dist"]), x) for x in insts),
                key=lambda t: t[0], default=(0, None))
    nn = norm(c["name"])
    applied = e is not None and nn not in BLOCK_N and (sc >= THRESH or nn in ALLOW_N) and sc >= 0.55
    if not applied:
        if e is None or sc < 0.60:
            no_match.append((c["name"], round(sc, 2), e["name"] if e else ""));
        else:
            low.append((round(sc, 2), c["name"], city, e["name"], e["dist"]))
        continue
    programs, batch = build_fields(e["agg"])
    matches.append((round(sc, 2), idx, c, e, programs, batch))

# collision safety net: if two colleges resolved to the same AICTE institution,
# keep the higher score and drop the rest (prevents a stray namesake slipping in)
by_inst = {}
for rec in matches:
    by_inst.setdefault(rec[3]["name"], []).append(rec)
keep = []
for en, lst in by_inst.items():
    lst.sort(key=lambda r: -r[0])
    keep.append(lst[0])
    for r in lst[1:]:
        print(f"!! COLLISION dropped: {r[2]['name']} (also -> {en})")
matches = sorted(keep, key=lambda x: -x[0])

print(f"=== APPLYING: {len(matches)} colleges ===")
for sc, idx, c, e, programs, batch in matches:
    tot = sum(n for _, n in batch)
    tag = " [ALLOW]" if norm(c["name"]) in ALLOW_N else ""
    print(f"[{sc:.2f}]{tag} {c['name']}  ({c.get('loc')})")
    print(f"        -> {e['name']} / {e['dist']} · {len(programs)} courses · {tot} seats")

print(f"\n=== NOT applied — borderline ({len(low)}) ===")
for sc, cn, city, en, dist in sorted(low, reverse=True):
    print(f"[{sc:.2f}] {cn} ({city})  ?->  {en} / {dist}")

print(f"\n=== NOT applied — no match ({len(no_match)}) ===")
for cn, sc, en in sorted(no_match, key=lambda x: -x[1]):
    print(f"[{sc:.2f}] {cn}   best: {en}")

print(f"\n=== already had programmes/batch ({len(skipped_have)}) ===")
print("  " + ", ".join(skipped_have))

# split-entry diagnostic: another AICTE entry in the same state nearly identical
# to the chosen one means this college is split and we're under-reporting.
def tset(s): return set(t for t in sig(s) if t not in STOP)
print("\n=== POSSIBLE SPLIT ENTRIES (review) ===")
by_state = {}
for x in insts:
    by_state.setdefault(x["state"], []).append(x)
flagged = 0
for sc, idx, c, e, programs, batch in matches:
    ce = tset(e["name"])
    for x in by_state[e["state"]]:
        if x is e:
            continue
        xs = tset(x["name"])
        j = len(ce & xs) / max(len(ce | xs), 1)
        if j >= 0.7:
            print(f"  {c['name']}\n     chose: {e['name']} ({sum(n for _,n in batch)} seats, {len(e['agg'])} courses)"
                  f"\n     also : {x['name']} ({sum(x['agg'].values())} seats, {len(x['agg'])} courses)  j={j:.2f}")
            flagged += 1
            break
if not flagged:
    print("  (none)")

# non-ASCII guard in generated fields
print("\n=== NON-ASCII in generated names (review) ===")
bad = 0
for sc, idx, c, e, programs, batch in matches:
    for label, arr in (("prog", [p[0] for p in programs]), ("batch", [b[0] for b in batch])):
        for v in arr:
            if any(ord(ch) > 126 for ch in v):
                print(f"  {c['name']} [{label}] {v!r}"); bad += 1
if not bad:
    print("  (none)")

if "--apply" in sys.argv:
    src_note = f"AICTE approved intake {YEAR}"
    for sc, idx, c, e, programs, batch in matches:
        c["programs"] = programs
        c["batch"] = batch
        c["progSrc"] = src_note
        lines[idx] = json.dumps(c, ensure_ascii=False, separators=(",", ":")) + \
            ("," if idx < len(lines) - 1 else "")
    newblock = "\n".join(lines)
    src2 = src[:m.start(2)] + newblock + src[m.end(2):]
    open(HTML, "w", encoding="utf-8").write(src2)
    print(f"\nAPPLIED {len(matches)} colleges to index.html")
