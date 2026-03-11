-- run_events: persistent event log for each run's pipeline timeline.
--
-- Events are published by the Celery worker and replayed by the SSE endpoint.
-- Redis Streams remain the live-delivery layer; this table is the durable store
-- so the event timeline is always available even after Redis TTL expiry.
--
-- stream_id stores the Redis Stream entry ID (e.g. "1710000000000-0") so the
-- SSE endpoint can resume the live Redis stream from the correct cursor after
-- replaying persisted events — avoiding both duplicates and gaps.

create table run_events (
    id          uuid primary key default gen_random_uuid(),
    run_id      uuid not null references runs(id) on delete cascade,
    event_type  text not null,
    phase       text not null default '',
    data        jsonb not null default '{}',
    stream_id   text,
    ts          timestamptz not null default now()
);

comment on table run_events is
    'Persistent pipeline event log for each run. '
    'Sourced from the Celery worker via publish_event(); used for history replay.';

-- Primary query pattern: fetch all events for a run in order
create index idx_run_events_run_id_ts on run_events(run_id, ts);

-- RLS: users can only read events for runs belonging to their own repos.
alter table run_events enable row level security;

create policy run_events_select on run_events
    for select
    using (
        run_id in (
            select r.id
            from   runs r
            join   repositories repo on repo.id = r.repo_id
            join   organizations org  on org.id  = repo.org_id
            where  org.owner_id = auth.uid()
        )
    );
