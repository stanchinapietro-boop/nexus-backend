SET LOCAL lock_timeout = '2s';

CREATE TABLE public.nexus_calendar_reminder (
    id integer PRIMARY KEY CHECK (id = 1),
    enabled boolean NOT NULL DEFAULT false,
    lead_minutes integer NOT NULL CHECK (lead_minutes BETWEEN 5 AND 1440),
    category varchar(30) NOT NULL DEFAULT '',
    version integer NOT NULL CHECK (version > 0)
);

CREATE TABLE public.nexus_reminder_runs (
    event_id integer NOT NULL,
    starts_at timestamptz NOT NULL,
    status varchar(10) NOT NULL CHECK (status IN ('sent', 'failed')),
    attempts smallint NOT NULL CHECK (attempts BETWEEN 1 AND 3),
    checked_at timestamptz NOT NULL,
    error_code varchar(5),
    PRIMARY KEY (event_id, starts_at)
);
CREATE INDEX nexus_reminder_runs_recent ON public.nexus_reminder_runs(checked_at DESC);
ALTER TABLE public.nexus_calendar_reminder ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.nexus_reminder_runs ENABLE ROW LEVEL SECURITY;

CREATE FUNCTION public.nexus_dispatch_calendar_reminders() RETURNS integer
LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog AS $$
DECLARE
    rule public.nexus_calendar_reminder%ROWTYPE;
    item record;
    deliveries integer := 0;
    checked timestamptz := statement_timestamp();
BEGIN
    IF NOT pg_try_advisory_xact_lock(16023014, 8) THEN
        RETURN 0;
    END IF;
    SELECT * INTO rule FROM public.nexus_calendar_reminder WHERE id = 1 AND enabled;
    IF NOT FOUND THEN
        RETURN 0;
    END IF;
    FOR item IN
        SELECT e.id, e.title, e.starts_at FROM public.life_events e
        LEFT JOIN public.nexus_reminder_runs r ON r.event_id = e.id AND r.starts_at = e.starts_at
        WHERE e.starts_at >= checked AND e.starts_at <= checked + make_interval(mins => rule.lead_minutes)
          AND (rule.category = '' OR e.category = rule.category)
          AND (r.event_id IS NULL OR (r.status = 'failed' AND r.attempts < 3
               AND r.checked_at <= checked - interval '1 minute' * r.attempts))
        ORDER BY e.starts_at, e.id LIMIT 50
    LOOP
        BEGIN
            INSERT INTO public.core_notifications(category, title, message)
                VALUES ('automation', 'Promemoria calendario', item.title);
            INSERT INTO public.nexus_reminder_runs(event_id, starts_at, status, attempts, checked_at)
                VALUES (item.id, item.starts_at, 'sent', 1, checked)
                ON CONFLICT (event_id, starts_at) DO UPDATE SET status = 'sent',
                    attempts = nexus_reminder_runs.attempts + 1, checked_at = EXCLUDED.checked_at, error_code = NULL;
            deliveries := deliveries + 1;
        EXCEPTION WHEN OTHERS THEN
            -- The failed action rolls back before its SQLSTATE is recorded. Keep private payloads out of the log.
            INSERT INTO public.nexus_reminder_runs(event_id, starts_at, status, attempts, checked_at, error_code)
                VALUES (item.id, item.starts_at, 'failed', 1, checked, SQLSTATE)
                ON CONFLICT (event_id, starts_at) DO UPDATE SET status = 'failed',
                    attempts = nexus_reminder_runs.attempts + 1, checked_at = EXCLUDED.checked_at,
                    error_code = EXCLUDED.error_code;
        END;
    END LOOP;
    RETURN deliveries;
END;
$$;
REVOKE ALL ON FUNCTION public.nexus_dispatch_calendar_reminders() FROM PUBLIC;
REVOKE ALL ON public.nexus_calendar_reminder, public.nexus_reminder_runs FROM PUBLIC;
DO $$
DECLARE client_role text;
BEGIN
    FOR client_role IN SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated', 'service_role') LOOP
        EXECUTE format('REVOKE ALL ON FUNCTION public.nexus_dispatch_calendar_reminders() FROM %I', client_role);
        EXECUTE format('REVOKE ALL ON public.nexus_calendar_reminder, public.nexus_reminder_runs FROM %I', client_role);
    END LOOP;
END $$;
