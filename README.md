# west

West Zone campus engine — the West-zone edition of the college priority
dashboard (see the `engine` repo for the all-India original).

## West Zone College Priority Dashboard

`index.html` is a self-contained dashboard for the early-careers hiring team,
scoped to West-zone campuses (Maharashtra, Gujarat, Goa). It uses the same
scoring framework as the all-India engine — salary, NIRF, NAAC, NBA, brand
perception and CG priority indices with adjusted weights and optional
engagement/diversity bonuses — with all data and logic embedded in the file:
no backend or external calls.

### Baseline data (148 colleges)

- **17 fully-scored colleges** carried over from the all-India engine's
  baseline (every West-zone college it had), with salaries, NAAC, NBA,
  engagement and CG priority intact.
- **131 further West-zone colleges** from the team's West-zone worksheet,
  each with its **TPO name, email and contact number**. Their NIRF 2023–25
  ranks were matched from the embedded official nirfindia.org directory
  (fuzzy name+city match, hand-reviewed — near-miss namesakes like
  VIIT-vs-VIT Pune, the two Cummins campuses, PES Modern vs COEP, the
  Bharati Vidyapeeth campuses and PCCOE&R vs PCCOE were kept separate).
  Salary, NAAC, NBA, engagement and CG fields are blank until the team
  fills them in via Edit — those colleges score on NIRF and brand
  perception alone in the meantime.

### What's different from the all-India engine

- **State chips instead of zone chips** — every college here is West zone,
  so the slicer, the "Avg score by state" chart and the catalogue grouping
  work on Maharashtra / Gujarat / Goa instead.
- **TPO & SPOC contact fields** on every college: TPO (name, email, phone)
  for the college side and SPOC (name, email, phone) for our team's owner
  of the relationship. They appear as a table column, in the row breakdown's
  Contacts card, on catalogue cards, in the Add/Edit form, and are
  searchable — and they never affect the score.
- **West-zone guard** — the Add College form's live location preview flags
  a location that resolves outside the West zone.
- Separate localStorage keys and a separate Supabase table
  (`shared_colleges_west`), so this dashboard never collides with the
  all-India one in the same browser or Supabase project.

Everything else — the three-step workflow (Add College → Dashboard →
Catalogue), cross-filtering visuals, tier cutoffs, matrices, NIRF
directory auto-fill and the print layout — matches the all-India engine;
see that repo's README for the full feature guide.

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
