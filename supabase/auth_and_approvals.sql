-- Role-based access + change-approval workflow for the West Zone dashboard.
-- Run in the Supabase SQL editor after supabase/shared_colleges.sql.
--
-- The dashboard ships a client-side login/roles/approval layer that works with
-- localStorage out of the box (a UI gate, NOT real security). To make it real
-- and team-wide, wire Supabase Auth + the tables/policies below, then fill in
-- the SHARED config in index.html. Three roles:
--   admin - full rights; approves/rejects change requests
--   spoc  - may edit only colleges they own (colleges.spoc = their name)
--   tpo   - may edit only their own college (by name)
-- SPOC/TPO edits become rows in shared_pending_west; an admin approves them,
-- which writes the change into shared_colleges_west (kind = 'edited'/'added').

-- 1) Per-user role + scope. Link each auth user to a role.
create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  role text not null default 'tpo' check (role in ('admin', 'spoc', 'tpo')),
  -- scope: the SPOC name (for spoc) or the exact college name (for tpo)
  scope text,
  name text,
  created_at timestamptz not null default now()
);
alter table public.profiles enable row level security;
create policy "read own profile" on public.profiles for select using (auth.uid() = id);
create policy "admins read all profiles" on public.profiles for select
  using (exists (select 1 from public.profiles p where p.id = auth.uid() and p.role = 'admin'));

-- helper: is the current user an admin?
create or replace function public.is_admin() returns boolean language sql stable as $$
  select exists (select 1 from public.profiles p where p.id = auth.uid() and p.role = 'admin');
$$;

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

-- submitters (spoc/tpo/admin) may create requests
create policy "insert own request" on public.shared_pending_west
  for insert with check (auth.uid() = submitted_by);
-- everyone signed in sees their own requests; admins see all
create policy "read own or admin" on public.shared_pending_west
  for select using (submitted_by = auth.uid() or public.is_admin());
-- only admins may change status (approve/reject)
create policy "admin updates status" on public.shared_pending_west
  for update using (public.is_admin()) with check (public.is_admin());

-- 3) Lock down the college table so only admins write the applied changes.
--    (Approved requests are applied by the admin who clicks Approve.)
--    Replace any permissive write policy from shared_colleges.sql with these:
alter table public.shared_colleges_west enable row level security;
drop policy if exists "anon can write" on public.shared_colleges_west;
create policy "anyone signed in can read" on public.shared_colleges_west
  for select using (auth.role() = 'authenticated');
create policy "admins can write" on public.shared_colleges_west
  for all using (public.is_admin()) with check (public.is_admin());

-- Seed an admin after creating the user in Auth:
--   insert into public.profiles (id, role, name)
--   values ('<auth-user-uuid>', 'admin', 'Administrator');
