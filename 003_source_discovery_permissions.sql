-- Optional hardening for the source discovery table.
-- Keep candidates private; service-role CI can insert/update regardless of RLS.

alter table public.source_candidates
  drop constraint if exists source_candidates_score_check;
alter table public.source_candidates
  add constraint source_candidates_score_check
  check (score is null or (score >= 0 and score <= 100));

alter table public.source_candidates
  drop constraint if exists source_candidates_decision_check;
alter table public.source_candidates
  add constraint source_candidates_decision_check
  check (decision in ('auto_approved', 'needs_review', 'rejected'));
