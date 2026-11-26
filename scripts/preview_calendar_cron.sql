-- One-time provisioning for the existing isolated NEXUS Preview. Run as one transaction.
DO $$
BEGIN
    IF (SELECT workspace FROM public.nexus_sync WHERE id=1) IS DISTINCT FROM
       '76ae99a8-04a3-41c3-aa37-6f973b0f9d86'::uuid
       OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='nexus_preview_app' AND NOT rolsuper AND NOT rolbypassrls)
       OR EXISTS (SELECT 1 FROM public.nexus_calendar_reminder WHERE enabled)
       OR EXISTS (SELECT 1 FROM pg_roles WHERE rolname='nexus_calendar_worker') THEN
        RAISE EXCEPTION 'Unexpected Preview target or previous worker installation';
    END IF;
END $$;
CREATE EXTENSION IF NOT EXISTS pg_cron WITH SCHEMA pg_catalog;
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM cron.job WHERE jobname='nexus-preview-calendar-reminders') THEN
        RAISE EXCEPTION 'The Preview calendar job already exists';
    END IF;
END $$;

CREATE ROLE nexus_calendar_worker NOLOGIN NOBYPASSRLS;
GRANT nexus_calendar_worker TO postgres WITH INHERIT FALSE, SET TRUE;
GRANT USAGE ON SCHEMA public TO nexus_calendar_worker;
GRANT SELECT ON public.nexus_calendar_reminder TO nexus_calendar_worker;
GRANT SELECT (id, title, starts_at, category) ON public.life_events TO nexus_calendar_worker;
GRANT SELECT, INSERT, UPDATE ON public.nexus_reminder_runs TO nexus_calendar_worker;
GRANT INSERT (category, title, message) ON public.core_notifications TO nexus_calendar_worker;
GRANT USAGE ON SEQUENCE public.core_notifications_id_seq TO nexus_calendar_worker;
-- Existing notification inserts increment the shared workspace revision through nexus_mark_changed.
GRANT SELECT (id, revision), UPDATE (revision) ON public.nexus_sync TO nexus_calendar_worker;
GRANT EXECUTE ON FUNCTION public.nexus_dispatch_calendar_reminders() TO nexus_calendar_worker;

CREATE POLICY reminder_worker_read_rule ON public.nexus_calendar_reminder FOR SELECT TO nexus_calendar_worker USING (true);
CREATE POLICY reminder_worker_read_events ON public.life_events FOR SELECT TO nexus_calendar_worker USING (true);
CREATE POLICY reminder_worker_audit ON public.nexus_reminder_runs TO nexus_calendar_worker USING (true) WITH CHECK (true);
CREATE POLICY reminder_worker_notify ON public.core_notifications FOR INSERT TO nexus_calendar_worker WITH CHECK (category='automation' AND note_id IS NULL);
CREATE POLICY reminder_worker_read_revision ON public.nexus_sync FOR SELECT TO nexus_calendar_worker USING (id=1);
CREATE POLICY reminder_worker_update_revision ON public.nexus_sync FOR UPDATE TO nexus_calendar_worker USING (id=1) WITH CHECK (id=1);

SELECT cron.schedule('nexus-preview-calendar-reminders', '* * * * *',
    'SET LOCAL ROLE nexus_calendar_worker; SELECT public.nexus_dispatch_calendar_reminders();');
