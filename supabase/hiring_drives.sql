-- Batch hiring tracker storage for the West Zone dashboard.
-- Run in the Supabase SQL editor after supabase/auth_and_approvals.sql
-- (it reuses the profiles table + is_admin() helper). Safe to re-run.
--
-- One row = one college x Business Unit hiring drive for a graduating batch,
-- carrying the full funnel. Access:
--   admin - read + write everything
--   spoc  - read everything; write only rows for colleges they own
--           (row.spoc = their profiles.scope)
--   tpo   - no access (the tab is hidden for them client-side too)

create table if not exists public.hiring_drives_west (
  id text primary key,                 -- client-generated id
  batch int not null,                  -- graduating year, e.g. 2027
  college text not null,
  bu text not null,                    -- Business Unit
  role text,
  ctc numeric,                         -- offered CTC in LPA
  opened date,
  deadline date,
  apps int not null default 0,         -- applications received
  l1 int not null default 0,           -- L1 assessment shortlisted
  l2 int not null default 0,           -- L2 assessment shortlisted
  sel int not null default 0,          -- interview selects
  rej int not null default 0,          -- interview rejects
  acc int not null default 0,          -- offers accepted
  joined int not null default 0,       -- joined
  spoc text,                           -- owning SPOC (from the college); ties a SPOC's writes
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- role + scope of the current user, read without re-triggering RLS on profiles
create or replace function public.hiring_role() returns text
  language sql stable security definer set search_path = public as $$
  select role from public.profiles where id = auth.uid();
$$;
create or replace function public.hiring_scope() returns text
  language sql stable security definer set search_path = public as $$
  select scope from public.profiles where id = auth.uid();
$$;

alter table public.hiring_drives_west enable row level security;
drop policy if exists "hiring read"   on public.hiring_drives_west;
drop policy if exists "hiring insert" on public.hiring_drives_west;
drop policy if exists "hiring update" on public.hiring_drives_west;
drop policy if exists "hiring delete" on public.hiring_drives_west;

-- read: admin + spoc only (TPOs get nothing)
create policy "hiring read" on public.hiring_drives_west
  for select to authenticated
  using (public.hiring_role() in ('admin', 'spoc'));

-- write: admin anything; spoc only rows tagged with their own SPOC scope
create policy "hiring insert" on public.hiring_drives_west
  for insert to authenticated
  with check (public.hiring_role() = 'admin'
    or (public.hiring_role() = 'spoc' and spoc = public.hiring_scope()));
create policy "hiring update" on public.hiring_drives_west
  for update to authenticated
  using (public.hiring_role() = 'admin'
    or (public.hiring_role() = 'spoc' and spoc = public.hiring_scope()))
  with check (public.hiring_role() = 'admin'
    or (public.hiring_role() = 'spoc' and spoc = public.hiring_scope()));
create policy "hiring delete" on public.hiring_drives_west
  for delete to authenticated
  using (public.hiring_role() = 'admin'
    or (public.hiring_role() = 'spoc' and spoc = public.hiring_scope()));

-- keep updated_at fresh on edits
create or replace function public.touch_hiring_updated_at() returns trigger
  language plpgsql as $$ begin new.updated_at = now(); return new; end; $$;
drop trigger if exists hiring_touch on public.hiring_drives_west;
create trigger hiring_touch before update on public.hiring_drives_west
  for each row execute function public.touch_hiring_updated_at();
