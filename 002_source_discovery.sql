-- Community Finder: automated source discovery metadata.
-- Run after the existing bootstrap/RLS migration.

alter table public.source_registry
  add column if not exists discovery_status text not null default 'manual',
  add column if not exists discovery_score integer,
  add column if not exists discovery_checks jsonb not null default '{}'::jsonb,
  add column if not exists discovered_at timestamptz,
  add column if not exists last_verified_at timestamptz,
  add column if not exists verification_notes text,
  add column if not exists discovery_query text,
  add column if not exists automation_mode text not null default 'manual';

create table if not exists public.source_candidates (
  id uuid primary key default gen_random_uuid(),
  source_key text not null unique,
  name text not null,
  url text not null,
  landing_url text,
  publisher text,
  city_key text,
  discovery_provider text,
  discovery_query text,
  score integer,
  decision text not null default 'needs_review',
  checks jsonb not null default '{}'::jsonb,
  reasons jsonb not null default '[]'::jsonb,
  discovered_at timestamptz not null default now(),
  last_checked_at timestamptz,
  reviewed_at timestamptz,
  reviewed_by uuid references auth.users(id),
  unique(url)
);

alter table public.source_candidates enable row level security;

-- Candidates are operational/admin data. Do not expose them publicly.
-- Service-role jobs bypass RLS. Admin policies can be added when the admin UI
-- is connected to authenticated user_roles.

drop policy if exists "source candidates no public access" on public.source_candidates;

create index if not exists source_candidates_decision_idx
  on public.source_candidates(decision);
create index if not exists source_registry_discovery_status_idx
  on public.source_registry(discovery_status, enabled);
