CREATE TABLE public.nexus_sync (
 id integer PRIMARY KEY CHECK (id=1), workspace uuid NOT NULL DEFAULT gen_random_uuid(),
 revision bigint NOT NULL DEFAULT 0, preferences jsonb NOT NULL DEFAULT '{}'::jsonb,
 version bigint NOT NULL DEFAULT 0);
INSERT INTO public.nexus_sync (id) VALUES (1);
CREATE FUNCTION public.nexus_mark_changed() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN UPDATE public.nexus_sync SET revision=revision+1 WHERE id=1; RETURN NULL; END $$;
DO $$ BEGIN IF to_regclass('public.academic_courses') IS NOT NULL THEN
 ALTER TABLE public.academic_courses ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.academic_courses FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.academic_courses FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.academic_courses FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.academic_courses FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.academic_exam_grade_links') IS NOT NULL THEN
 ALTER TABLE public.academic_exam_grade_links ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.academic_exam_grade_links FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.academic_exam_grade_links FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.academic_exam_grade_links FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.academic_exam_grade_links FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.academic_exam_task_links') IS NOT NULL THEN
 ALTER TABLE public.academic_exam_task_links ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.academic_exam_task_links FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.academic_exam_task_links FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.academic_exam_task_links FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.academic_exam_task_links FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.academic_exams') IS NOT NULL THEN
 ALTER TABLE public.academic_exams ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.academic_exams FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.academic_exams FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.academic_exams FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.academic_exams FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.academic_flashcards') IS NOT NULL THEN
 ALTER TABLE public.academic_flashcards ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.academic_flashcards FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.academic_flashcards FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.academic_flashcards FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.academic_flashcards FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.academic_goals') IS NOT NULL THEN
 ALTER TABLE public.academic_goals ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.academic_goals FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.academic_goals FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.academic_goals FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.academic_goals FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.academic_grade_meta') IS NOT NULL THEN
 ALTER TABLE public.academic_grade_meta ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.academic_grade_meta FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.academic_grade_meta FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.academic_grade_meta FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.academic_grade_meta FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.academic_grades') IS NOT NULL THEN
 ALTER TABLE public.academic_grades ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.academic_grades FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.academic_grades FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.academic_grades FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.academic_grades FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.academic_lessons') IS NOT NULL THEN
 ALTER TABLE public.academic_lessons ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.academic_lessons FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.academic_lessons FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.academic_lessons FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.academic_lessons FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.academic_notes') IS NOT NULL THEN
 ALTER TABLE public.academic_notes ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.academic_notes FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.academic_notes FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.academic_notes FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.academic_notes FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.academic_study_sessions') IS NOT NULL THEN
 ALTER TABLE public.academic_study_sessions ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.academic_study_sessions FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.academic_study_sessions FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.academic_study_sessions FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.academic_study_sessions FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.academic_subtasks') IS NOT NULL THEN
 ALTER TABLE public.academic_subtasks ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.academic_subtasks FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.academic_subtasks FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.academic_subtasks FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.academic_subtasks FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.academic_task_meta') IS NOT NULL THEN
 ALTER TABLE public.academic_task_meta ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.academic_task_meta FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.academic_task_meta FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.academic_task_meta FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.academic_task_meta FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.academic_task_recurrences') IS NOT NULL THEN
 ALTER TABLE public.academic_task_recurrences ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.academic_task_recurrences FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.academic_task_recurrences FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.academic_task_recurrences FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.academic_task_recurrences FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.academic_tasks') IS NOT NULL THEN
 ALTER TABLE public.academic_tasks ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.academic_tasks FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.academic_tasks FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.academic_tasks FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.academic_tasks FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.app_auth') IS NOT NULL THEN
 ALTER TABLE public.app_auth ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.app_auth FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.app_auth FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.app_auth FROM authenticated; END IF;
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.core_notifications') IS NOT NULL THEN
 ALTER TABLE public.core_notifications ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.core_notifications FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.core_notifications FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.core_notifications FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.core_notifications FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.core_projects') IS NOT NULL THEN
 ALTER TABLE public.core_projects ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.core_projects FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.core_projects FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.core_projects FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.core_projects FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.fin_accounts') IS NOT NULL THEN
 ALTER TABLE public.fin_accounts ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.fin_accounts FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.fin_accounts FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.fin_accounts FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.fin_accounts FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.fin_budgets') IS NOT NULL THEN
 ALTER TABLE public.fin_budgets ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.fin_budgets FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.fin_budgets FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.fin_budgets FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.fin_budgets FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.fin_categories') IS NOT NULL THEN
 ALTER TABLE public.fin_categories ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.fin_categories FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.fin_categories FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.fin_categories FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.fin_categories FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.fin_goals') IS NOT NULL THEN
 ALTER TABLE public.fin_goals ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.fin_goals FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.fin_goals FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.fin_goals FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.fin_goals FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.fin_recurring') IS NOT NULL THEN
 ALTER TABLE public.fin_recurring ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.fin_recurring FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.fin_recurring FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.fin_recurring FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.fin_recurring FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.fin_transactions') IS NOT NULL THEN
 ALTER TABLE public.fin_transactions ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.fin_transactions FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.fin_transactions FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.fin_transactions FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.fin_transactions FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.inbox_items') IS NOT NULL THEN
 ALTER TABLE public.inbox_items ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.inbox_items FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.inbox_items FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.inbox_items FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.inbox_items FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.integration_tokens') IS NOT NULL THEN
 ALTER TABLE public.integration_tokens ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.integration_tokens FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.integration_tokens FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.integration_tokens FROM authenticated; END IF;
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.life_events') IS NOT NULL THEN
 ALTER TABLE public.life_events ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.life_events FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.life_events FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.life_events FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.life_events FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.life_goal_milestones') IS NOT NULL THEN
 ALTER TABLE public.life_goal_milestones ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.life_goal_milestones FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.life_goal_milestones FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.life_goal_milestones FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.life_goal_milestones FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.life_goals') IS NOT NULL THEN
 ALTER TABLE public.life_goals ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.life_goals FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.life_goals FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.life_goals FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.life_goals FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.life_habit_logs') IS NOT NULL THEN
 ALTER TABLE public.life_habit_logs ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.life_habit_logs FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.life_habit_logs FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.life_habit_logs FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.life_habit_logs FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.life_habits') IS NOT NULL THEN
 ALTER TABLE public.life_habits ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.life_habits FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.life_habits FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.life_habits FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.life_habits FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.life_routine_logs') IS NOT NULL THEN
 ALTER TABLE public.life_routine_logs ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.life_routine_logs FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.life_routine_logs FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.life_routine_logs FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.life_routine_logs FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.life_routine_steps') IS NOT NULL THEN
 ALTER TABLE public.life_routine_steps ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.life_routine_steps FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.life_routine_steps FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.life_routine_steps FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.life_routine_steps FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.life_routines') IS NOT NULL THEN
 ALTER TABLE public.life_routines ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.life_routines FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.life_routines FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.life_routines FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.life_routines FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.life_workout_exercises') IS NOT NULL THEN
 ALTER TABLE public.life_workout_exercises ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.life_workout_exercises FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.life_workout_exercises FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.life_workout_exercises FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.life_workout_exercises FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.life_workouts') IS NOT NULL THEN
 ALTER TABLE public.life_workouts ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.life_workouts FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.life_workouts FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.life_workouts FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.life_workouts FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.notes') IS NOT NULL THEN
 ALTER TABLE public.notes ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.notes FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.notes FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.notes FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.notes FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.planner_areas') IS NOT NULL THEN
 ALTER TABLE public.planner_areas ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.planner_areas FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.planner_areas FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.planner_areas FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.planner_areas FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.planner_days') IS NOT NULL THEN
 ALTER TABLE public.planner_days ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.planner_days FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.planner_days FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.planner_days FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.planner_days FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.planner_event_links') IS NOT NULL THEN
 ALTER TABLE public.planner_event_links ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.planner_event_links FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.planner_event_links FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.planner_event_links FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.planner_event_links FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.planner_focus_sessions') IS NOT NULL THEN
 ALTER TABLE public.planner_focus_sessions ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.planner_focus_sessions FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.planner_focus_sessions FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.planner_focus_sessions FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.planner_focus_sessions FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.planner_placements') IS NOT NULL THEN
 ALTER TABLE public.planner_placements ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.planner_placements FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.planner_placements FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.planner_placements FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.planner_placements FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.planner_weeks') IS NOT NULL THEN
 ALTER TABLE public.planner_weeks ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.planner_weeks FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.planner_weeks FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.planner_weeks FROM authenticated; END IF;
 CREATE TRIGGER nexus_revision AFTER INSERT OR UPDATE OR DELETE ON public.planner_weeks FOR EACH ROW EXECUTE FUNCTION public.nexus_mark_changed();
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.ticktick_sync_snapshot') IS NOT NULL THEN
 ALTER TABLE public.ticktick_sync_snapshot ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.ticktick_sync_snapshot FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.ticktick_sync_snapshot FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.ticktick_sync_snapshot FROM authenticated; END IF;
 END IF; END $$;
DO $$ BEGIN IF to_regclass('public.nexus_sync') IS NOT NULL THEN
 ALTER TABLE public.nexus_sync ENABLE ROW LEVEL SECURITY;
 REVOKE ALL ON public.nexus_sync FROM PUBLIC;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON public.nexus_sync FROM anon; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON public.nexus_sync FROM authenticated; END IF;
 END IF; END $$;
