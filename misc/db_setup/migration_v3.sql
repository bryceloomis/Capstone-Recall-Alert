-- =============================================================================
-- migration_v3.sql — user_carts: support receipt-sourced items (no UPC)
--
-- What changed and why:
--   1. Drop NOT NULL on product_upc — receipt items have no barcode/UPC.
--      Barcode-scanned items will still always provide a UPC; only receipt
--      items will leave this NULL.
--
--   2. Add source column ('barcode' | 'receipt') so alert generation in
--      user_alerts.py knows to use exact UPC matching vs fuzzy name matching.
--
--   3. Partial unique index on (user_id, product_name) WHERE product_upc IS NULL
--      — deduplicates receipt items by name per user.
--      The existing UNIQUE(user_id, product_upc) still deduplicates barcode items.
--      (PostgreSQL NULLs are never equal in unique constraints, so we need a
--       separate index for the receipt item case.)
--
-- Run once against the RDS instance (safe — all DDL is guarded):
--   psql $DATABASE_URL -f migration_v3.sql
-- =============================================================================

BEGIN;

-- ── 1. Drop NOT NULL on product_upc ──────────────────────────────────────────
DO $$
BEGIN
    ALTER TABLE user_carts ALTER COLUMN product_upc DROP NOT NULL;
    RAISE NOTICE 'Dropped NOT NULL on user_carts.product_upc';
EXCEPTION
    WHEN others THEN
        RAISE NOTICE 'Could not drop NOT NULL on product_upc (may already be nullable): %', SQLERRM;
END $$;

-- ── 2. Add source column ──────────────────────────────────────────────────────
DO $$
BEGIN
    ALTER TABLE user_carts
        ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'barcode';
    RAISE NOTICE 'Added source column to user_carts';
EXCEPTION
    WHEN duplicate_column THEN
        RAISE NOTICE 'source column already exists, skipping';
END $$;

-- ── 3. Partial unique index for receipt items ─────────────────────────────────
DO $$
BEGIN
    CREATE UNIQUE INDEX uq_user_carts_receipt_item
        ON user_carts (user_id, product_name)
        WHERE product_upc IS NULL;
    RAISE NOTICE 'Created partial unique index uq_user_carts_receipt_item';
EXCEPTION
    WHEN duplicate_table THEN
        RAISE NOTICE 'Index uq_user_carts_receipt_item already exists, skipping';
END $$;

COMMIT;
