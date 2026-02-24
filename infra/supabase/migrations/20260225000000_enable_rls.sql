-- =============================================================================
-- Enable Row Level Security on all public tables.
--
-- The FastAPI backend connects as the `postgres` superuser (direct PG
-- connection string) which bypasses RLS by default, so enabling RLS here
-- does NOT break the API.
--
-- With RLS enabled and no policies, the `anon` and `authenticated` Supabase
-- roles cannot read or write any row directly (e.g. via the Supabase JS
-- client). All access must go through the FastAPI backend, which is the
-- intended architecture.
-- =============================================================================

ALTER TABLE public.users                ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organizations        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.github_installations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.repositories         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.baselines            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.runs                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.opportunities        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.attempts             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.proposals            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.artifacts            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.settings             ENABLE ROW LEVEL SECURITY;
