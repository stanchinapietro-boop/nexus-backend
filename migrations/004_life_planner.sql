-- Richiede le migrazioni Core 001–003. Solo estensioni additive al catalogo NEXUS.

SET LOCAL search_path TO public;

CREATE TABLE IF NOT EXISTS life_goals (
	id SERIAL NOT NULL, 
	title VARCHAR(180) NOT NULL, 
	description TEXT NOT NULL, 
	category VARCHAR(30) NOT NULL, 
	goal_type VARCHAR(16) NOT NULL, 
	target_value FLOAT, 
	current_value FLOAT NOT NULL, 
	unit VARCHAR(30) NOT NULL, 
	due_date DATE, 
	motivation TEXT NOT NULL, 
	active BOOLEAN NOT NULL, 
	PRIMARY KEY (id)
);

DO $$ BEGIN PERFORM id, title, description, category, goal_type, target_value, current_value, unit, due_date, motivation, active FROM public.life_goals LIMIT 0; END $$;

ALTER TABLE public.life_goals ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS life_habits (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	description TEXT NOT NULL, 
	category VARCHAR(30) NOT NULL, 
	kind VARCHAR(12) NOT NULL, 
	days VARCHAR(20) NOT NULL, 
	target_value FLOAT NOT NULL, 
	unit VARCHAR(30) NOT NULL, 
	start_date DATE NOT NULL, 
	active BOOLEAN NOT NULL, 
	PRIMARY KEY (id)
);

DO $$ BEGIN PERFORM id, name, description, category, kind, days, target_value, unit, start_date, active FROM public.life_habits LIMIT 0; END $$;

ALTER TABLE public.life_habits ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS life_routines (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	kind VARCHAR(30) NOT NULL, 
	days VARCHAR(20) NOT NULL, 
	active BOOLEAN NOT NULL, 
	PRIMARY KEY (id)
);

DO $$ BEGIN PERFORM id, name, kind, days, active FROM public.life_routines LIMIT 0; END $$;

ALTER TABLE public.life_routines ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS life_workouts (
	id SERIAL NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	sport VARCHAR(40) NOT NULL, 
	day DATE NOT NULL, 
	duration_minutes INTEGER NOT NULL, 
	place VARCHAR(180) NOT NULL, 
	description TEXT NOT NULL, 
	intensity INTEGER, 
	notes TEXT NOT NULL, 
	completed BOOLEAN NOT NULL, 
	PRIMARY KEY (id)
);

DO $$ BEGIN PERFORM id, name, sport, day, duration_minutes, place, description, intensity, notes, completed FROM public.life_workouts LIMIT 0; END $$;

ALTER TABLE public.life_workouts ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS planner_areas (
	id SERIAL NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	description VARCHAR(300) NOT NULL, 
	color VARCHAR(7) NOT NULL, 
	icon VARCHAR(24) NOT NULL, 
	importance INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);

DO $$ BEGIN PERFORM id, name, description, color, icon, importance FROM public.planner_areas LIMIT 0; END $$;

ALTER TABLE public.planner_areas ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS planner_days (
	day DATE NOT NULL, 
	priorities JSON NOT NULL, 
	start_min INTEGER, 
	end_min INTEGER, 
	version INTEGER NOT NULL, 
	PRIMARY KEY (day)
);

DO $$ BEGIN PERFORM day, priorities, start_min, end_min, version FROM public.planner_days LIMIT 0; END $$;

ALTER TABLE public.planner_days ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS planner_event_links (
	event_id INTEGER NOT NULL, 
	source_key VARCHAR(200), 
	project_id INTEGER, 
	color VARCHAR(7) NOT NULL, 
	PRIMARY KEY (event_id), 
	FOREIGN KEY(event_id) REFERENCES life_events (id) ON DELETE CASCADE, 
	FOREIGN KEY(project_id) REFERENCES core_projects (id) ON DELETE SET NULL
);

DO $$ BEGIN PERFORM event_id, source_key, project_id, color FROM public.planner_event_links LIMIT 0; END $$;

ALTER TABLE public.planner_event_links ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS planner_focus_sessions (
	id SERIAL NOT NULL, 
	source_key VARCHAR(200) NOT NULL, 
	target_minutes INTEGER NOT NULL, 
	started TIMESTAMP WITH TIME ZONE NOT NULL, 
	resumed TIMESTAMP WITH TIME ZONE, 
	ended TIMESTAMP WITH TIME ZONE, 
	elapsed INTEGER NOT NULL, 
	status VARCHAR(12) NOT NULL, 
	active_slot INTEGER, 
	notes VARCHAR(500) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (active_slot)
);

CREATE INDEX IF NOT EXISTS ix_planner_focus_sessions_started ON planner_focus_sessions (started);

DO $$ BEGIN PERFORM id, source_key, target_minutes, started, resumed, ended, elapsed, status, active_slot, notes FROM public.planner_focus_sessions LIMIT 0; END $$;

ALTER TABLE public.planner_focus_sessions ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS planner_weeks (
	monday DATE NOT NULL, 
	objectives JSON NOT NULL, 
	achievements TEXT NOT NULL, 
	obstacles TEXT NOT NULL, 
	next_week TEXT NOT NULL, 
	version INTEGER NOT NULL, 
	PRIMARY KEY (monday)
);

DO $$ BEGIN PERFORM monday, objectives, achievements, obstacles, next_week, version FROM public.planner_weeks LIMIT 0; END $$;

ALTER TABLE public.planner_weeks ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS life_goal_milestones (
	id SERIAL NOT NULL, 
	goal_id INTEGER NOT NULL, 
	title VARCHAR(180) NOT NULL, 
	due_date DATE, 
	completed BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(goal_id) REFERENCES life_goals (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_life_goal_milestones_goal_id ON life_goal_milestones (goal_id);

DO $$ BEGIN PERFORM id, goal_id, title, due_date, completed FROM public.life_goal_milestones LIMIT 0; END $$;

ALTER TABLE public.life_goal_milestones ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS life_habit_logs (
	id SERIAL NOT NULL, 
	habit_id INTEGER NOT NULL, 
	day DATE NOT NULL, 
	value FLOAT NOT NULL, 
	completed BOOLEAN NOT NULL, 
	note VARCHAR(300) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_life_habit_day UNIQUE (habit_id, day), 
	FOREIGN KEY(habit_id) REFERENCES life_habits (id)
);

DO $$ BEGIN PERFORM id, habit_id, day, value, completed, note FROM public.life_habit_logs LIMIT 0; END $$;

ALTER TABLE public.life_habit_logs ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS life_routine_logs (
	id SERIAL NOT NULL, 
	routine_id INTEGER NOT NULL, 
	day DATE NOT NULL, 
	completed_steps VARCHAR(2000) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_life_routine_day UNIQUE (routine_id, day), 
	FOREIGN KEY(routine_id) REFERENCES life_routines (id)
);

DO $$ BEGIN PERFORM id, routine_id, day, completed_steps FROM public.life_routine_logs LIMIT 0; END $$;

ALTER TABLE public.life_routine_logs ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS life_routine_steps (
	id SERIAL NOT NULL, 
	routine_id INTEGER NOT NULL, 
	title VARCHAR(140) NOT NULL, 
	position INTEGER NOT NULL, 
	duration_minutes INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(routine_id) REFERENCES life_routines (id)
);

DO $$ BEGIN PERFORM id, routine_id, title, position, duration_minutes FROM public.life_routine_steps LIMIT 0; END $$;

ALTER TABLE public.life_routine_steps ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS life_workout_exercises (
	id SERIAL NOT NULL, 
	workout_id INTEGER NOT NULL, 
	name VARCHAR(140) NOT NULL, 
	muscle_group VARCHAR(60) NOT NULL, 
	sets JSON NOT NULL, 
	notes TEXT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workout_id) REFERENCES life_workouts (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_life_workout_exercises_workout_id ON life_workout_exercises (workout_id);

DO $$ BEGIN PERFORM id, workout_id, name, muscle_group, sets, notes FROM public.life_workout_exercises LIMIT 0; END $$;

ALTER TABLE public.life_workout_exercises ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS planner_placements (
	key VARCHAR(200) NOT NULL, 
	scheduled DATE, 
	minutes INTEGER, 
	goal_id INTEGER, 
	project_id INTEGER, 
	energy VARCHAR(10), 
	context VARCHAR(100) NOT NULL, 
	dependencies JSON NOT NULL, 
	quadrant INTEGER, 
	area_id INTEGER, 
	version INTEGER NOT NULL, 
	PRIMARY KEY (key), 
	FOREIGN KEY(goal_id) REFERENCES life_goals (id) ON DELETE SET NULL, 
	FOREIGN KEY(project_id) REFERENCES core_projects (id) ON DELETE SET NULL, 
	FOREIGN KEY(area_id) REFERENCES planner_areas (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_planner_placements_project_id ON planner_placements (project_id);

CREATE INDEX IF NOT EXISTS ix_planner_placements_scheduled ON planner_placements (scheduled);

CREATE INDEX IF NOT EXISTS ix_planner_placements_goal_id ON planner_placements (goal_id);

CREATE INDEX IF NOT EXISTS ix_planner_placements_area_id ON planner_placements (area_id);

DO $$ BEGIN PERFORM key, scheduled, minutes, goal_id, project_id, energy, context, dependencies, quadrant, area_id, version FROM public.planner_placements LIMIT 0; END $$;

ALTER TABLE public.planner_placements ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE t text; r text; seq text;
BEGIN
 FOREACH t IN ARRAY ARRAY['life_goals', 'life_habits', 'life_routines', 'life_workouts', 'planner_areas', 'planner_days', 'planner_event_links', 'planner_focus_sessions', 'planner_weeks', 'life_goal_milestones', 'life_habit_logs', 'life_routine_logs', 'life_routine_steps', 'life_workout_exercises', 'planner_placements'] LOOP
  EXECUTE format('REVOKE ALL ON TABLE public.%I FROM PUBLIC',t);
  seq := CASE WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=t AND column_name='id') THEN pg_get_serial_sequence(format('public.%I',t),'id') END;
  IF seq IS NOT NULL THEN EXECUTE format('REVOKE ALL ON SEQUENCE %s FROM PUBLIC',seq); END IF;
  FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN ('anon','authenticated') LOOP
   EXECUTE format('REVOKE ALL ON TABLE public.%I FROM %I',t,r);
   IF seq IS NOT NULL THEN EXECUTE format('REVOKE ALL ON SEQUENCE %s FROM %I',seq,r); END IF;
  END LOOP;
 END LOOP;
END $$;

INSERT INTO planner_areas (name,description,color,icon,importance) VALUES ('Scuola','','#38bdf8','',3),('Lavoro','','#38bdf8','',3),('Salute','','#38bdf8','',3),('Sport','','#38bdf8','',3),('Finanze','','#38bdf8','',3),('Progetti','','#38bdf8','',3),('Relazioni','','#38bdf8','',3),('Vita sociale','','#38bdf8','',3),('Crescita personale','','#38bdf8','',3),('Hobby','','#38bdf8','',3),('Riposo','','#38bdf8','',3) ON CONFLICT(name) DO NOTHING;
