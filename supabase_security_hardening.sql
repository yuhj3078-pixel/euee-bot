-- ============================================================================
-- SUPABASE SECURITY HARDENING
-- Run this AFTER supabase_schema.sql (and fix_payment_schema.sql if needed).
-- ============================================================================

DO $$
BEGIN
    -- Remove legacy permissive policies if they were created by an older schema version.
    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'users') THEN
        EXECUTE 'DROP POLICY IF EXISTS "Service role full access" ON public.users';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'payment_attempts') THEN
        EXECUTE 'DROP POLICY IF EXISTS "Service role full access" ON public.payment_attempts';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'exam_results') THEN
        EXECUTE 'DROP POLICY IF EXISTS "Service role full access" ON public.exam_results';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'confessions') THEN
        EXECUTE 'DROP POLICY IF EXISTS "Service role full access" ON public.confessions';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'battles') THEN
        EXECUTE 'DROP POLICY IF EXISTS "Service role full access" ON public.battles';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'wrong_questions') THEN
        EXECUTE 'DROP POLICY IF EXISTS "Service role full access" ON public.wrong_questions';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'feature_suggestions') THEN
        EXECUTE 'DROP POLICY IF EXISTS "Service role full access" ON public.feature_suggestions';
    END IF;

    -- Sensitive / private tables
    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'users') THEN
        EXECUTE 'ALTER TABLE public.users ENABLE ROW LEVEL SECURITY';
        EXECUTE 'ALTER TABLE public.users FORCE ROW LEVEL SECURITY';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'payment_attempts') THEN
        EXECUTE 'ALTER TABLE public.payment_attempts ENABLE ROW LEVEL SECURITY';
        EXECUTE 'ALTER TABLE public.payment_attempts FORCE ROW LEVEL SECURITY';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'exam_results') THEN
        EXECUTE 'ALTER TABLE public.exam_results ENABLE ROW LEVEL SECURITY';
        EXECUTE 'ALTER TABLE public.exam_results FORCE ROW LEVEL SECURITY';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'confessions') THEN
        EXECUTE 'ALTER TABLE public.confessions ENABLE ROW LEVEL SECURITY';
        EXECUTE 'ALTER TABLE public.confessions FORCE ROW LEVEL SECURITY';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'battles') THEN
        EXECUTE 'ALTER TABLE public.battles ENABLE ROW LEVEL SECURITY';
        EXECUTE 'ALTER TABLE public.battles FORCE ROW LEVEL SECURITY';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'boss_fights') THEN
        EXECUTE 'ALTER TABLE public.boss_fights ENABLE ROW LEVEL SECURITY';
        EXECUTE 'ALTER TABLE public.boss_fights FORCE ROW LEVEL SECURITY';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'wrong_questions') THEN
        EXECUTE 'ALTER TABLE public.wrong_questions ENABLE ROW LEVEL SECURITY';
        EXECUTE 'ALTER TABLE public.wrong_questions FORCE ROW LEVEL SECURITY';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'tier_change_log') THEN
        EXECUTE 'ALTER TABLE public.tier_change_log ENABLE ROW LEVEL SECURITY';
        EXECUTE 'ALTER TABLE public.tier_change_log FORCE ROW LEVEL SECURITY';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'parent_reports') THEN
        EXECUTE 'ALTER TABLE public.parent_reports ENABLE ROW LEVEL SECURITY';
        EXECUTE 'ALTER TABLE public.parent_reports FORCE ROW LEVEL SECURITY';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'feature_suggestions') THEN
        EXECUTE 'ALTER TABLE public.feature_suggestions ENABLE ROW LEVEL SECURITY';
        EXECUTE 'ALTER TABLE public.feature_suggestions FORCE ROW LEVEL SECURITY';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'content_cache') THEN
        EXECUTE 'ALTER TABLE public.content_cache ENABLE ROW LEVEL SECURITY';
        EXECUTE 'ALTER TABLE public.content_cache FORCE ROW LEVEL SECURITY';
    END IF;

    -- Content tables can still be protected by default-deny RLS.
    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'daily_tips') THEN
        EXECUTE 'ALTER TABLE public.daily_tips ENABLE ROW LEVEL SECURITY';
        EXECUTE 'ALTER TABLE public.daily_tips FORCE ROW LEVEL SECURITY';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'textbook_chunks') THEN
        EXECUTE 'ALTER TABLE public.textbook_chunks ENABLE ROW LEVEL SECURITY';
        EXECUTE 'ALTER TABLE public.textbook_chunks FORCE ROW LEVEL SECURITY';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'real_exam_questions') THEN
        EXECUTE 'ALTER TABLE public.real_exam_questions ENABLE ROW LEVEL SECURITY';
        EXECUTE 'ALTER TABLE public.real_exam_questions FORCE ROW LEVEL SECURITY';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'panic_kit') THEN
        EXECUTE 'ALTER TABLE public.panic_kit ENABLE ROW LEVEL SECURITY';
        EXECUTE 'ALTER TABLE public.panic_kit FORCE ROW LEVEL SECURITY';
    END IF;
END $$;

-- Default-deny remains in effect because no anon/authenticated policies are added here.
-- The backend should use SUPABASE_SERVICE_ROLE_KEY, which bypasses RLS safely on the server side.

DO $$
BEGIN
    RAISE NOTICE 'Row Level Security has been enabled on the existing EUEE bot tables.';
    RAISE NOTICE 'Anon/public access remains blocked unless you add explicit policies later.';
END $$;
