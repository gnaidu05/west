-- Role-based access + change-approval workflow for the West Zone dashboard.
-- Run in the Supabase SQL editor after supabase/shared_colleges.sql.
-- Safe to re-run (idempotent).
--
-- The dashboard ships a client-side login/roles/approval layer that works with
-- localStorage out of the box (a UI gate, NOT real security). To make it real
-- and team-wide, wire Supabase Auth + the tables/policies below, fill in the
-- SHARED config in index.html, and set AUTH.mode = "supabase". Three roles:
--   admin - full rights; approves/rejects change requests
--   spoc  - may edit only colleges they own (colleges.spoc = their name)
--   tpo   - may edit only their own college (by name)
-- SPOC/TPO edits become rows in shared_pending_west; an admin approves them,
-- which writes the change into shared_colleges_west (kind = 'edited'/'added').

-- 1) Per-user role + scope, keyed to the Supabase Auth user id.
create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  role text not null default 'tpo' check (role in ('admin', 'spoc', 'tpo')),
  -- scope: the SPOC name (for spoc) or the exact college name (for tpo)
  scope text,
  name text,
  created_at timestamptz not null default now()
);

-- SECURITY DEFINER so this check runs as the table owner and does NOT re-trigger
-- row-level security on profiles — without this the admin policy below recurses.
create or replace function public.is_admin() returns boolean
  language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.profiles p where p.id = auth.uid() and p.role = 'admin');
$$;

alter table public.profiles enable row level security;
drop policy if exists "read own profile"       on public.profiles;
drop policy if exists "admins read all profiles" on public.profiles;
create policy "read own profile" on public.profiles
  for select using (auth.uid() = id);
create policy "admins read all profiles" on public.profiles
  for select using (public.is_admin());

-- 2) The change-request queue the dashboard reads/writes (PENDING_TABLE).
create table if not exists public.shared_pending_west (
  id text primary key,                       -- client-generated request id
  created_at timestamptz not null default now(),
  ts timestamptz not null default now(),
  name text not null,                        -- target college name
  status text not null default 'pending' check (status in ('pending', 'approved', 'rejected')),
  submitted_by uuid default auth.uid(),
  by text,                                   -- display name of submitter
  payload jsonb not null                     -- full request {payload, diff, ...}
);
alter table public.shared_pending_west enable row level security;
drop policy if exists "insert own request" on public.shared_pending_west;
drop policy if exists "read own or admin"  on public.shared_pending_west;
drop policy if exists "admin updates status" on public.shared_pending_west;
-- submitters (spoc/tpo/admin) may create requests for themselves
create policy "insert own request" on public.shared_pending_west
  for insert to authenticated with check (auth.uid() = submitted_by);
-- everyone signed in sees their own requests; admins see all
create policy "read own or admin" on public.shared_pending_west
  for select to authenticated using (submitted_by = auth.uid() or public.is_admin());
-- only admins may change status (approve/reject)
create policy "admin updates status" on public.shared_pending_west
  for update to authenticated using (public.is_admin()) with check (public.is_admin());

-- 3) Lock down the college table so only admins write the applied changes.
--    (Approved requests are applied by the admin who clicks Approve.)
--    This replaces the open anon policies created by shared_colleges.sql.
alter table public.shared_colleges_west enable row level security;
drop policy if exists "anon read"   on public.shared_colleges_west;
drop policy if exists "anon insert" on public.shared_colleges_west;
drop policy if exists "anon update" on public.shared_colleges_west;
drop policy if exists "anon delete" on public.shared_colleges_west;
drop policy if exists "signed-in can read" on public.shared_colleges_west;
drop policy if exists "admins can write"   on public.shared_colleges_west;
create policy "signed-in can read" on public.shared_colleges_west
  for select to authenticated using (true);
create policy "admins can write" on public.shared_colleges_west
  for all to authenticated using (public.is_admin()) with check (public.is_admin());

-- Seed roles after creating each user in Authentication -> Users
-- (tick "Auto Confirm User"). Copy each user's UID from that screen:
--   insert into public.profiles (id, role, scope, name) values
--     ('<admin-uuid>', 'admin', null,              'Administrator'),
--     ('<arthi-uuid>', 'spoc',  'Arthi',           'Arthi'),
--     ('<tpo-uuid>',   'tpo',   'Symbiosis Institute of Technology', 'Rahul Digge');
