#!/usr/bin/env python3
"""Refresh the Programmes + Batch/Intake profile fields of the West-zone
baseline from the curated *All-India NIRF Engineering Intake (2025-26)*
workbook.

Source: `probe/nirf_intake/source_all_india_nirf_intake_2025_26.xlsx`, its
`College Program Master` sheet frozen to
`probe/nirf_intake/west_program_master.json`. Each row is one UG branch of one
institution with its official *Approved / Sanctioned Intake* (AICTE 2025-26
public approvals, or JoSAA-verified for NIRF institutes), normalised branch
name and NIRF-2025 link. We aggregate rows by (branch, level) into the
dashboard's `programs` ([name, level]) and `batch` ([name, intake]) shapes.

Only 56 West-zone institutions appear in the workbook, so only the baseline
colleges that confidently match are updated; everyone else is left untouched.
Because this dashboard drives real hiring decisions, matches are hand-reviewed:
BLOCK excludes high-scoring but wrong namesakes / wrong sub-entities, ALLOW
promotes correct matches whose fuzzy score fell just short, and a collision
guard drops any college resolving to an institution already taken.

Unlike the AICTE seed this REFRESHES: a college that already had programmes/
batch is overwritten from this newer, verified source (its other profile
fields — overview, campuses, placement, etc. — are left intact).

Report-only by default; pass --apply to rewrite index.html.
"""
import json, re, sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, "index.html")
SRCJSON = os.path.join(ROOT, "probe", "nirf_intake", "west_program_master.json")
YEAR = "2025-26"
THRESH = 0.82

# ---- fuzzy matcher (same shape as build_aicte_profiles.py) --------------
def norm(s): return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower())).strip()
STOP = {"of","and","the","for","institute","college","engineering","technology",
        "university","management","science","sciences","studies","s","trust",
        "education","society","societys","charitable","deemed","to","be"}
def sig(s): return [t for t in norm(s).split() if len(t) > 1]
def score(qn, qc, en, ec):
    qt = sig(qn); hay = norm(en + " " + (ec or ""))
    if not qt: return 0.0
    frac = sum(1 for t in qt if t in hay) / len(qt)
    qs = set(t for t in qt if t not in STOP); es = set(t for t in sig(en) if t not in STOP)
    s = len(qs & es) / max(len(qs), len(es)) if qs and es else 0.0
    return (frac + s) / 2 + (0.12 if qc and ec and norm(qc) in norm(ec) else 0.0)

LVL_RANK = {"UG": 0, "Integrated": 1, "PG": 2, "PG Diploma": 3,
            "Post Diploma": 4, "Diploma": 5, "Doctoral": 6}

# ---- institutions from the frozen workbook ------------------------------
# NIRF-derived rows for institutions whose per-branch split wasn't resolved carry
# this single placeholder "branch" holding the institution's total intake. It is
# not a real programme, so it is dropped from per-branch aggregation — an
# institution left with no real branch rows is not updated via the fuzzy pass.
PSEUDO = "All UG Engineering — institution total"
# ...except these colleges, where the workbook only reports the institution total
# and there is no existing per-branch profile to preserve, so we deliberately
# write that official total as a single clearly-labelled intake row. Maps the
# baseline college name -> the workbook institution name (exact).
AGG_LABEL = "All UG Engineering (institution total)"
AGG_APPLY = {
    "Nirma University": "Nirma University",
    "Dr. Vishwanath Karad MIT World Peace University": "Dr. Vishwanath Karad MIT World Peace University",
    "Dhirubhai Ambani Institute of Information and Communication Technology":
        "Dhirubhai Ambani Institute of Information and Communication Technology",
    "Army Institute of Technology": "Army Institute of Technology",
    "MIT Art, Design and Technology University, Pune": "MIT Art, Design and Technology University, Pune",
}

def pseudo_totals():
    """institution name -> official total UG-engineering intake (the PSEUDO row)."""
    rows = json.load(open(SRCJSON, encoding="utf-8"))
    tot = {}
    for r in rows:
        if (r["branch"] or "").strip() == PSEUDO:
            try:
                tot[r["inst"]] = tot.get(r["inst"], 0) + int(float(r["intake"] or 0))
            except (ValueError, TypeError):
                pass
    return tot

def west_institutions():
    rows = json.load(open(SRCJSON, encoding="utf-8"))
    grp = {}
    for r in rows:
        key = (r["inst"], r["dist"], r["state"])
        g = grp.setdefault(key, {"name": r["inst"], "dist": r["dist"] or "",
                                 "state": r["state"], "nirf": r["nirf"], "agg": {}})
        c = (r["branch"] or r["official"] or "").strip()
        lv = (r["level"] or "UG").strip()
        if not c or c == PSEUDO:
            continue
        try:
            n = int(float(r["intake"] or 0))
        except (ValueError, TypeError):
            n = 0
        g["agg"][(c, lv)] = g["agg"].get((c, lv), 0) + n
    return [g for g in grp.values() if g["agg"]]

def build_fields(agg):
    levels_by_course = {}
    for (c, lv) in agg:
        levels_by_course.setdefault(c, set()).add(lv)
    rows = sorted(agg.items(), key=lambda kv: (LVL_RANK.get(kv[0][1], 9), kv[0][0]))
    programs, batch = [], []
    for (c, lv), n in rows:
        programs.append([c, lv])
        label = f"{c} ({lv})" if len(levels_by_course[c]) > 1 else c
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

insts = west_institutions()
print(f"workbook West institutions: {len(insts)} | baseline colleges: {len(cols)}\n")

def has(v): return bool(v) and (len(v) if isinstance(v, (list, str)) else True)

# Hand-reviewed exclusions: high-scoring but WRONG (namesake / wrong campus).
BLOCK = {
    # dashboard entry is NMIMS Mumbai (MPSTME); the exact-name hit is the Dhule /
    # Shirpur campus. The Mumbai entity is listed under a different name in the
    # workbook, so we don't auto-map it — leave this college's profile unchanged.
    "SVKM's Narsee Monjee Institute of Management Studies",
}
# Hand-reviewed inclusions: correct match whose fuzzy score fell just short.
ALLOW = {
    # Nadiad campus sits in Kheda district, so city!=dist dropped the score.
    "Dharmsinh Desai University - Engineering Department",
}
BLOCK_N = {norm(x) for x in BLOCK}
ALLOW_N = {norm(x) for x in ALLOW}
base_norms = [norm(c["name"]) for _, c in cols]
for label, S in (("BLOCK", BLOCK_N), ("ALLOW", ALLOW_N)):
    for n in S:
        cnt = base_norms.count(n)
        if cnt != 1:
            print(f"!! {label} name resolves to {cnt} baseline colleges: {n}")
            sys.exit(1)

matches, no_match, low = [], [], []
for idx, c in cols:
    city = (c.get("loc") or "").split(",")[0].strip()
    sc, e = max(((score(c["name"], city, x["name"], x["dist"]), x) for x in insts),
                key=lambda t: t[0], default=(0, None))
    nn = norm(c["name"])
    applied = e is not None and nn not in BLOCK_N and (sc >= THRESH or nn in ALLOW_N) and sc >= 0.55
    if not applied:
        if e is None or sc < 0.60:
            no_match.append((c["name"], round(sc, 2), e["name"] if e else ""))
        else:
            low.append((round(sc, 2), c["name"], city, e["name"], e["dist"]))
        continue
    programs, batch = build_fields(e["agg"])
    matches.append((round(sc, 2), idx, c, e, programs, batch))

# aggregate pass: the named colleges whose only workbook data is the institution
# total. Applied explicitly (not fuzzy) since we have the exact name mapping.
AGG_N = {norm(k) for k in AGG_APPLY}
for n in AGG_N:
    if base_norms.count(n) != 1:
        print(f"!! AGG_APPLY name resolves to {base_norms.count(n)} baseline colleges: {n}")
        sys.exit(1)
totals = pseudo_totals()
already = {norm(c["name"]) for _, _, c, _, _, _ in matches}
for idx, c in cols:
    nn = norm(c["name"])
    if nn not in AGG_N or nn in already:
        continue
    inst_name = AGG_APPLY[next(k for k in AGG_APPLY if norm(k) == nn)]
    seats = totals.get(inst_name)
    if not seats:
        print(f"!! AGG_APPLY: no institution total for {inst_name!r}")
        sys.exit(1)
    programs = [[AGG_LABEL, "UG"]]
    batch = [[AGG_LABEL, seats]]
    e = {"name": inst_name, "dist": "(institution total)", "nirf": "", "agg": {0: seats}}
    matches.append((1.00, idx, c, e, programs, batch))

# collision safety net: two colleges resolving to one institution -> keep best
by_inst = {}
for rec in matches:
    by_inst.setdefault((rec[3]["name"], rec[3]["dist"]), []).append(rec)
keep = []
for en, lst in by_inst.items():
    lst.sort(key=lambda r: -r[0])
    keep.append(lst[0])
    for r in lst[1:]:
        print(f"!! COLLISION dropped: {r[2]['name']} (also -> {en[0]} / {en[1]})")
matches = sorted(keep, key=lambda x: -x[0])

print(f"=== WOULD UPDATE: {len(matches)} colleges ===")
for sc, idx, c, e, programs, batch in matches:
    tot = sum(n for _, n in batch)
    had = "refresh" if (has(c.get("programs")) or has(c.get("batch"))) else "new"
    tag = " [ALLOW]" if norm(c["name"]) in ALLOW_N else ""
    print(f"[{sc:.2f}]{tag} ({had}) {c['name']}  ({c.get('loc')})")
    print(f"        -> {e['name']} / {e['dist']} [{e['nirf'] or '-'}] · {len(programs)} courses · {tot} seats")

print(f"\n=== NOT applied — borderline ({len(low)}) ===")
for sc, cn, city, en, dist in sorted(low, reverse=True):
    print(f"[{sc:.2f}] {cn} ({city})  ?->  {en} / {dist}")

print(f"\n=== institutions in workbook NOT matched to any baseline college ===")
taken = {(e["name"], e["dist"]) for _, _, _, e, _, _ in matches}
for x in insts:
    if (x["name"], x["dist"]) not in taken:
        print(f"  {x['state'][:3]}/{x['dist'][:16]:16} {x['name'][:56]} ({sum(x['agg'].values())} seats)")

if "--apply" in sys.argv:
    src_note = f"NIRF/AICTE verified intake {YEAR}"
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
