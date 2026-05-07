-- ============================================================================
-- PAYMENT / BATTLE COMPATIBILITY PATCH
-- Safe to run after supabase_schema.sql on existing projects.
-- ============================================================================

-- 1. Ensure BOSS FIGHTS table exists and has a stable uniqueness rule
CREATE TABLE IF NOT EXISTS boss_fights (
    id TEXT PRIMARY KEY,
    year INTEGER NOT NULL,
    week INTEGER NOT NULL,
    subject TEXT NOT NULL,
    question TEXT NOT NULL,
    model_answer TEXT,
    explanation TEXT,
    completers JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_boss_fights_year_week_unique
    ON boss_fights(year, week);

-- 2. Ensure PAYMENT ATTEMPTS exists in the format the bot expects
CREATE TABLE IF NOT EXISTS payment_attempts (
    tx_id TEXT PRIMARY KEY,
    transaction_id TEXT UNIQUE,
    telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    username VARCHAR(100),
    plan_requested VARCHAR(50) NOT NULL,
    screenshot_url TEXT,
    status VARCHAR(20) DEFAULT 'PENDING',
    amount NUMERIC,
    source TEXT DEFAULT 'manual_review',
    currency TEXT DEFAULT 'ETB',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Add compatibility columns if an older schema already created the table
ALTER TABLE payment_attempts ADD COLUMN IF NOT EXISTS tx_id TEXT;
ALTER TABLE payment_attempts ADD COLUMN IF NOT EXISTS transaction_id TEXT;
ALTER TABLE payment_attempts ADD COLUMN IF NOT EXISTS screenshot_url TEXT;
ALTER TABLE payment_attempts ADD COLUMN IF NOT EXISTS amount NUMERIC;
ALTER TABLE payment_attempts ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'manual_review';
ALTER TABLE payment_attempts ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'ETB';
ALTER TABLE payment_attempts ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

UPDATE payment_attempts
SET tx_id = COALESCE(tx_id, transaction_id)
WHERE tx_id IS NULL;

UPDATE payment_attempts
SET transaction_id = COALESCE(transaction_id, tx_id)
WHERE transaction_id IS NULL;

ALTER TABLE payment_attempts ALTER COLUMN tx_id SET NOT NULL;
ALTER TABLE payment_attempts ALTER COLUMN transaction_id SET NOT NULL;

-- 4. Move the primary key to tx_id when an older schema used transaction_id
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'payment_attempts'
          AND constraint_type = 'PRIMARY KEY'
          AND constraint_name = 'payment_attempts_pkey'
    ) THEN
        BEGIN
            ALTER TABLE payment_attempts DROP CONSTRAINT payment_attempts_pkey;
        EXCEPTION
            WHEN undefined_object THEN NULL;
        END;
    END IF;

    BEGIN
        ALTER TABLE payment_attempts ADD CONSTRAINT payment_attempts_pkey PRIMARY KEY (tx_id);
    EXCEPTION
        WHEN duplicate_table THEN NULL;
        WHEN duplicate_object THEN NULL;
    END;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS idx_payment_attempts_tx_id
    ON payment_attempts(tx_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_payment_attempts_transaction_id
    ON payment_attempts(transaction_id);

CREATE INDEX IF NOT EXISTS idx_payment_attempts_status
    ON payment_attempts(status);

CREATE INDEX IF NOT EXISTS idx_payment_attempts_telegram_id
    ON payment_attempts(telegram_id);

-- 5. Keep updated_at fresh on edits
CREATE OR REPLACE FUNCTION payment_attempts_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_payment_attempts_updated_at ON payment_attempts;
CREATE TRIGGER update_payment_attempts_updated_at
    BEFORE UPDATE ON payment_attempts
    FOR EACH ROW
    EXECUTE FUNCTION payment_attempts_set_updated_at();

-- 6. RLS stays on for sensitive tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE boss_fights ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    RAISE NOTICE 'Payment compatibility patch applied successfully.';
END $$;
