# west

West Zone campus engine — the West-zone edition of the college priority
dashboard (see the `engine` repo for the all-India original).

## West Zone College Priority Dashboard

`index.html` is a self-contained dashboard for the early-careers hiring team,
scoped to West-zone campuses (Maharashtra, Gujarat, Goa). It uses the same
scoring framework as the all-India engine minus the CG priority tag —
salary (28.6%), NIRF (19%), NAAC (19%), NBA (19%) and brand perception
(14.3%) indices with optional engagement/diversity bonuses — with all data
and logic embedded in the file: no backend or external calls. Brand
perception uses **NIRF's official Perception (PR) survey score** (employer
+ academic peers; published for ranks 1–100, captured by the directory
workflow and rescaled onto the dashboard's 0–100 scale) where available —
currently COEP, PDEU, DIAT and Symbiosis — and an indicative model
estimate (NIRF standing + salary + vintage) for everyone else; each
college's breakdown states which one it is.

### Baseline data (163 colleges)

- **17 fully-scored colleges** carried over from the all-India engine's
  baseline (every West-zone college it had), with salaries, NAAC, NBA and
  engagement intact.
- **146 further West-zone colleges** from the team's worksheets, each
  with its **TPO name, email and contact number**. NIRF 2023–25 ranks
  were matched from the embedded official nirfindia.org directory (fuzzy
  name+city match, hand-reviewed — near-miss namesakes like VIIT-vs-VIT
  Pune, the two Cummins campuses, the DY Patil / Raisoni / Parul /
  Walchand entities and PCCOE&R vs PCCOE were kept separate). Salary,
  NAAC, NBA and engagement fields are blank until the team fills them in
  via Edit — those colleges score on NIRF and brand perception alone in
  the meantime.
- **84 colleges reconciled from the West Zone SPOC workbook**: each
  carries its team **SPOC** (Arthi / Nishil / Asmita / Ritika, from the
  "Updated NEW SPOC" column), refreshed TPO contacts, a diversity flag for
  Diversity / Div-Only types, and the reference-only programme fields —
  college group, HML, MOU status & type, WZ priority (Priority-1..4),
  phase and mode — shown in the row breakdown and as catalogue tags.

### What's different from the all-India engine

- **State chips instead of zone chips** — every college here is West zone,
  so the slicer, the "Avg score by state" chart and the catalogue grouping
  work on Maharashtra / Gujarat / Goa instead.
- **SPOC-driven, state-driven pages** — instead of the all-India engine's
  priority tiers, the dashboard carries a clickable **SPOC portfolios band**
  (count, avg score, Priority-1s per owner — click to focus the page) and a
  **Colleges by SPOC** donut, and the catalogue groups colleges **by SPOC,
  then by state**, with per-SPOC and per-state summary tiles. Colleges
  without an owner sit in an "Unassigned — needs a SPOC" section (also a
  filter option). The tier cutoffs, opportunity/value matrices and the CG
  priority tag (filter, column, scoring component) from the all-India
  engine were removed — the worksheet's Priority-1..4 remains as a
  reference field.
- **TPO & SPOC fields** on every college: TPO (name, email, phone) for
  the college side and the SPOC name for our team's owner of the
  relationship. They appear as table columns, in the row breakdown's
  Contacts card, on catalogue cards, in the Add/Edit form, and are
  searchable — plus the SPOC slicer on the dashboard. Contacts never
  affect the score.
- **Programme fields** (group, HML, MOU status & type, WZ priority, phase,
  mode) imported from the SPOC workbook are reference-only: shown in the
  breakdown's Profile card and as catalogue tags, preserved across form
  edits and synced through Supabase, never scored.
- **West-zone guard** — the Add College form's live location preview flags
  a location that resolves outside the West zone.
- Separate localStorage keys and a separate Supabase table
  (`shared_colleges_west`), so this dashboard never collides with the
  all-India one in the same browser or Supabase project.

Everything else — the three-step workflow (Add College → Dashboard →
Catalogue), cross-filtering visuals, NIRF directory auto-fill and the
print layout — matches the all-India engine; see that repo's README for
the full feature guide.

## Team-shared additions (Supabase)

Out of the box, changes made through the UI stay in each person's browser.
To share them live across the team:

1. Create (or reuse) a [Supabase](https://supabase.com) project.
2. In the SQL editor, run `supabase/shared_colleges.sql` from this repo —
   it creates the `shared_colleges_west` table (including the TPO/SPOC
   contact columns) with row-level security.
3. In `index.html`, fill in the `SHARED` config near the top of the last
   script block with your project URL and public anon key.
4. Commit and push to `main` — the site republishes automatically.

## Updating the NIRF directory

The "Update NIRF directory" workflow (Actions tab) runs
`scripts/build_nirf_directory.py` against nirfindia.org and commits the
refreshed embedded directory — run it whenever NIRF publishes a new year.

Deploy by serving `index.html` anywhere (e.g. GitHub Pages — pushes to
`main` publish via the Pages workflow) or opening it directly in a browser.
