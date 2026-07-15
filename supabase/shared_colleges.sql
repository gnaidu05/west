-- Team-shared college data for the West Zone College Priority Dashboard.
-- Run once in the Supabase SQL editor (or with `supabase db push`).
--
-- One table holds everything the team changes through the UI:
--   kind = 'added'  -> a new college added by the team
--   kind = 'edited' -> an override of one of the baseline colleges
--                      (matched to the baseline by exact name)
--
-- NIRF and NBA columns are text because the scoring model accepts bands
-- like "101-150" and "-" as well as plain numbers; the dashboard converts
-- numeric strings back to numbers when it loads rows.

create table if not exists public.shared_colleges_west (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  kind text not null default 'added' check (kind in ('added', 'edited')),
  name text not null,
  loc text not null,
  type text,
  year int,
  div text,
  nirf25 text,
  nirf24 text,
  nirf23 text,
  naac text,
  nba text,
  avg numeric,
  med numeric,
  eng text,
  cg text not null default 'NA',
  -- reference-only contact fields (never affect the score)
  tpo text,
  tpoemail text,
  tpophone text,
  spoc text,
  spocemail text,
  spocphone text
);

-- If you created this table from an earlier version of this file (without
-- the kind column), run this instead of the create above:
--   alter table public.shared_colleges_west
--     add column if not exists kind text not null default 'added';

create unique index if not exists shared_colleges_west_name_key
  on public.shared_colleges_west (lower(name));

alter table public.shared_colleges_west enable row level security;

-- The dashboard talks to this table with the project's public anon key, so
-- anyone who can open the page can read and write rows. That matches an
-- internal team tool. If you later add Supabase Auth, change `to anon`
-- below to `to authenticated` and have the page sign users in.
create policy "anon read"   on public.shared_colleges_west for select to anon using (true);
create policy "anon insert" on public.shared_colleges_west for insert to anon with check (true);
create policy "anon update" on public.shared_colleges_west for update to anon using (true);
create policy "anon delete" on public.shared_colleges_west for delete to anon using (true);
