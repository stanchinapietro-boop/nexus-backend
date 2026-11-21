CREATE TABLE IF NOT EXISTS public.integration_tokens (provider varchar(30) PRIMARY KEY, access_token varchar(2000) NOT NULL);
CREATE TABLE IF NOT EXISTS public.ticktick_sync_snapshot (connection varchar(64) PRIMARY KEY, revision bigint NOT NULL, payload json NOT NULL);
ALTER TABLE public.integration_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ticktick_sync_snapshot ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.ticktick_sync_snapshot, public.integration_tokens FROM PUBLIC;
DO $$ DECLARE r text; BEGIN
FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN ('anon','authenticated') LOOP
 EXECUTE format('REVOKE ALL ON public.integration_tokens, public.ticktick_sync_snapshot FROM %I',r);
END LOOP;
END $$;
