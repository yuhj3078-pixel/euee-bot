-- ============================================================================
-- SQL ADDITIONS FOR ABEBE BOT
-- Run these in Supabase Dashboard → SQL Editor
-- ============================================================================

-- Helper function for updated_at triggers
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 1. NOTES TABLE (Study Notes PDFs)
-- ============================================================================
CREATE TABLE IF NOT EXISTS notes (
    id SERIAL PRIMARY KEY,
    subject VARCHAR(50) NOT NULL,
    title VARCHAR(255),
    content TEXT,
    file_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add unique constraint to prevent duplicates
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'unique_notes_subject'
    ) THEN
        ALTER TABLE notes ADD CONSTRAINT unique_notes_subject
        UNIQUE (subject) DEFERRABLE INITIALLY DEFERRED;
    END IF;
END $$;

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_notes_subject ON notes(subject);
CREATE INDEX IF NOT EXISTS idx_notes_created_at ON notes(created_at);

-- Trigger for updated_at
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'update_notes_updated_at'
    ) THEN
        CREATE TRIGGER update_notes_updated_at
            BEFORE UPDATE ON notes
            FOR EACH ROW
            EXECUTE FUNCTION set_updated_at();
    END IF;
END $$;

-- ============================================================================
-- 2. AUDIO_LESSONS TABLE (MP3 Audio Lessons)
-- ============================================================================
CREATE TABLE IF NOT EXISTS audio_lessons (
    id SERIAL PRIMARY KEY,
    subject VARCHAR(50) NOT NULL,
    title VARCHAR(255),
    file_url TEXT,
    file_size_bytes BIGINT,
    duration_seconds INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add unique constraint
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'unique_audio_subject'
    ) THEN
        ALTER TABLE audio_lessons ADD CONSTRAINT unique_audio_subject
        UNIQUE (subject) DEFERRABLE INITIALLY DEFERRED;
    END IF;
END $$;

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_audio_lessons_subject ON audio_lessons(subject);
CREATE INDEX IF NOT EXISTS idx_audio_lessons_created_at ON audio_lessons(created_at);

-- Trigger for updated_at
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'update_audio_lessons_updated_at'
    ) THEN
        CREATE TRIGGER update_audio_lessons_updated_at
            BEFORE UPDATE ON audio_lessons
            FOR EACH ROW
            EXECUTE FUNCTION set_updated_at();
    END IF;
END $$;

-- ============================================================================
-- 3. NOTES_ACCESS TABLE (Track which users accessed which notes)
-- ============================================================================
CREATE TABLE IF NOT EXISTS notes_access (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL,
    subject VARCHAR(50),
    access_type VARCHAR(20),  -- 'read', 'download', 'listen'
    accessed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add foreign key constraint
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_notes_access_telegram_id'
    ) THEN
        ALTER TABLE notes_access
        ADD CONSTRAINT fk_notes_access_telegram_id
        FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE;
    END IF;
END $$;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_notes_access_telegram_id ON notes_access(telegram_id);
CREATE INDEX IF NOT EXISTS idx_notes_access_subject ON notes_access(subject);
CREATE INDEX IF NOT EXISTS idx_notes_access_type ON notes_access(access_type);

-- ============================================================================
-- SUCCESS MESSAGE
-- ============================================================================
DO $$
BEGIN
    RAISE NOTICE '✅ Additional tables created successfully!';
    RAISE NOTICE '📚 notes table ready for study materials';
    RAISE NOTICE '🎵 audio_lessons table ready for MP3 files';
    RAISE NOTICE '📊 notes_access table ready for tracking access';
END $$;
