SET LOCAL lock_timeout = '2s';
CREATE TABLE public.volley_skill_samples (
    id uuid PRIMARY KEY,
    workout_id integer NOT NULL REFERENCES public.life_workouts(id) ON DELETE CASCADE,
    skill varchar(12) NOT NULL CHECK (skill IN ('serve', 'receive', 'attack', 'block')),
    attempts integer NOT NULL CHECK (attempts BETWEEN 1 AND 10000),
    successful integer NOT NULL CHECK (successful BETWEEN 0 AND attempts)
);
CREATE INDEX volley_skill_samples_workout_idx ON public.volley_skill_samples(workout_id, skill);
ALTER TABLE public.volley_skill_samples ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.volley_skill_samples FROM PUBLIC;
DO $$
DECLARE client_role text;
BEGIN
    FOR client_role IN SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated', 'service_role') LOOP
        EXECUTE format('REVOKE ALL ON public.volley_skill_samples FROM %I', client_role);
    END LOOP;
END $$;
