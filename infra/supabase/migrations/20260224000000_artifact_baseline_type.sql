-- Allow 'baseline' as an artifact type alongside existing log/trace/bench/diff.
-- Also make proposal_id nullable so run-level artifacts (not tied to a proposal) can be stored.
alter table artifacts drop constraint if exists artifacts_type_check;
alter table artifacts add constraint artifacts_type_check check (type in ('log', 'trace', 'bench', 'diff', 'baseline'));
alter table artifacts alter column proposal_id drop not null;
