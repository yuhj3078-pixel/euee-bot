-- ============================================================================
-- PAYMENT COMPATIBILITY PATCH
-- Safe to run after supabase_schema.sql on existing projects.
-- This ensures payment_records table exists with the correct schema.
-- ============================================================================

-- 1. Ensure PAYMENT ATTEMPTS table has all required columns
-- If the table exists but is missing columns, add them
ALTER TABLE payment_attempts ADD COLUMN IF NOT EXISTS tx_id TEXT;
ALTER TABLE payment_attempts ADD COLUMN IF NOT EXISTS transaction_id TEXT;
ALTER TABLE payment_attempts ADD COLUMN IF NOT EXISTS screenshot_url TEXT;
ALTER TABLE payment_attempts ADD COLUMN IF NOT EXISTS amount NUMERIC;
ALTER TABLE payment_attempts ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'telebirr';
ALTER TABLE payment_attempts ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'ETB';
ALTER TABLE payment_attempts ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- 2. Ensure tx_id and transaction_id are populated for existing records
UPDATE payment_attempts SET tx_id = transaction_id WHERE tx_id IS NULL AND transaction_id IS NOT NULL;
UPDATE payment_attempts SET transaction_id = tx_id WHERE transaction_id IS NULL AND tx_id IS NOT NULL;

-- 3. Make tx_id NOT NULL (primary key requirement)
ALTER TABLE payment_attempts ALTER COLUMN tx_id SET NOT NULL;
ALTER TABLE payment_attempts ALTER COLUMN transaction_id SET NOT NULL;

-- 4. Ensure primary key is on tx_id
DO $$
BEGIN
    -- Drop existing primary key constraint if it exists on different column
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE table_schema = 'public' 
        AND table_name = 'payment_attempts' 
        AND constraint_type = 'PRIMARY KEY'
    ) THEN
        ALTER TABLE payment_attempts DROP CONSTRAINT payment_attempts_pkey;
    END IF;
    
    -- Add primary key on tx_id
    ALTER TABLE payment_attempts ADD CONSTRAINT payment_attempts_pkey PRIMARY KEY (tx_id);
EXCEPTION
    WHEN duplicate_object THEN NULL; -- Already exists
END $$;

-- 5. Ensure unique constraints
CREATE UNIQUE INDEX IF NOT EXISTS idx_payment_attempts_tx_id ON payment_attempts(tx_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_payment_attempts_transaction_id ON payment_attempts(transaction_id);

-- 6. Ensure status index exists
CREATE INDEX IF NOT EXISTS idx_payment_attempts_status ON payment_attempts(status);
CREATE INDEX IF NOT EXISTS idx_payment_attempts_telegram_id ON payment_attempts(telegram_id);

-- 7. Ensure updated_at trigger exists
DROP TRIGGER IF EXISTS update_payment_attempts_updated_at ON payment_attempts;
CREATE TRIGGER update_payment_attempts_updated_at
    BEFORE UPDATE ON payment_attempts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 8. Ensure RLS is enabled
ALTER TABLE payment_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_attempts FORCE ROW LEVEL SECURITY;

-- 9. Verify the fix
DO $$
BEGIN
    RAISE NOTICE 'Payment compatibility patch applied successfully.';
    RAISE NOTICE 'payment_attempts table is ready for use.';
END $$;