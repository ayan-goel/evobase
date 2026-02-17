-- Minimal seed data for local development.
-- Uses deterministic UUIDs so tests and dev tooling can reference them.

insert into users (id, email)
values ('00000000-0000-0000-0000-000000000001', 'dev@selfopt.local');

insert into organizations (id, name, owner_id)
values (
    '00000000-0000-0000-0000-000000000010',
    'Dev Organization',
    '00000000-0000-0000-0000-000000000001'
);

insert into repositories (id, org_id, github_repo_id, default_branch, package_manager, install_cmd, build_cmd, test_cmd)
values (
    '00000000-0000-0000-0000-000000000100',
    '00000000-0000-0000-0000-000000000010',
    123456789,
    'main',
    'npm',
    'npm install',
    'npm run build',
    'npm test'
);

insert into settings (repo_id, compute_budget_minutes, max_proposals_per_run, schedule)
values (
    '00000000-0000-0000-0000-000000000100',
    60,
    10,
    '0 2 * * *'
);
